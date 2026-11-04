from contextlib import contextmanager
from contextvars import ContextVar

_device = ContextVar("actor_device", default=None)


def current_device():
    return _device.get()


@contextmanager
def device_context(device):
    token = _device.set(device)
    try:
        yield
    finally:
        _device.reset(token)


def actor_name(staff=None):
    if staff:
        return staff.name
    device = current_device()
    return device.name if device else "Development staff"
