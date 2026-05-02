import pathlib

import pytest

from repositories import DbStorage


@pytest.fixture
def temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path


@pytest.fixture
def temp_db_path(temp_dir: pathlib.Path) -> pathlib.Path:
    return temp_dir / "test_storage.sqlite"


@pytest.fixture
def db_storage(temp_db_path: pathlib.Path):
    db = DbStorage(file_path=str(temp_db_path))
    try:
        yield db
    finally:
        db.close()
