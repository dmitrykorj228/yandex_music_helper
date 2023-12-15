import asyncio
import logging
import os
import platform
import shutil
import eyed3
import telegram
import yaml
from argparse import ArgumentParser
from pathlib import Path
from typing import Union, List, Tuple
from retrying import retry
from yandex_music import ClientAsync, Track
from yandex_music.exceptions import InvalidBitrateError, TimedOutError
from eyed3.id3.frames import ImageFrame
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

REMOVE_FILENAME_SYMBOLS = {"|", "/", "\\", "<", ">", "+", "\"", ":", "?", "*"}


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

    async def download_playlist(self, playlist_id: int):
        playlist_owner_name = self.user_config['playlist_owner_name']
        logging.info(f'Getting tracks of playlist #{playlist_id}, owner={playlist_owner_name}')
        playlist_title, playlist_tracks = await self.call_function(self.get_album, playlist_id, playlist_owner_name,
                                                                   search_unavailable=False)
        if not playlist_tracks:
            logging.error(f"Playlist {playlist_id} doesn't contain tracks!")
            return
        Path(self.user_config['save_path'], playlist_title).mkdir(parents=True, exist_ok=True)
        for track in playlist_tracks:
            track_filename = await self.get_track_fullname(track, str(playlist_title))
            if Path(track_filename).exists():
                logging.info(f"File already exists: {track_filename}")
                continue
            try:
                await self.call_function(track.download_async, track_filename, bitrate_in_kbps=320)
                logging.info(f"Successfully downloaded: {track_filename}")
            except InvalidBitrateError:
                logging.warning(f"Unfortunately, 320kbps is not available for: {track_filename} (trying 192kbps)")
                await self.call_function(track.download_async, track_filename)
                logging.info(f"Successfully downloaded with 192kbps: {track_filename}")

            # cover_image = track_filename.replace(".mp3", ".png")
            # await track.download_cover_async(cover_image)
            # self.set_front_cover(track_filename, cover_image)

    @retry(stop_max_attempt_number=10)
    async def call_function(self, func, *args, **kwargs):
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

    async def get_track_fullname(self, track: Track, playlist_id: str) -> str:
        title = track.title
        uploaded_track = True
        if ".mp3" not in track.title:
            uploaded_track = False
            if len(track.artists) > 1:
                artists_name = ", ".join([artist.name for artist in track.artists])
                title = f"{artists_name} - {track.title}"
            elif track.artists:
                title = f"{track.artists[0].name} - {title}"
            if track.version:
                title = f"{title} ({track.version})"
        for char in REMOVE_FILENAME_SYMBOLS:
            title = title.replace(char, "")
        save_path = str(Path(self.user_config['save_path'], playlist_id, title))
        return save_path if uploaded_track else f"{save_path}.mp3"

    def set_front_cover(self, audio_filepath: str, cover_image: str) -> None:
        """
        Sets the front cover image of an audio file.

        :param audio_filepath: The filepath of the audio file.
        :type audio_filepath: str
        :param cover_image: The filepath of the cover image file.
        :type cover_image: str
        :return: None
        """

        eyed3.log.setLevel("ERROR")
        audiofile = eyed3.load(audio_filepath)
        audiofile.initTag()
        audiofile.tag.images.set(ImageFrame.FRONT_COVER, open(cover_image, 'rb').read(), 'image/png')
        audiofile.tag.save()
        Path(cover_image).unlink()


async def async_main(params):
    if params.action.lower() == "download":
        await asyncio.gather(
            *(YandexMusicHelper(params).download_playlist(playlist) for playlist in params.playlists))
    else:
        await asyncio.gather(
            *(YandexMusicHelper(params).search_unavailable_songs(playlist) for playlist in params.playlists))


def get_parsed_args():
    parser = ArgumentParser(description='YandexMusic. Unavailable music finder')
    parser.add_argument("-a", "--action", type=str, required=True,
                        help='Select action [unavailable, download]')
    parser.add_argument("-u", "--username", type=str, required=True,
                        help='Username in configfile')
    parser.add_argument("-p", "--playlists", nargs="*", type=int, required=True,
                        help='Playlists list')
    return parser.parse_args()


if __name__ == '__main__':
    args = get_parsed_args()
    if platform.system().lower() == 'windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(async_main(args))
