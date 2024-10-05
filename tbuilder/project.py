from typing import List

import yaml

from .project_paths import ProjectPaths
from .spec import Spec


class Project:
    def __init__(self):
        project_paths = ProjectPaths()

        # load SPEC files
        specs = [Spec(f) for f in sorted(project_paths.specdir.glob("*.spec"))]
        self._specsdict = {str(s.name): s for s in specs}

        # load already detected dependencies
        self._dependencies = dict()
        self._deps_fname = project_paths.statedir / "_tbuilder_project.yaml"
        if self._deps_fname.exists():
            with open(self._deps_fname, "r") as f:
                self._dependencies = yaml.safe_load(f)
                if self._dependencies is None:
                    self._dependencies = dict()

    @property
    def specs(self) -> List[Spec]:
        return self._specsdict.values()

    def needs_building(self) -> List[Spec]:
        res = []
        for s in self.specs:
            rpms = []
            force_rebuild = False
            for deps in self._dependencies.get(s.name, []):
                if deps not in self._specsdict:
                    force_rebuild = True
                else:
                    for r in self._specsdict[deps].rpms:
                        rpms.append(r)
            if force_rebuild or not s.is_ready(rpms):
                res.append(s)
        return res

    def update_dependencies(self, sdep: Spec, rpms: List[str]):
        # s - SPEC that was built
        # rpms - RPMs used to build that SPEC
        dname = sdep.name
        deps = set()
        r2s = self._rpm_to_spec()
        for r in rpms:
            s = r2s.get(r, None)
            if s is not None:
                deps.add(s)
                print(f"SPEC dependency: {dname} depends on {s}")

        self._dependencies[dname] = sorted(list(deps))

        with open(self._deps_fname, "w") as f:
            yaml.dump(self._dependencies, f)

    def _rpm_to_spec(self):
        r2s = dict()
        for s in self.specs:
            sname = str(s.name)
            for r in s.rpms:
                rname = r.stem
                r2s[rname] = sname
        return r2s
