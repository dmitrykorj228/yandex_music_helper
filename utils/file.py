from pathlib import Path
from typing import List
from zipfile import ZIP_DEFLATED, ZipFile

MAX_SIZE = 50000000
COMPRESS_LEVEL = 3


def zip_folder(files_path: Path, zip_username: str):
    size = 0
    files = []
    part_index = 1

    def zip_files(files_list):
        to_zip(Path(files_path.parent, f"zip_{zip_username}", f"part_{part_index}.zip"), files_list)

    for file in files_path.rglob('*'):
        size += file.stat().st_size
        files.append(file)
        if size >= MAX_SIZE:
            files.remove(file)
            zip_files(files)
            files.append(file)
            size = 0
            files = []
            part_index += 1
    if files:
        zip_files(files)
    return Path(files_path.parent, f"zip_{zip_username}")


def to_zip(result_zip_file_path: Path, files_to_zip: List[Path]):
    result_zip_file_path.parent.mkdir(exist_ok=True)
    with ZipFile(result_zip_file_path, "w", compression=ZIP_DEFLATED,
                 compresslevel=COMPRESS_LEVEL) as zip_file:
        for file in files_to_zip:
            zip_file.write(file, file.name)
