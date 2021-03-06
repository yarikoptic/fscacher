from hashlib import sha256
import os
from pathlib import Path
import random
import shutil
from time import time
from uuid import uuid4
from morecontext import envset
from fscacher import PersistentCache


class TimeFile:
    FILE_SIZE = 1024
    param_names = ["n", "control"]
    params = ([10, 100, 10000], ["", "ignore"])

    def setup_cache(self):
        with open("foo.dat", "wb") as fp:
            fp.write(bytes(random.choices(range(256), k=self.FILE_SIZE)))

    def setup(self, n, control):
        with envset("FSCACHER_CACHE", control):
            self.cache = PersistentCache(name=str(uuid4()))

    def time_file(self, n, control):
        @self.cache.memoize_path
        def hashfile(path):
            with open(path, "rb") as fp:
                return sha256(fp.read()).hexdigest()

        for _ in range(n):
            hashfile("foo.dat")

    def teardown(self, n, control):
        self.cache.clear()


class TimeDirectoryFlat:
    LAYOUT = (100,)

    param_names = ["n", "control", "tmpdir"]
    params = (
        [10, 100, 1000],
        ["", "ignore"],
        os.environ.get("FSCACHER_BENCH_TMPDIRS", ".").split(":"),
    )

    def setup(self, n, control, tmpdir):
        cache_id = str(uuid4())
        with envset("FSCACHER_CACHE", control):
            self.cache = PersistentCache(name=cache_id)
        self.dir = Path(tmpdir, cache_id)
        self.dir.mkdir()
        create_tree(self.dir, self.LAYOUT)

    def time_directory(self, n, control, tmpdir):
        @self.cache.memoize_path
        def dirsize(path):
            total_size = 0
            with os.scandir(path) as entries:
                for e in entries:
                    if e.is_dir():
                        total_size += dirsize(e.path)
                    else:
                        total_size += e.stat().st_size
            return total_size

        for _ in range(n):
            dirsize(str(self.dir))

    def teardown(self, *args, **kwargs):
        self.cache.clear()
        shutil.rmtree(self.dir)


class TimeDirectoryDeep(TimeDirectoryFlat):
    LAYOUT = (3, 3, 3, 3)


def create_tree(root, layout):
    base_time = time()
    dirs = [Path(root)]
    for i, width in enumerate(layout):
        if i < len(layout) - 1:
            dirs2 = []
            for d in dirs:
                for x in range(width):
                    d2 = d / f"d{x}"
                    d2.mkdir()
                    dirs2.append(d2)
            dirs = dirs2
        else:
            for j, d in enumerate(dirs):
                for x in range(width):
                    f = d / f"f{x}.dat"
                    f.write_bytes(b"\0" * random.randint(1, 1024))
                    t = base_time - x - j * width
                    os.utime(f, (t, t))
