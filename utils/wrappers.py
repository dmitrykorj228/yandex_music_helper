import asyncio
import logging

from retrying import retry
from yandex_music.exceptions import InvalidBitrateError, TimedOutError


@retry(stop_max_attempt_number=10)
async def call_function(func, *args, **kwargs):
    max_tries = 10
    arg_value = None
    arg_type = None
    if len(args):
        if isinstance(args[0], int):
            arg_value = 'playlist'
        elif isinstance(args[0], str):
            arg_type = 'track'
            arg_value = args[0]

    while max_tries > 0:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, InvalidBitrateError):
                raise InvalidBitrateError
            elif isinstance(e, TimedOutError):
                max_tries -= 1
                if arg_type == 'track':
                    logging.warning(
                        f"[{arg_value}] Failed to download. Retrying in 3 seconds... ({max_tries} tries left)")
                else:
                    if func.__name__ == 'fetch_track_async':
                        max_tries_additional_message = ""
                        if max_tries <= 3:
                            max_tries_additional_message = f"({max_tries} tries left)"
                        logging.warning(
                            f"{type(e).__name__}, Failed to fetch track. Retrying in 3 seconds... {max_tries_additional_message}")
                    else:
                        logging.warning(
                            f"{type(e).__name__}, trying to repeat action after 3 seconds. Attempts left = {max_tries}.")
                await asyncio.sleep(3)
            else:
                logging.error(str(e))
