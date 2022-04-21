"""Create a new directory in base_dir and delete old directories as needed, logging as we go.
"""

import logging
import re
import shutil
from datetime import datetime

module_logger = logging.getLogger(__name__)


class FolderRotator:  # pylint: disable=too-few-public-methods
    """Create a new directory in base_dir and delete old directories as needed, logging as we go.
    """

    def __init__(self, base_dir) -> None:
        self.base_dir = base_dir
        self._class_logger = logging.getLogger(__name__).getChild(self.__class__.__name__)

    #: Make dir Methods
    def _build_new_download_dir_path(self, prefix, date_format):
        today = datetime.today()
        download_dir = self.base_dir / f'{prefix}{today.strftime(date_format)}'
        return download_dir

    def _make_new_download_dir(self, download_dir_path, exist_ok):
        self._class_logger.debug(f'Attempting to create new directory `{download_dir_path}`')
        try:
            download_dir_path.mkdir(exist_ok=exist_ok)
        except FileNotFoundError as error:
            raise FileNotFoundError(f'Base directory `{self.base_dir}` does not exist.') from error
        else:
            self._class_logger.debug(f'Successfully created `{download_dir_path}`')
            return download_dir_path

    #: Rotator Methods
    def _get_all_but_n_most_recent_folder_paths(self, prefix, pattern, max_folder_count):
        pattern = f'{prefix}{pattern}'
        self._class_logger.debug(f'Folder regex pattern: {pattern}')
        folder_paths = [path for path in self.base_dir.iterdir() if re.match(pattern, path.stem)]
        if max_folder_count > len(folder_paths):
            self._class_logger.debug(
                f'max_folder_count `{max_folder_count}` greater than number of existing folders `{len(folder_paths)}`; '
                'no folders deleted'
            )
            max_folder_count = 0
        return sorted(folder_paths)[:-max_folder_count]

    def _delete_old_folders(self, folder_paths_to_delete):
        deleted_folders = []
        for folder in folder_paths_to_delete:
            try:
                self._class_logger.debug(f'Attempting to delete `{folder}`')
                shutil.rmtree(folder)
            except Exception:
                self._class_logger.warning(f'Could not delete `{folder}; delete manually`')
            else:
                self._class_logger.debug(f'Successfully deleted `{folder}`')
                deleted_folders.append(folder)

        return deleted_folders

    def get_rotated_directory(
        self,
        prefix='',
        date_format='%Y%m%d_%H%M%S',
        exist_ok=False,
        pattern='[0-9]{8}_[0-9]{6}',
        max_folder_count=10
    ):  # pylint: disable=too-many-arguments
        """Get a new directory using the info provided, rotating according to max_folder_count.

        Logs to logging.getLogger(__name__).getChild(self.__class__.__name__).
        DEBUG:
            Directory creation attempt/success
            Individual directory deletion attempts/successes
        INFO:
            Directories deleted as part of rotation

        Raises FileNotFoundError if base_dir does not exist. If exist_ok is False (default), it will raise
        a FileExistsError if the desired new folder already exists. Silently swallows any errors when deleting
        folders and moves on to the next folder to be deleted.

        Args:
            prefix (str, optional): Folder prefix for date. Any spacers(_, -, etc) must be provided in the prefix.
                Defaults to ''.
            date_format (str, optional): Date format argument to strftime(). Defaults to '%Y%m%d_%H%M%S'
                (YYYYMMDD_hhmmss).
            exist_ok (bool, optional): If exist_ok is False, a FileExistsError is raised if the new download directory
                already exists. Defaults to False.
            pattern (str, optional): Regex date matching pattern to determine folders eligible for rotation deletion.
                Defaults to '[0-9]{8}_[0-9]{6}' (matches default date_format).
            max_folder_count (int, optional): Number of folders to keep, not including the folder created.
                Defaults to 10.

        Returns:
            Path: Path object to newly created folder
        """
        folder_paths_to_delete = self._get_all_but_n_most_recent_folder_paths(prefix, pattern, max_folder_count)
        deleted_folders = self._delete_old_folders(folder_paths_to_delete)
        self._class_logger.info(
            f'Deleted {len(deleted_folders)} folder(s) for rotation: {[str(folder) for folder in deleted_folders]}'
        )
        #: Do folder creation after deletion so that we know our new folder will never be deleted beforehand
        download_dir = self._build_new_download_dir_path(prefix, date_format)
        created_dir_path = self._make_new_download_dir(download_dir, exist_ok)

        return created_dir_path
