import asyncio
import logging
from argparse import ArgumentParser
from typing import Union, List, Tuple
import telegram
import yaml
from retrying import retry
from yandex_music import ClientAsync, Track

from music_database import MusicDatabase

file_log = logging.FileHandler('log.log')
console_out = logging.StreamHandler()

logging.basicConfig(handlers=(file_log, console_out),
                    format='[%(asctime)s | %(levelname)s]: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO)

TELEGRAM_BOT_MESSAGE_PREFIX = "❗️ New unavailable music found ❗️️ \nCount: {}\nPlaylist «{}» \n \n"


class YandexMusicHelper:
    def __init__(self, config_params):
        self.config = yaml.full_load(open("config.yaml", "r"))[config_params.username]
        self.telegram_config = self.config['telegram']
        self.async_client = self.get_async_client()

    async def get_async_client(self):
        return await ClientAsync(self.config['token']).init()

    async def search_unavailable_songs(self, playlist_index):
        playlist_owner_name = self.config['owner_name']
        db = MusicDatabase(self.config)
        logging.info(f'Getting tracks of playlist #{playlist_index}, owner={playlist_owner_name}')
        playlist_title, playlist_tracks = await self.call_function(self.get_album, playlist_index, playlist_owner_name,
                                                                   search_unavailable=True)
        if playlist_tracks:
            data = []
            new_unavailable_tracks = []
            db_tracks = db.get_track_by_album(playlist_index)
            for track, track_id in playlist_tracks:
                if track_id not in db_tracks:
                    new_unavailable_tracks.append(track)
                    data.append((track, track_id, playlist_index, False))
            bot = telegram.Bot(self.telegram_config['token'])
            if new_unavailable_tracks:
                logging.info(f'Fetching done! Found {len(playlist_tracks)} new unavailable tracks.')
                db.insert_to_table(data)
                async with bot:
                    message = TELEGRAM_BOT_MESSAGE_PREFIX.format(
                        len(new_unavailable_tracks), playlist_title) + "\n".join(
                        new_unavailable_tracks)
                    if len(message) > 4096:
                        for x in range(0, len(message), 4096):
                            await bot.send_message(text=message[x:x + 4096],
                                                   chat_id=self.telegram_config['chat_id'])
                    else:
                        await bot.send_message(text=message,
                                               chat_id=self.telegram_config['chat_id'])

            else:
                logging.info('Fetching done! New unavailable tracks not found.')
        else:
            logging.error(f"Playlist {playlist_index} doesn't contain tracks!")

    @retry(stop_max_attempt_number=10)
    async def call_function(self, func, *args, **kwargs):
        max_tries = 10
        while max_tries > 0:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                max_tries -= 1
                logging.warning(
                    f"{type(e).__name__}, trying to repeat action after 3 seconds. Attempts left = {max_tries}.")
                await asyncio.sleep(3)

    async def get_album(self, album_id: int, owner_name: str, search_unavailable=False) -> Tuple[str, Union[
        List[Track], List[str]]]:
        playlist = await self.call_function((await self.async_client).users_playlists, album_id, owner_name)
        track_list = []
        for track in playlist.tracks:
            full_track = await self.call_function(track.fetch_track_async)
            if full_track.available and not search_unavailable:
                track_list.append(full_track)
            elif not full_track.available and search_unavailable:
                track_name = self.get_track_fullname(full_track)
                track_list.append((track_name, int(full_track.id)))

        return playlist.title, track_list

    def get_track_fullname(self, track: Track) -> str:
        title = track.title
        if len(track.artists) > 1:
            artists_name = ", ".join([artist.name for artist in track.artists])
            title = f"{artists_name} - {track.title}"
        else:
            title = f"{track.artists[0].name} - {title}"
        if track.version:
            title = f"{title} ({track.version})"
        full_name = title
        return full_name


async def async_main(params):
    """create three class instances and run do_work"""
    await asyncio.gather(
        *(YandexMusicHelper(params).search_unavailable_songs(playlist) for playlist in params.playlists))


def get_parsed_args():
    parser = ArgumentParser(description='YandexMusic. Unavailable music finder')
    parser.add_argument("-u", "--username", type=str, required=True,
                        help='Username in configfile')
    parser.add_argument("-p", "--playlists", nargs="*", type=int, required=True,
                        help='Playlists list')
    return parser.parse_args()


if __name__ == '__main__':
    args = get_parsed_args()
    asyncio.run(async_main(args))
