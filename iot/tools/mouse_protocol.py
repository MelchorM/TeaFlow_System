"""Bounded, acknowledged input for the cashier's local USB serial bridge."""
from collections import deque
from dataclasses import dataclass
import threading
import time

WIDTH, HEIGHT = 800, 480


def position(x, y):
    return max(0, min(WIDTH - 1, int(x))), max(0, min(HEIGHT - 1, int(y)))


@dataclass(frozen=True)
class Frame:
    kind: str
    x: int
    y: int
    created: float

    def encode(self, sequence):
        if self.kind not in 'mducp' or len(self.kind) != 1:
            raise ValueError('Unknown mouse event')
        if not 1 <= sequence <= 0xFFFFFFFF or position(self.x, self.y) != (self.x, self.y):
            raise ValueError('Invalid mouse frame')
        return f'mouse {sequence} {self.kind} {self.x} {self.y}\n'.encode('ascii')


class InputBuffer:
    """Coalesce movement; preserve press/release order; expire delayed clicks."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.edges = deque()
            self.movement = None
            self.down = None
            self.dragged = False

    def motion(self, x, y):
        x, y = position(x, y)
        with self.lock:
            self.movement = Frame('m', x, y, self.clock())
            if self.down and (abs(x - self.down[0]) > 8 or abs(y - self.down[1]) > 8):
                self.dragged = True

    def press(self, x, y):
        x, y = position(x, y)
        with self.lock:
            self.movement = None
            self.down = (x, y)
            self.dragged = False
            self.edges.append(Frame('d', x, y, self.clock()))
            self._bound()

    def release(self, x, y):
        x, y = position(x, y)
        with self.lock:
            if self.down is None:
                return
            dragged = self.dragged or abs(x - self.down[0]) > 8 or abs(y - self.down[1]) > 8
            self.movement = None
            self.edges.append(Frame('c' if dragged else 'u', x, y, self.clock()))
            self.down = None
            self.dragged = False
            self._bound()

    def cancel(self):
        with self.lock:
            self.edges.clear()
            self.movement = None
            self.down = None
            self.dragged = False
            self.edges.append(Frame('c', 0, 0, self.clock()))

    def _bound(self):
        # A stalled board must not play back a burst of clicks later.
        if len(self.edges) > 12:
            self.edges.clear()
            self.edges.append(Frame('c', 0, 0, self.clock()))
            self.down = None
            self.dragged = False

    def take(self):
        with self.lock:
            if self.edges:
                event = self.edges.popleft()
                if self.clock() - event.created > 1.0:
                    self.edges.clear()
                    self.movement = None
                    self.down = None
                    self.dragged = False
                    return Frame('c', 0, 0, self.clock())
                return event
            event, self.movement = self.movement, None
            return event


class Acknowledgement:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.sequence = 0
        self.pending = None
        self.sent_at = 0.0

    def send(self, frame):
        if self.pending is not None:
            raise RuntimeError('Wait for the board acknowledgement')
        if self.sequence == 0xFFFFFFFF:
            raise RuntimeError('Reconnect to renew the sequence')
        self.sequence += 1
        packet = frame.encode(self.sequence)
        self.pending = self.sequence
        self.sent_at = self.clock()
        return packet

    def receive(self, line):
        if self.pending is not None and line == f'TFMOUSE ACK {self.pending}':
            self.pending = None
            return True
        return False

    def timed_out(self):
        return self.pending is not None and self.clock() - self.sent_at > 8.0
