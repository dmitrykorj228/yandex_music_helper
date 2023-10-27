import sqlite3
from sqlite3 import Cursor
from typing import Tuple, List, Dict


class MusicDatabase:
    def __init__(self, config):
        """
        Initializes an instance of the class.

        :param config: The configuration object for the database.
        """
        self.config = config
        self.table_owner_name = self.config['playlist_owner_name'].replace(".", "")
        self.connection = sqlite3.connect(f"unavailable_songs[{self.table_owner_name}].db")
        self.__prepare_table()

    @property
    def cursor(self) -> Cursor:
        """
        Returns the cursor object associated with the database connection.

        :rtype: Cursor
        """
        return self.connection.cursor()

    @property
    def table_name(self) -> str:
        """
        Returns the table name for the unavailable music based on the table owner name.

        :return: The table name as a string.
        :rtype: str
        """
        return f"unavailable_music_{self.table_owner_name}"

    def __prepare_table(self) -> None:
        """
        Creates the table if it doesn't exist in the database.

        :return: None
        """
        is_table_exists = bool(
            self.cursor.execute(
                f"SELECT * FROM sqlite_master WHERE name = '{self.table_name}' AND type='table'").fetchone())
        if not is_table_exists:
            self.cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name}(title, track_id, album_id, telegram_message_send)")

    def insert_to_table(self, music_data: List[Tuple[str, int, int, bool]]) -> None:
        """
        Inserts multiple rows of music data into a table.
        Args:
            music_data (List[Tuple[str, int, int, bool]]): A list of tuples representing the music data
                to be inserted. Each tuple contains the following information:
                - Element 1: The name of the song (str)
                - Element 2: The track id from yandex database (int)
                - Element 3: The album id from yandex database (int)
                - Element 4: A boolean value indicating if telegram message was sent (bool)
        Returns:
            None: This function does not return anything.
        """
        self.cursor.executemany(f"INSERT INTO {self.table_name} VALUES(?, ?, ?, ?)", music_data)
        self.connection.commit()

    def get_track_by_album(self, album_id: int) -> List[Dict[str, int]]:
        """
        Get the tracks associated with a given album ID.
        Args:
            album_id (int): The ID of the album.
        Returns:
            List[Dict[str, int]]: A list of dictionaries representing the track IDs associated with the album.
        """
        response = self.cursor.execute(f"SELECT track_id FROM {self.table_name} WHERE album_id={album_id}").fetchall()
        return [track_id for track_id, *args in response]
