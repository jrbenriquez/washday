from contextvars import ContextVar
from contextlib import contextmanager

_shop = ContextVar("shop", default=None)


def current_shop():
    return _shop.get()


@contextmanager
def shop_context(shop):
    token = _shop.set(getattr(shop, "pk", shop))
    try:
        yield
    finally:
        _shop.reset(token)
