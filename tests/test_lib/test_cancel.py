import threading

from lib.cancel import is_cancelled, request_cancel, reset


class TestCancel:
    def test_initial_state_is_not_cancelled(self):
        reset()
        assert is_cancelled() is False

    def test_request_cancel_sets_flag(self):
        reset()
        request_cancel()
        assert is_cancelled() is True

    def test_reset_clears_flag(self):
        request_cancel()
        reset()
        assert is_cancelled() is False

    def test_thread_safe_read_from_other_thread(self):
        reset()
        results = []

        def worker():
            results.append(is_cancelled())

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results == [False]

    def test_thread_sees_cancel_from_main(self):
        reset()
        results = []
        event = threading.Event()

        def worker():
            event.wait()
            results.append(is_cancelled())

        t = threading.Thread(target=worker)
        t.start()
        request_cancel()
        event.set()
        t.join()
        assert results == [True]
