import hashlib
import json
import os


def hash_of(text):
    return hashlib.sha256(text.encode()).hexdigest()


class SyncState:
    def __init__(self, path):
        self.path = path
        self.recorded = self.load()

    def hash_of_last_sync(self, name):
        return self.recorded["hashes"].get(name)

    def record_hash(self, name, text):
        self.recorded["hashes"][name] = hash_of(text)
        self.save()

    def events_cursor(self):
        return self.recorded["events_cursor"]

    def record_events_cursor(self, cursor):
        self.recorded["events_cursor"] = cursor
        self.save()

    def value(self, key):
        return self.recorded.get(key)

    def record_value(self, key, value):
        self.recorded[key] = value
        self.save()

    def load(self):
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, ValueError):
            return {"hashes": {}, "events_cursor": 0}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(self.recorded))
        os.replace(temporary, self.path)
