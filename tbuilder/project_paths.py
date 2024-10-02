from pathlib import Path


# paths used by tbuilder projects
class ProjectPaths:
    # singleton
    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super(ProjectPaths, cls).__new__(cls)
        return cls._instance

    def init(self, project, rpmroot):
        # called when singleton is initialized
        self.project = Path(project)
        self.rpmroot = rpmroot
        self.target = None

    def set_target(self, target):
        self.target = target
        self._create_dirs()

    @property
    def _builddir_base(self) -> Path:
        return self.project / "build" / self.target

    @property
    def logdir(self) -> Path:
        return self._builddir_base / "log"

    @property
    def rpmdir(self) -> Path:
        return self.project / self.rpmroot / self.target

    @property
    def specdir(self) -> Path:
        return self.project / "spec"

    @property
    def statedir(self) -> Path:
        return self._builddir_base / "state"

    def _create_dirs(self):
        for p in [self.logdir, self.rpmdir, self.statedir]:
            p.mkdir(parents=True, exist_ok=True)
