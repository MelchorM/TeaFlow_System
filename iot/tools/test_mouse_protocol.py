import unittest
from mouse_protocol import Acknowledgement, Frame, InputBuffer, position


class MouseProtocolTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.inputs = InputBuffer(clock=lambda: self.now)

    def test_only_latest_motion_survives_without_a_backlog(self):
        for i in range(10000):
            self.inputs.motion(i % 800, i % 480)
        event = self.inputs.take()
        self.assertEqual((event.kind, event.x, event.y), ('m', 399, 399))
        self.assertIsNone(self.inputs.take())

    def test_click_coordinates_and_order_survive_motion_coalescing(self):
        self.inputs.motion(5, 5)
        self.inputs.press(400, 200)
        self.inputs.motion(402, 201)
        self.inputs.release(402, 201)
        events = [self.inputs.take(), self.inputs.take()]
        self.assertEqual([(e.kind, e.x, e.y) for e in events], [('d', 400, 200), ('u', 402, 201)])
        self.assertIsNone(self.inputs.take())

    def test_drag_outside_then_back_cannot_turn_into_a_click(self):
        self.inputs.press(100, 100)
        self.inputs.motion(200, 100)
        self.inputs.motion(100, 100)
        self.inputs.release(100, 100)
        self.assertEqual(self.inputs.take().kind, 'd')
        self.assertEqual(self.inputs.take().kind, 'c')

    def test_expired_press_discards_all_pending_clicks(self):
        self.inputs.press(400, 200)
        self.inputs.release(400, 200)
        self.now += 1.1
        self.assertEqual(self.inputs.take().kind, 'c')
        self.assertIsNone(self.inputs.take())

    def test_expired_release_cancels_an_already_sent_press(self):
        self.inputs.press(400, 200)
        self.assertEqual(self.inputs.take().kind, 'd')
        self.inputs.release(400, 200)
        self.now += 1.1
        self.assertEqual(self.inputs.take().kind, 'c')

    def test_focus_loss_cancels_instead_of_releasing(self):
        self.inputs.press(400, 200)
        self.inputs.cancel()
        self.inputs.release(400, 200)
        self.assertEqual(self.inputs.take().kind, 'c')
        self.assertIsNone(self.inputs.take())

    def test_rapid_click_burst_is_canceled_when_board_is_stalled(self):
        for _ in range(7):
            self.inputs.press(400, 200)
            self.inputs.release(400, 200)
        events = []
        while (event := self.inputs.take()) is not None:
            events.append(event.kind)
        self.assertEqual(events, ['c'])

    def test_reconnect_starts_with_no_queued_press_or_release(self):
        self.inputs.press(400, 200)
        self.inputs.release(400, 200)
        self.inputs.reset()
        self.assertIsNone(self.inputs.take())
        self.inputs.release(400, 200)
        self.assertIsNone(self.inputs.take())

    def test_outside_coordinates_are_clamped_but_invalid_frames_are_rejected(self):
        self.assertEqual(position(-15, 900), (0, 479))
        for frame in [Frame('u', 800, 100, 0), Frame('bad', 100, 100, 0)]:
            with self.assertRaises(ValueError):
                frame.encode(1)
        self.assertEqual(Frame('u', 799, 479, 0).encode(123), b'mouse 123 u 799 479\n')

    def test_wait_for_exact_ack_before_sending_another_frame(self):
        ack = Acknowledgement(clock=lambda: self.now)
        frame = Frame('m', 10, 10, self.now)
        self.assertEqual(ack.send(frame), b'mouse 1 m 10 10\n')
        with self.assertRaises(RuntimeError):
            ack.send(frame)
        self.assertFalse(ack.receive('Wi-Fi status=3'))
        self.assertFalse(ack.receive('TFMOUSE ACK 2'))
        self.assertTrue(ack.receive('TFMOUSE ACK 1'))
        self.assertFalse(ack.receive('TFMOUSE ACK 1'))
        self.assertEqual(ack.send(frame), b'mouse 2 m 10 10\n')

    def test_missing_ack_times_out_without_replaying_a_click(self):
        ack = Acknowledgement(clock=lambda: self.now)
        ack.send(Frame('u', 10, 10, self.now))
        self.now += 8.1
        self.assertTrue(ack.timed_out())
        self.assertEqual(ack.sequence, 1)
        self.assertEqual(ack.pending, 1)


if __name__ == '__main__':
    unittest.main()
