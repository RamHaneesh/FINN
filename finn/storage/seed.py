"""Bootstrap an empty deployment volume from the repository's pre-warmed cache."""
from pathlib import Path
from contextlib import closing
import shutil
import sqlite3

from finn.config import ROOT


def bootstrap_seed(root: Path, source: Path = ROOT / "data") -> bool:
    root, source = Path(root), Path(source)
    database, seed = root / "finn.sqlite3", source / "finn.sqlite3"
    if database.resolve() == seed.resolve() or not seed.is_file():
        return False
    # Never replace an existing volume, including databases created by an earlier run.
    if database.exists() and database.stat().st_size:
        return False
    root.mkdir(parents=True, exist_ok=True)
    # SQLite backup includes committed WAL transactions; copying a live DB file does not.
    with closing(sqlite3.connect(seed.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(database)) as dst:
            src.backup(dst)
    for directory in ("documents", "research"):
        if (source / directory).is_dir():
            shutil.copytree(source / directory, root / directory, dirs_exist_ok=True)
    return True
