#!/usr/bin/env python3
import sys
import time
from pathlib import Path

from ledger_parse import CODE_HEADER, CODE_HEADER_PREFIX, LANGUAGE_HEADER_PREFIX
from storage.backups import Backups
from storage.local_folder import LocalFolder

EXAMPLE_PREFIX = "  - "
LANGUAGE_BY_EXTENSION = {
    "php": "PHP", "py": "Python", "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript", "jsx": "JavaScript",
    "mjs": "JavaScript", "sh": "Shell", "bash": "Shell", "zsh": "Shell", "go": "Go",
}


def migrate_directory(directory):
    folder = LocalFolder(directory)
    text = folder.get("ledger.md")
    if not text:
        return
    migrated = migrate_text(text)
    if migrated == text:
        return
    Backups(folder, time.time).keep("ledger.md")
    folder.put("ledger.md", migrated)


def migrate_text(text):
    migrated = []
    awaiting_language = False
    for line in text.split("\n"):
        if line.startswith(EXAMPLE_PREFIX):
            awaiting_language = True
        elif line.startswith(LANGUAGE_HEADER_PREFIX):
            awaiting_language = False
        elif awaiting_language and line.startswith(CODE_HEADER_PREFIX):
            awaiting_language = False
            migrated += language_line_for(line)
        migrated.append(line)
    return "\n".join(migrated)


def language_line_for(code_line):
    language = language_of_code_header(code_line[len(CODE_HEADER_PREFIX):])
    line_ending = "\r" if code_line.endswith("\r") else ""
    return [f"{LANGUAGE_HEADER_PREFIX}{language}{line_ending}"] if language else []


def language_of_code_header(header):
    found = CODE_HEADER.match(header.strip())
    path = found["path"] if found else ""
    extension = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return LANGUAGE_BY_EXTENSION.get(extension, "")


def main():
    migrate_directory(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
