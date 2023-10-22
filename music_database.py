import sqlite3
from sqlite3 import Cursor
from typing import Tuple, List, Dict


class MusicDatabase:
    def __init__(self, config):
        self.config = config
        self.table_owner_name = self.config['owner_name']
        self.connection = sqlite3.connect(f"unavailable_songs[{self.table_owner_name}].db")
        self.__prepare_table()

    @property
    def cursor(self) -> Cursor:
        return self.connection.cursor()

    @property
    def table_name(self) -> str:
        return f"unavailable_music_{self.table_owner_name}"

    def __prepare_table(self) -> None:
        is_table_exists = bool(
            self.cursor.execute(
                f"SELECT * FROM sqlite_master WHERE name = '{self.table_name}' AND type='table'").fetchone())
        if not is_table_exists:
            self.cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name}(title, track_id, album_id, telegram_message_send)")

    def insert_to_table(self, music_data: List[Tuple[str, int, int, bool]]) -> None:
        self.cursor.executemany(f"INSERT INTO {self.table_name} VALUES(?, ?, ?, ?)", music_data)
        self.connection.commit()

    def get_track_by_album(self, album_id) -> List[Dict[str, int]]:
        response = self.cursor.execute(f"SELECT track_id FROM {self.table_name} WHERE album_id={album_id}").fetchall()
        return [track_id for track_id, *args in response]
