import functools


def safe_loop():
    """Run coroutine in a safe loop.

    The coroutine runs in a 'while True' loop
    and exceptions logged.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            logger = args[0].logger
            while True:
                try:
                    res = await func(*args)
                    if res is True:
                        break
                except Exception:
                    logger.error("Unkown exception", exc_info=True)

        return wrapped

    return wrapper
