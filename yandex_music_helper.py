import asyncio
import logging
from argparse import ArgumentParser
from typing import Union, List

import yaml
from retrying import retry
from yandex_music import ClientAsync, Track

file_log = logging.FileHandler('log.log')
console_out = logging.StreamHandler()

logging.basicConfig(handlers=(file_log, console_out),
                    format='[%(asctime)s | %(levelname)s]: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO)


class YandexMusicHelper:
    def __init__(self, config_params):
        self.config = yaml.full_load(open("config.yaml", "r"))[config_params.username]
        self.async_client = self.get_async_client()

    async def get_async_client(self):
        return await ClientAsync(self.config['token']).init()

    async def search_unavailable_songs(self):
        playlists = self.config['playlists']
        playlist_owner_name = self.config['owner_name']
        for playlist_index in playlists:
            logging.info(f'Getting tracks of playlist #{playlist_index}, owner={playlist_owner_name}')
            playlist_tracks = await self.call_function(self.get_album_tracks, playlist_index, playlist_owner_name,
                                                       search_unavailable=True)
            logging.info(f'Fetching done! Found {len(playlist_tracks)} unavailable tracks.')

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

    async def get_album_tracks(self, album_id: int, owner_name: str, search_unavailable=False) -> Union[
        List[Track], List[str]]:
        playlist_tracks = await self.call_function((await self.async_client).users_playlists, album_id, owner_name)
        track_list = []
        for track in playlist_tracks.tracks:
            full_track = await self.call_function(track.fetch_track_async)
            if full_track.available and not search_unavailable:
                track_list.append(full_track)
            elif not full_track.available and search_unavailable:
                track_name = self.get_track_fullname(full_track)
                track_list.append(track_name)

        return track_list

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
    await asyncio.gather(*([YandexMusicHelper(params).search_unavailable_songs()]))


def get_parsed_args():
    parser = ArgumentParser(description='YandexMusic. Unavailable music finder')
    parser.add_argument("-u", "--username", type=str, required=True,
                        help='Username in configfile')
    return parser.parse_args()


if __name__ == '__main__':
    args = get_parsed_args()
    asyncio.get_event_loop().run_until_complete(async_main(args))
