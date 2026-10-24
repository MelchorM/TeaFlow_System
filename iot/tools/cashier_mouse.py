"""Control a readable TeaFlow cashier display through its USB serial cable.

The wired mouse connects to Windows. Input is sent only while this window's
control area has focus; global mouse input is never captured.
"""
import argparse
import queue
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

try:
    import serial
except ImportError:
    # The project's PlatformIO runtime already supplies this pure-Python module.
    sys.path.append(str(Path(__file__).resolve().parents[2] / '.tools/python-packages'))
    import serial
from serial.tools import list_ports
from mouse_protocol import Acknowledgement, Frame, HEIGHT, InputBuffer, WIDTH


class SerialBridge(threading.Thread):
    def __init__(self, inputs, messages, port=None):
        super().__init__(name='TeaFlow cashier mouse', daemon=True)
        self.inputs, self.messages, self.port = inputs, messages, port
        self.stopping = threading.Event()
        self.reconnect = threading.Event()
        self.connected = threading.Event()
        self.current_port = ''
        self.status = ''

    def report(self, text):
        if text != self.status:
            self.status = text
            self.messages.put(text)
            print(text, flush=True)

    def choose_port(self):
        if self.port:
            return self.port
        candidates = [p.device for p in list_ports.comports() if p.vid == 0x1A86]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            self.report('More than one CH340 board found. Restart with --port COMnumber.')
        else:
            self.report('Connect the cashier USB data cable to the laptop or hub.')
        return None

    def run(self):
        while not self.stopping.is_set():
            self.reconnect.clear()
            try:
                port = self.choose_port()
                if port:
                    self.session(port)
            except (serial.SerialException, OSError, RuntimeError) as error:
                self.report(f'Not connected: {error}')
            finally:
                self.connected.clear()
                self.inputs.reset()
            self.stopping.wait(2)

    def session(self, port):
        connection = serial.Serial(port=None, baudrate=115200, timeout=0.02, write_timeout=0.5)
        connection.dtr = False
        connection.rts = False
        connection.port = port
        received = bytearray()

        def lines():
            received.extend(connection.read(min(max(connection.in_waiting, 1), 1024)))
            while b'\n' in received:
                line, _, remainder = received.partition(b'\n')
                received[:] = remainder
                yield line.decode('ascii', errors='replace').strip()
            if len(received) > 4096:
                received.clear()

        def wait_for(prefix, timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not self.stopping.is_set() and not self.reconnect.is_set():
                for line in lines():
                    if line.startswith(prefix):
                        return
            raise RuntimeError('No cashier mouse handshake. Check the firmware and close Serial Monitor.')

        self.report(f'Checking cashier on {port}...')
        try:
            connection.open()
            time.sleep(0.3)
            connection.reset_input_buffer()
            connection.write(b'mouse hello\n')
            wait_for('TFMOUSE READY 1 800 480 JC8048W550', 8)
            connection.write(b'mouse begin\n')
            wait_for('TFMOUSE ACTIVE 1', 8)
            self.current_port = port
            self.inputs.reset()
            self.connected.set()
            self.report(f'Connected on {port} - move inside the mouse area; watch the ESP32 screen.')
            acknowledgement = Acknowledgement()
            last_sent = 0.0
            while not self.stopping.is_set() and not self.reconnect.is_set():
                for line in lines():
                    acknowledgement.receive(line)
                    if line.startswith('TFMOUSE ERROR'):
                        raise RuntimeError(line.removeprefix('TFMOUSE ERROR '))
                if acknowledgement.timed_out():
                    raise RuntimeError('The board stopped acknowledging input. Pending clicks canceled.')
                now = time.monotonic()
                if acknowledgement.pending is None and now - last_sent >= 0.04:
                    event = self.inputs.take()
                    if event is None and now - last_sent >= 1.0:
                        event = Frame('p', 0, 0, now)
                    if event:
                        connection.write(acknowledgement.send(event))
                        last_sent = now
        finally:
            self.connected.clear()
            self.inputs.reset()
            if connection.is_open:
                try:
                    # Stop cancels a held click; it never synthesizes release.
                    connection.write(b'mouse stop\n')
                    connection.flush()
                except (serial.SerialException, OSError):
                    pass
                connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Override CH340 detection, for example COM8')
    args = parser.parse_args()
    inputs, messages = InputBuffer(), queue.SimpleQueue()
    bridge = SerialBridge(inputs, messages, args.port)
    root = tk.Tk()
    root.title('TeaFlow cashier mouse control')
    root.geometry('850x650')
    root.minsize(660, 470)
    root.configure(bg='#f5f9f6')
    root.option_add('*Font', ('Segoe UI', 11))
    outer = ttk.Frame(root, padding=16)
    outer.pack(fill='both', expand=True)
    ttk.Label(outer, text='TeaFlow cashier mouse control', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
    ttk.Label(outer, text='Keep this window open. Move in the area below and left-click while looking at the ESP32.', wraplength=750).pack(anchor='w', pady=(8, 12))
    canvas = tk.Canvas(outer, width=WIDTH, height=HEIGHT, bg='#e9f3ec', highlightthickness=2, highlightbackground='#22664f', cursor='crosshair')
    canvas.pack(fill='both', expand=True)
    caption = canvas.create_text(400, 210, text='Move your mouse here\nWatch the cursor on the cashier screen', fill='#22664f', font=('Segoe UI', 17), justify='center')
    cursor = canvas.create_oval(-30, -30, -10, -10, outline='#172f27', width=2)
    status = tk.StringVar(value='Finding the cashier USB connection...')
    ttk.Label(outer, textvariable=status, wraplength=800).pack(anchor='w', pady=(10, 4))
    ttk.Label(outer, text='Left-click = tap   |   Drag or leave the area = cancel   |   First click wakes a dimmed screen', font=('Segoe UI', 10)).pack(anchor='w')
    controls = ttk.Frame(outer)
    controls.pack(fill='x', pady=(10, 0))

    def cancel(_event=None):
        inputs.cancel()

    def reconnect():
        inputs.cancel()
        bridge.connected.clear()
        bridge.reconnect.set()
        status.set('Reconnecting; queued clicks have been canceled...')

    def location(event):
        return (event.x * WIDTH / max(1, canvas.winfo_width()), event.y * HEIGHT / max(1, canvas.winfo_height()))

    def motion(event):
        canvas.coords(cursor, event.x - 7, event.y - 7, event.x + 7, event.y + 7)
        if bridge.connected.is_set():
            inputs.motion(*location(event))

    def press(event):
        canvas.focus_set()
        if bridge.connected.is_set():
            inputs.press(*location(event))

    def release(event):
        if bridge.connected.is_set():
            inputs.release(*location(event))

    def resized(event):
        canvas.coords(caption, event.width / 2, event.height / 2)

    def focus_changed(_event):
        # Moving focus between our own controls must not eat the first click.
        root.after_idle(lambda: cancel() if root.focus_displayof() is None else None)

    def close():
        inputs.cancel()
        bridge.stopping.set()
        bridge.join(timeout=0.8)
        root.destroy()

    def update_status():
        try:
            while True:
                status.set(messages.get_nowait())
        except queue.Empty:
            pass
        root.after(100, update_status)

    ttk.Button(controls, text='Cancel click', command=cancel).pack(side='left')
    ttk.Button(controls, text='Reconnect', command=reconnect).pack(side='left', padx=10)
    ttk.Button(controls, text='Close mouse control', command=close).pack(side='right')
    canvas.bind('<Motion>', motion)
    canvas.bind('<ButtonPress-1>', press)
    canvas.bind('<ButtonRelease-1>', release)
    canvas.bind('<Leave>', cancel)
    canvas.bind('<Configure>', resized)
    root.bind('<Escape>', cancel)
    root.bind('<FocusOut>', focus_changed)
    root.protocol('WM_DELETE_WINDOW', close)
    bridge.start()
    update_status()
    root.mainloop()


if __name__ == '__main__':
    main()
