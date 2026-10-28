from __future__ import annotations

from functools import cache

from forja.settings import get_settings
from forja.storage.files import LocalFileStorage


@cache
def get_storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().data_dir / "files")
