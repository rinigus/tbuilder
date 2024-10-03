import argparse
import collections
import copy
import datetime
import glob
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .commands import Commands
from .config import Config
from .project import Project
from .project_paths import ProjectPaths


##########################################################
## main
def main():

    parser = argparse.ArgumentParser(description="Generate project build files")

    parser.add_argument("project_directory", default=".", help="Directory containing project files")

    args = parser.parse_args()

    project = Path(args.project_directory)
    if not project.is_dir():
        print("Project directory does not exist or is not a directory:", project)
        sys.exit(-1)

    # change to project dir
    os.chdir(project)

    # load config
    config = Config()

    project_paths = ProjectPaths()
    project_paths.init(".", config.rpmrootdir)
    commands = Commands()

    # check if targets can be set
    for target in config.targets:
        commands.set_target(target)

    # main loop
    for target in config.targets:
        print("\n\nStarting builds for", target, "\n")

        # initialize for each target
        project_paths.set_target(target)
        commands.set_target(target)

        # project depends on target through SPEC states
        project = Project()

        # start build loop
        Done = False
        Error = False
        while not Done and not Error:
            # check whether we have to remove untracked RPMs
            tracked_rpms = []
            for s in project.specs:
                tracked_rpms.extend([str(r) for r in s.rpms])
            for f in project_paths.rpmdir.glob("*.rpm"):
                if str(f) not in tracked_rpms:
                    print(f"Removing old or unknown RPM: {f}")
                    f.unlink()
            print()

            # recreate repo
            commands.createrepo()

            # update list of SPECs that require building
            specs = project.needs_building()

            # check if there is any spec to build
            if not specs:
                Done = True
                continue

            # find specs that we can build at this stage
            to_build = commands.can_build(specs)

            if not to_build:
                print("Cannot build any of the remaining SPEC files due to missing requirements\n")
                for s in specs:
                    print(f"Cannot build: {s}")
                Error = True
                continue

            print("### Can build the following SPECs ###")
            for spec in to_build:
                print(spec)
            print()

            for s in to_build:
                rpms, rpms_in_system = commands.build(s)
                if not rpms:
                    print(f"Failed to build {s}")
                    Error = True
                    break

                # if parallelized, this section has to be revised to ensure
                # that dependencies are handled correctly
                s.set_rpms(rpms)                
                project.update_dependencies(s, rpms_in_system)
                print(f"{s} build successful")

    if Error:
        print()
        print("Error while building packages")
        print()
        sys.exit(7)

    print("\nAll builds finished\n")
