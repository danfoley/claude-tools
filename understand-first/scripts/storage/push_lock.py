import os

DEFAULT_LEASE_SECONDS = 600


class PushLock:
    def __init__(self, path, clock, lease_seconds=DEFAULT_LEASE_SECONDS):
        self.path = path
        self.clock = clock
        self.lease_seconds = lease_seconds

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            if self.create_with_expiry():
                return True
            if not self.has_expired():
                return False
            self.path.unlink(missing_ok=True)

    def release(self):
        self.path.unlink(missing_ok=True)

    def create_with_expiry(self):
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w") as file:
            file.write(str(self.clock() + self.lease_seconds))
        return True

    def has_expired(self):
        try:
            return float(self.path.read_text()) <= self.clock()
        except FileNotFoundError:
            return True
        except ValueError:
            return True
