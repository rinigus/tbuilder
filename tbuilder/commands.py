import importlib.resources as pkg_resources
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

import git

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
            config = Config()

            with pkg_resources.path("tbuilder.scripts", "build") as sp:
                shutil.copy(sp, td)

            # drop all RPMS in the sourcedir
            rpmsdir = spec.srcdir / "RPMS"
            if rpmsdir.exists():
                shutil.rmtree(rpmsdir)

            # deal with repos
            cmd = "/dependencies/build -r file:///extra_repo".split()
            for r in self._repos:
                cmd.extend(["-r", r])

            # add vendor if needed
            if config.vendor:
                cmd.extend(["-v", config.vendor])

            # handle shallow builds
            if config.shallow_clones:
                repo = git.Repo(spec.srcdir)
                remote_url = next(repo.remote("origin").urls)
                commit_id = repo.head.commit.hexsha
                cmd.extend(["-d", f"{remote_url}:{commit_id}"])

            specname = spec.spec_resolved_fname.name
            cmd.extend(["-s", specname])

            isok = self._run_docker(
                cmd,
                [
                    f"{spec.srcdir}:/source",
                    f"{td}:/dependencies",
                    f"./{project_paths.rpmdir}:/extra_repo",
                ],
                log_name=project_paths.logdir / f"{spec.name}.log",
            )

            if not isok:
                print("\nError while building package\n")
                sys.exit(-1)

            rpms_in_system = [r.strip() for r in open(td / "rpmlist")]

            # move RPMs
            rpms = []
            for rpm in rpmsdir.glob("*.rpm"):
                rpms.append(shutil.move(rpm, project_paths.rpmdir))

            # cleanup
            shutil.rmtree(rpmsdir)

            return rpms, rpms_in_system

    @property
    def _docker_name(self) -> str:
        return f"ghcr.io/sailfishos-open/docker-sailfishos-builder-{self.arch}:{self.version}"

    @property
    def _repos(self) -> List[str]:
        config = Config()
        res = []
        for r in config.repositories:
            res.append(r.replace("@ARCH@", self.arch).replace("@VERSION@", self.version))
        return res

    def _run_docker(self, command: List[str], volumes: List[str], log_name=None) -> bool:
        args = "podman run --rm -it".split()
        for v in volumes:
            args.extend(["-v", v])
        args.append(self._docker_name)
        args.extend(command)
        print(" ".join(args))

        project_paths = ProjectPaths()
        with open(project_paths.current_log, "w") as log_file:
            process = subprocess.Popen(args, stdout=log_file, stderr=subprocess.STDOUT)
            r = process.wait()

        if log_name is not None:
            print(f"Log: {log_name}")
            shutil.copy(project_paths.current_log, log_name)

        print()
        return r == 0
