from __future__ import annotations

from .local_folder import LocalFolder
from .push_lock import Clock

BACKUP_FOLDER = "backups"
BACKUPS_KEPT_PER_FILE = 10


class Backups:
    def __init__(self, data: LocalFolder, clock: Clock) -> None:
        self.data = data
        self.clock = clock
        self.folder = LocalFolder(data.directory / BACKUP_FOLDER)

    def keep(self, name: str) -> None:
        text = self.data.get(name)
        if not text or text == self.newest_text(name):
            return
        self.folder.put(f"{name}.{int(self.clock())}", text)
        self.discard_all_but_newest(name)

    def newest_text(self, name: str) -> str | None:
        existing = self.existing(name)
        return self.folder.get(existing[-1]) if existing else None

    def discard_all_but_newest(self, name: str) -> None:
        for old in self.existing(name)[:-BACKUPS_KEPT_PER_FILE]:
            (self.folder.directory / old).unlink(missing_ok=True)

    def existing(self, name: str) -> list[str]:
        if not self.folder.directory.exists():
            return []
        candidates = [path.name for path in self.folder.directory.glob(f"{name}.*")]
        stamped = [candidate for candidate in candidates if candidate[len(name) + 1 :].isdigit()]
        return sorted(stamped, key=lambda backup: int(backup[len(name) + 1 :]))
