import sys

import yaml


class Config:
    # singleton
    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)

        self.project_name = config.get("project", "")
        self.targets = config.get("targets", [])
        self.rpmrootdir = config.get("rpms", "")
        self.repositories = config.get("repositories", [])
        self.macros = config.get("macros", [])
        self.project_options = config.get("options", [])
        self.buildoptions = config.get("buildoptions", "")
        self.shadow_builds = config.get("shadow_builds", [])
        self.install_extra_packages = config.get("install", [])
        self.skip_rpms = config.get("skip_rpms", [])

        self.specdir = "spec"
        self.repodir = "repodata"

        # check for required parameters
        if len(self.project_name) < 1:
            print("No project name specified in the project config.yaml")
            sys.exit(-1)
        if len(self.targets) < 1:
            print("No targets specified in the project config.yaml")
            sys.exit(-1)
        if len(self.rpmrootdir) < 1:
            print("No RPMS directory specified in the project config.yaml")
            sys.exit(-1)
