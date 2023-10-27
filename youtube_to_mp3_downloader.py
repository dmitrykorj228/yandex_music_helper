from pathlib import Path
from typing import List

import yt_dlp
from youtube_search import YoutubeSearch

YOUTUBE_VIDEO_PREFIX = "https://youtube.ru"


def get_mp3_from_video(song_list: List[str], output_path: str) -> int:
    """
    Download mp3 files from a list of songs by searching for their audio on YouTube.
    Parameters:
        song_list (List[str]): A list of songs to search for on YouTube.
        output_path (str): The directory where the downloaded mp3 files will be saved.
    Returns:
        None
    """
    downloaded_count = 0
    for song in song_list:
        search_query = f"{song} audio lyrics video"
        youtube_videos = YoutubeSearch(search_query, max_results=3).to_dict()
        found_audio = None
        for video in youtube_videos:
            if "audio" in video['title'].lower() or "lyrics" in video['title'].lower():
                found_audio = video
                break
        result = youtube_videos[0] if found_audio is None else found_audio
        url = YOUTUBE_VIDEO_PREFIX + result['url_suffix']
        download_path = Path(output_path, song)
        ydl_opts = {
            'outtmpl': str(download_path),
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except Exception as e:
                print(e)

            if Path(f"{download_path}.mp3").exists():
                downloaded_count += 1
    return downloaded_count
