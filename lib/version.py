import os

from setting.setting import PIP_BIN_DIR, CURRENT_VERSION


class Version:

    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    def tuple(self):
        return [self.major, self.minor, self.patch]

    def string(self):
        return f'{self.major}.{self.minor}.{self.patch}'

    def int(self):
        return int.from_bytes(bytes(self.tuple()), byteorder='big')

    @staticmethod
    def from_tuple(version: tuple):
        return Version(version[0], version[1], version[2])

    @staticmethod
    def from_int(version: int):
        return Version.from_tuple(tuple(int(version).to_bytes(length=3, byteorder='big')))

    @staticmethod
    def from_string(version: str):
        return Version.from_tuple(tuple([int(v) for v in version.split('.')]))

    def path(self):
        return os.path.join(PIP_BIN_DIR, f'{self.string()}/platon')

    def upgrade(self, major: int = 0, minor: int = 0, patch: int = 0):
        return Version(self.major + major, self.minor + minor, self.patch + patch)


current_version = Version.from_string(CURRENT_VERSION)
next_version = Version(current_version.major, current_version.minor + 1, 0)
next_major_version = Version(current_version.major + 1, 0, 0)
next_patch_version = Version(current_version.major, current_version.minor, current_version.patch + 1)
min_version = Version(0, 0, 0)
max_version = Version(255, 255, 255)


def get_platon(version: Version):
    return version.path()
