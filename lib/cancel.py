import threading

_cancel_event = threading.Event()


def is_cancelled():
    return _cancel_event.is_set()


def request_cancel():
    _cancel_event.set()


def reset():
    _cancel_event.clear()
