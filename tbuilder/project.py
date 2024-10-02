from typing import List

import yaml

from .project_paths import ProjectPaths
from .spec import Spec


class Project:
    def __init__(self):
        project_paths = ProjectPaths()

        # load SPEC files
        self.specsdict = {str(f): Spec(f) for f in sorted(project_paths.specdir.glob("*.spec"))}

        # load already detected dependencies
        self.dependencies = dict()
        self.deps_fname = project_paths.statedir / "_tbuilder_project.yaml"
        if self.deps_fname.exists():
            with open(self.deps_fname, "r") as f:
                self.dependencies = yaml.safe_load(f)
                if self.dependencies is None:
                    self.dependencies = dict()

    @property
    def specs(self) -> List[Spec]:
        return self.specsdict.values()

    def needs_building(self) -> List[Spec]:
        res = []
        for s in self.specs:
            rpms = []
            force_rebuild = False
            for deps in self.dependencies.get(s.name, []):
                if deps not in self.specsdict:
                    force_rebuild = True
                else:
                    for r in self.specsdict[deps].rpms:
                        rpms.append(r)
            if force_rebuild or not s.is_ready(rpms):
                res.append(s)
        return res

    def update_dependencies(self, sdep: Spec, rpms: List[str]):
        # s - SPEC that was built
        # rpms - RPMs used to build that SPEC
        dname = sdep.name
        deps = []
        r2s = self._rpm_to_spec()
        for r in rpms:
            s = r2s.get(r + ".rpm", None)
            if s is not None:
                deps.append(s)
                print(f"SPEC dependency: {dname} depends on {s}")

        self.dependencies[dname] = deps

        with open(self.deps_fname, "w") as f:
            yaml.dump(self.dependencies, f)

    def _rpm_to_spec(self):
        r2s = dict()
        for s in self.specs:
            sname = str(s.spec_fname)
            for r in s.rpms:
                rname = r.name
                r2s[rname] = sname
        return r2s
