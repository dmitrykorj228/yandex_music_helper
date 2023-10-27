import asyncio
import logging
import os
import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Union, List, Tuple
import telegram
import yaml
from retrying import retry
from yandex_music import ClientAsync, Track

from music_database import MusicDatabase
from utils.file import zip_folder
from youtube_to_mp3_downloader import get_mp3_from_video

file_log = logging.FileHandler('log.log')
console_out = logging.StreamHandler()

logging.basicConfig(handlers=(file_log, console_out),
                    format='[%(asctime)s | %(levelname)s]: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO)
DOWNLOADED_MUSIC_FOLDER_TEMPLATE = "downloaded_tracks_{}"
TELEGRAM_BOT_MESSAGE_PREFIX = "❗️ New unavailable music found ❗️️ \nCount: {}\nPlaylist «{}» \n \n"
MAX_TELEGRAM_MESSAGE_LENGTH = 4096


class YandexMusicHelper:
    def __init__(self, config_params):
        self.config = yaml.full_load(open("config.yaml", "r"))
        self.telegram_bot_config = self.config['TelegramBot']
        self.user_config = self.config[config_params.username]
        self.async_client = self.get_async_client()
        self.download_path = Path(
            os.getcwd(), DOWNLOADED_MUSIC_FOLDER_TEMPLATE.format(self.user_config['playlist_owner_name']))

    async def get_async_client(self):
        return await ClientAsync(self.user_config['auth_token']).init()

    async def search_unavailable_songs(self, playlist_index):
        playlist_owner_name = self.user_config['playlist_owner_name']
        db = MusicDatabase(self.user_config)
        logging.info(f'Getting tracks of playlist #{playlist_index}, owner={playlist_owner_name}')
        playlist_title, playlist_tracks = await self.call_function(self.get_album, playlist_index, playlist_owner_name,
                                                                   search_unavailable=True)
        if not playlist_tracks:
            logging.error(f"Playlist {playlist_index} doesn't contain tracks!")
            return

        data = []
        new_unavailable_tracks = []
        db_tracks = db.get_track_by_album(playlist_index)
        for track, track_id in playlist_tracks:
            if track_id not in db_tracks:
                new_unavailable_tracks.append(track)
                data.append((track, track_id, playlist_index, False))
        bot = telegram.Bot(self.telegram_bot_config['token'])
        if new_unavailable_tracks:
            zip_path = None
            logging.info(f'Fetching done! Found {len(playlist_tracks)} new unavailable tracks.')
            db.insert_to_table(data)
            downloaded_count = get_mp3_from_video(new_unavailable_tracks, output_path=str(self.download_path))
            if downloaded_count:
                zip_path = zip_folder(Path(Path(os.getcwd()), f"downloaded_tracks_{playlist_owner_name}"),
                                      playlist_owner_name)
            async with bot:
                message = TELEGRAM_BOT_MESSAGE_PREFIX.format(
                    len(new_unavailable_tracks), playlist_title) + "\n".join(
                    new_unavailable_tracks)
                if len(message) > MAX_TELEGRAM_MESSAGE_LENGTH:
                    for x in range(0, len(message), MAX_TELEGRAM_MESSAGE_LENGTH):
                        await bot.send_message(text=message[x:x + MAX_TELEGRAM_MESSAGE_LENGTH],
                                               chat_id=self.user_config['telegram_chat_id'])
                else:

                    await bot.send_message(text=message,
                                           chat_id=self.user_config['telegram_chat_id'])
                if zip_path:
                    for file in zip_path.rglob('*'):
                        await bot.send_document(self.user_config['telegram_chat_id'], document=file)
                    shutil.rmtree(self.download_path)
                    shutil.rmtree(zip_path)

        else:
            logging.info('Fetching done! New unavailable tracks not found.')

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
