import os




class Version:

    def __init__(self, version: str):
        version = tuple([int(v) for v in version.split('.')])

        self.major = version[0]
        self.minor = version[1]
        self.patch = version[2]

    def int(self):
        return int.from_bytes(bytes(self.tuple()), byteorder='big')

    def string(self):
        return f'{self.major}.{self.minor}.{self.patch}'

    def tuple(self):
        return [self.major, self.minor, self.patch]

    def path(self):
        from setting.setting import PIP_BIN_DIR
        return os.path.join(PIP_BIN_DIR, f'{self}/platon')

    def next_patch_version(self):
        return Version(f'{self.major}.{self.minor}.{self.patch + 1}')

    def next_minor_version(self):
        return Version(f'{self.major}.{self.minor + 1}.0')

    def next_major_version(self):
        return Version(f'{self.major + 1}.0.0')

    @staticmethod
    def max_version():
        return Version('255.255.255')

    @staticmethod
    def min_version():
        return Version('0.0.0')
