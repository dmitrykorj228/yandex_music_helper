import asyncio
import logging

from retrying import retry
from yandex_music.exceptions import InvalidBitrateError, TimedOutError


@retry(stop_max_attempt_number=10)
async def call_function(func, *args, **kwargs):
    max_tries = 10
    while max_tries > 0:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, InvalidBitrateError):
                raise InvalidBitrateError
            elif isinstance(e, TimedOutError):
                max_tries -= 1
                logging.warning(
                    f"{type(e).__name__}, trying to repeat action after 3 seconds. Attempts left = {max_tries}.")
                await asyncio.sleep(3)
            else:
                logging.error(str(e))
