import eyed3
from eyed3.core import Date
from eyed3.id3.frames import ImageFrame
from yandex_music import Track

eyed3.log.setLevel("ERROR")


class TagEditor:

    @staticmethod
    def set_all_tags(track: Track, audio_filepath: str, cover_image) -> None:
        audiofile = eyed3.load(audio_filepath)
        audiofile.initTag(version=(2, 3, 0))

        # SET TITLE SONG
        track_title = track.title
        if track.filename and not track.artists:
            track_title = track_title.split(" - ")[1].replace(".mp3", "")
        else:
            track_title = f"{track_title} ({track.version})" if track.version else track_title
        audiofile.tag.title = track_title

        # SET ARTIST NAME
        if track.artists:
            artist_tag = f"{track.artists[0].name}"
        elif len(track.artists) > 1:
            artists_name = ", ".join([artist.name for artist in track.artists])
            artist_tag = f"{artists_name}"
        else:
            artist_tag = track.title.split(" - ")[0]
        audiofile.tag.artist = artist_tag

        # SET FRONT COVER
        if not isinstance(cover_image, bytes):
            cover_image = open(cover_image, 'rb').read()
        audiofile.tag.images.set(ImageFrame.FRONT_COVER, cover_image, 'image/png')

        # SET ICON, ASK ??
        # img = Image.open(io.BytesIO(cover_image))
        # img = img.resize((32, 32))
        # img_byte_arr = io.BytesIO()
        # img.save(img_byte_arr, format='PNG')
        # audiofile.tag.images.set(ImageFrame.ICON, cover_image, 'image/png')

        # SET ALBUM THINGS
        if len(track.albums) > 0:
            album = track.albums[0]
            audiofile.tag.album = album.title
            if album.year:
                audiofile.tag.recording_date = Date(album.year)
            if album.genre:
                audiofile.tag.genre = album.genre
            if album.track_position:
                audiofile.tag.track_num = album.track_position.index

        else:
            audiofile.tag.album = "No album"

        audiofile.tag.save()
