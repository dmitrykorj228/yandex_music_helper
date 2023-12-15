import os
from pathlib import Path

import eyed3
from eyed3.id3.frames import ImageFrame
from yandex_music import Track

from utils.wrappers import call_function

eyed3.log.setLevel("ERROR")


class TagEditor:

    @staticmethod
    async def set_tags(track: Track, track_fullname: str) -> None:
        if track.cover_uri:
            cover_image = track_fullname.replace(".mp3", ".png")
            await call_function(track.download_cover_async, cover_image)
            TagEditor.set_front_cover(track_fullname, cover_image)
        else:
            cover_image = str(Path(os.getcwd(), "default_front_cover.png"))
            TagEditor.set_front_cover(track_fullname, cover_image, unlink=False)

    @staticmethod
    def set_front_cover(audio_filepath: str, cover_image: str, unlink=True) -> None:
        """
        Sets the front cover image of an audio file.

        :param audio_filepath: The file path of the audio file.
        :type audio_filepath: str
        :param cover_image: The file path of the cover image.
        :type cover_image: str
        :param unlink: Whether to unlink the cover image file after setting it. Defaults to True.
        :type unlink: bool, optional
        :return: None
        """
        audiofile = eyed3.load(audio_filepath)
        audiofile.initTag()
        audiofile.tag.images.set(ImageFrame.FRONT_COVER, open(cover_image, 'rb').read(), 'image/png')
        audiofile.tag.save()
        if unlink:
            Path(cover_image).unlink()
