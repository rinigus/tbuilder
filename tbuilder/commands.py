import importlib.resources as pkg_resources
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from tbuilder import project_paths

from .config import Config
from .project_paths import ProjectPaths
from .spec import Spec


# commands abstraction
class Commands:
    # singleton
    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Commands, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        # check createrepo is with _c suffix
        if shutil.which("createrepo_c") is not None:
            self._createrepo = "createrepo_c"
        elif shutil.which("createrepo") is not None:
            self._createrepo = "createrepo"
        else:
            print("Cannot find createrepo")
            sys.exit(-1)

    def set_target(self, target):
        self.target = target
        self.version, self.arch = target.split("-")

    def createrepo(self):
        project_paths = ProjectPaths()
        repodir = project_paths.rpmdir / "repodata"
        if repodir.exists():
            shutil.rmtree(repodir)
        cmd = "createrepo_c /extra_repo".split()
        isok = self._run_docker(
            cmd,
            [
                f"./{project_paths.rpmdir}:/extra_repo",
            ],
        )

        if not isok:
            print("\nError while creating repository\n")
            sys.exit(-2)

    def can_build(self, specs: List[Spec]) -> List[Spec]:
        res = []
        with tempfile.TemporaryDirectory() as tmpdirname:
            td = Path(tmpdirname)
            project_paths = ProjectPaths()

            ts = td / "spec"
            ts.mkdir()
            for spec in specs:
                shutil.copy(spec.spec_fname, ts)
            with pkg_resources.path("tbuilder.scripts", "check-can-build") as sp:
                shutil.copy(sp, td)

            cmd = "/source/check-can-build -o /source/can-build.txt -r file:///extra_repo".split()
            for r in self._repos:
                cmd.extend(["-r", r])

            for spec in specs:
                cmd.append(f"/source/{spec.spec_fname}")

            isok = self._run_docker(
                cmd,
                [
                    f"{tmpdirname}:/source",
                    f"./{project_paths.rpmdir}:/extra_repo",
                ],
            )

            if isok:
                with open(td / "can-build.txt", "r") as f:
                    for line in f:
                        sn = Path(line.strip()).name
                        for spec in specs:
                            if sn == spec.spec_fname.name:
                                res.append(spec)
            else:
                print("\nError while checking package\n")
                sys.exit(-1)

        return res

    def build(self, spec: Spec) -> List[str]:
        with tempfile.TemporaryDirectory() as tmpdirname:
            td = Path(tmpdirname)
            project_paths = ProjectPaths()

            with pkg_resources.path("tbuilder.scripts", "build") as sp:
                shutil.copy(sp, td)

            # drop all RPMS in the sourcedir
            rpmsdir = spec.srcdir / "RPMS"
            if rpmsdir.exists():
                shutil.rmtree(rpmsdir)

            cmd = "/dependencies/build -r file:///extra_repo".split()
            for r in self._repos:
                cmd.extend(["-r", r])

            specname = spec.spec_resolved_fname.name
            cmd.extend(["-s", specname])

            isok = self._run_docker(
                cmd,
                [
                    f"{spec.srcdir}:/source",
                    f"{td}:/dependencies",
                    f"./{project_paths.rpmdir}:/extra_repo",
                ],
            )

            if not isok:
                print("\nError while building package\n")
                sys.exit(-1)

            rpms = []
            for rpm in rpmsdir.glob("*.rpm"):
                rpms.append(shutil.copy(rpm, project_paths.rpmdir))

            rpms_in_system = [l.strip() for l in open(td / "rpmlist")]

            return rpms, rpms_in_system

    @property
    def _docker_name(self) -> str:
        return f"docker-sailfishos-builder-{self.arch}:{self.version}"

    @property
    def _repos(self) -> List[str]:
        config = Config()
        res = []
        for r in config.repositories:
            res.append(r.replace("@ARCH@", self.arch).replace("@VERSION@", self.version))
        return res

    def _run_docker(self, command: List[str], volumes: List[str]) -> bool:
        args = "podman run --rm -it".split()
        for v in volumes:
            args.extend(["-v", v])
        args.append(self._docker_name)
        args.extend(command)
        print(" ".join(args))
        return subprocess.run(args).returncode == 0
