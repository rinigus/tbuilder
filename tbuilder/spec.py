from pathlib import Path

import yaml

from .project_paths import ProjectPaths


class Spec:
    # handle SPEC
    def __init__(self, s: Path):
        self.spec_fname = s
        self.name = s.stem

        project_paths = ProjectPaths()
        self.state_fname = project_paths.statedir / (self.name + ".yaml")

        self.rpms = []
        if self.state_fname.exists():
            with open(self.state_fname, "r") as f:
                self.rpms = yaml.safe_load(f)
                if self.rpms is None:
                    self.rpms = []
                else:
                    self.rpms = [Path(r) for r in self.rpms]

        linkdir = self.spec_fname.parent / self.spec_fname.readlink().parent
        self.spec_resolved_fname = self.spec_fname.resolve()
        self.specdir = linkdir.resolve()
        self.srcdir = linkdir.parent.resolve()

    def __str__(self):
        return str(self.name)

    def set_rpms(self, rpms):
        self.rpms = [Path(r) for r in rpms]
        with open(self.state_fname, "w") as f:
            yaml.dump([f"{r}" for r in self.rpms], f)

    @property
    def mtime(self):
        mtime = 0
        for f in self.specdir.glob("*"):
            mtime = max(mtime, f.stat().st_mtime)
        for f in self.srcdir.glob("*"):
            mtime = max(mtime, f.stat().st_mtime)
        return mtime

    def is_ready(self, extra_dependencies) -> bool:
        if not self.rpms:
            return False

        for f in self.rpms:
            if not f.exists():
                print(f"{self.name}: Missing expected RPM {f} - asking for rebuild\n")
                self.set_rpms([])
                return False

        # check modified time
        mtime = self.mtime

        # mtime of dependencies
        for f in extra_dependencies:
            mtime = max(mtime, Path(f).stat().st_mtime)

        for f in self.rpms:
            if mtime > Path(f).stat().st_mtime:
                return False

        # source files look to be older than RPMs, all is ready
        return True
