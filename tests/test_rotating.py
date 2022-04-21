import logging
from datetime import datetime
from pathlib import Path

import pytest

import erap.rotating


class TestFolderRotator:

    def test_build_new_download_dir_path_with_prefix(self, mocker):

        today_mock = mocker.Mock()
        today_mock.strftime.return_value = 'today'
        datetime_mock = mocker.Mock()
        datetime_mock.today.return_value = today_mock
        mocker.patch('erap.rotating.datetime', new=datetime_mock)

        class_mock = mocker.Mock
        class_mock.base_dir = Path('foo')

        test_dir = erap.rotating.FolderRotator._build_new_download_dir_path(class_mock, 'bar_', 'fakeformat')

        assert test_dir == Path('foo', 'bar_today')

    def test_build_new_download_dir_path_no_prefix(self, mocker):

        today_mock = mocker.Mock()
        today_mock.strftime.return_value = 'today'
        datetime_mock = mocker.Mock()
        datetime_mock.today.return_value = today_mock
        mocker.patch('erap.rotating.datetime', new=datetime_mock)

        class_mock = mocker.Mock
        class_mock.base_dir = Path('foo')

        test_dir = erap.rotating.FolderRotator._build_new_download_dir_path(class_mock, '', 'fakeformat')

        assert test_dir == Path('foo', 'today')

    def test_make_new_download_dir_returns_path_on_success(self, mocker):
        class_mock = mocker.Mock()
        class_mock.base_dir = Path('foo')
        # class_mock.prefix = ''

        mock_mkdir = mocker.Mock()
        mocker.patch('pathlib.Path.mkdir', new=mock_mkdir)

        download_dir = erap.rotating.FolderRotator._make_new_download_dir(class_mock, Path('foo_path'), False)

        assert download_dir == Path('foo_path')

    def test_make_new_download_dir_raises_error_with_bad_base_dir(self, mocker):
        class_mock = mocker.Mock()
        class_mock.base_dir = Path('foo')
        # class_mock.prefix = ''

        mock_mkdir = mocker.Mock()
        mock_mkdir.side_effect = FileNotFoundError()
        mocker.patch('pathlib.Path.mkdir', new=mock_mkdir)

        with pytest.raises(FileNotFoundError) as execinfo:
            download_dir = erap.rotating.FolderRotator._make_new_download_dir(class_mock, Path('foo_path'), False)

        assert 'Base directory' in str(execinfo)

    def test_make_new_download_dir_raises_other_error(self, mocker):
        class_mock = mocker.Mock()
        class_mock.base_dir = Path('foo')
        # class_mock.prefix = ''

        mock_mkdir = mocker.Mock()
        mock_mkdir.side_effect = RuntimeError()
        mocker.patch('pathlib.Path.mkdir', new=mock_mkdir)

        with pytest.raises(RuntimeError) as execinfo:
            download_dir = erap.rotating.FolderRotator._make_new_download_dir(class_mock, Path('foo_path'), False)

    def test_get_all_but_n_most_recent_folder_paths_defined_pattern(self, mocker):
        base_dir_mock = mocker.Mock()
        base_dir_mock.iterdir.return_value = [
            Path('bar/foo_20210101_010101'),
            Path('bar/foo_20210101_010102'),
            Path('bar/foo_20210101_010103')
        ]
        rotator = erap.rotating.FolderRotator(base_dir_mock)

        folders_to_delete = rotator._get_all_but_n_most_recent_folder_paths(
            prefix='foo_', pattern='[0-9]{8}_[0-9]{6}', max_folder_count=2
        )

        assert folders_to_delete == [Path('bar/foo_20210101_010101')]

    def test_get_all_but_n_most_recent_folder_paths_defined_pattern_sorts_properly(self, mocker):
        base_dir_mock = mocker.Mock()
        base_dir_mock.iterdir.return_value = [
            Path('bar/foo_20210101_010102'),
            Path('bar/foo_20210101_010103'),
            Path('bar/foo_20210101_010101')
        ]
        rotator = erap.rotating.FolderRotator(base_dir_mock)

        folders_to_delete = rotator._get_all_but_n_most_recent_folder_paths(
            prefix='foo_', pattern='[0-9]{8}_[0-9]{6}', max_folder_count=1
        )

        assert folders_to_delete == [Path('bar/foo_20210101_010101'), Path('bar/foo_20210101_010102')]

    def test_get_all_but_n_most_recent_folder_paths_excess_max_folder_count_doesnt_delete_any(self, mocker, caplog):
        caplog.set_level(logging.DEBUG)
        base_dir_mock = mocker.Mock()
        base_dir_mock.iterdir.return_value = [
            Path('bar/foo_20210101:010101'),
            Path('bar/foo_20210101:010102'),
            Path('bar/foo_20210101:010103')
        ]
        rotator = erap.rotating.FolderRotator(base_dir_mock)

        folders_to_delete = rotator._get_all_but_n_most_recent_folder_paths(
            prefix='foo_', pattern='[0-9]{8}:[0-9]{6}', max_folder_count=5
        )

        assert folders_to_delete == []
        assert 'max_folder_count `5` greater than number of existing folders `3`; no folders deleted' in caplog.text

    def test_delete_old_folders_swallows_exception(self, mocker):
        class_mock = mocker.Mock()
        folders_to_delete = ['foo', 'bar']

        rmtree_mock = mocker.Mock()
        rmtree_mock.side_effect = RuntimeError
        mocker.patch('shutil.rmtree', rmtree_mock)

        deleted_folders = erap.rotating.FolderRotator._delete_old_folders(class_mock, folders_to_delete)

        assert deleted_folders == []

    def test_delete_old_folders_returns_folders_deleted(self, mocker):
        class_mock = mocker.Mock()
        folders_to_delete = ['foo', 'bar']

        mocker.patch('shutil.rmtree')

        deleted_folders = erap.rotating.FolderRotator._delete_old_folders(class_mock, folders_to_delete)

        assert deleted_folders == ['foo', 'bar']

    def test_delete_old_folders_continues_after_swallowing_exception(self, mocker):
        class_mock = mocker.Mock()
        folders_to_delete = ['foo', 'bar']

        def side_effect(arg):
            if arg == 'foo':
                raise RuntimeError

        rmtree_mock = mocker.Mock()
        rmtree_mock.side_effect = side_effect
        mocker.patch('shutil.rmtree', rmtree_mock)

        deleted_folders = erap.rotating.FolderRotator._delete_old_folders(class_mock, folders_to_delete)

        assert deleted_folders == ['bar']
