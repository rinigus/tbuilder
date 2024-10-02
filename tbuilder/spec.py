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

        # self.keeprelease = keeprelease
        # # determine src and spec abs path
        # ## handle case where we can have relative symbolic links
        # ## as well as rpm within the source dir which is symlink.
        # ## for these cases, resolve symlink late
        # slink = os.readlink(s)
        # rpmdir, specfname_rel = os.path.split(slink)
        # self.srcpath, rpmpath_rel = os.path.split(rpmdir)
        # self.specfname_rel = os.path.join(rpmpath_rel, specfname_rel)
        # # handle relative path
        # if not os.path.isabs(self.srcpath):
        #     self.srcpath = os.path.abspath(os.path.join(os.path.dirname(s), self.srcpath))
        # # fill data using queries
        # self.name = query(
        #     tool,
        #     "rpmspec",
        #     self.specfname_rel,
        #     "--queryformat=%{NAME} ",
        #     macros,
        #     cwd=self.srcpath,
        # )[0][0]
        # self.requires, self.requires_full = query(
        #     tool,
        #     "rpmspec",
        #     self.specfname_rel,
        #     "--buildrequires",
        #     macros,
        #     cwd=self.srcpath,
        # )
        # self.requires = set(self.requires)
        # self.missing = set()
        # print(self.name)

    # def __str__(self):
    #     return "{name}: {specfname}  / requires: {requires} / missing: {missing}".format(**self.__dict__)

    # def can_build(self, system_provided, local_provided):
    #     self.missing = set()
    #     for r, rsimple in self.requires_full.items():
    #         if not local_provided.provided(r, rsimple) and not system_provided.provided(r, rsimple):
    #             self.missing.add(r)
    #     return len(self.missing) == 0

    # def load_release(self, tool):
    #     rfile = os.path.join(releasedir(tool), os.path.basename(self.specfname))
    #     release = 0
    #     if os.path.exists(rfile):
    #         with open(rfile, "r") as f:
    #             t = f.read()
    #             try:
    #                 release = int(t)
    #             except:
    #                 pass
    #     release += 1
    #     return rfile, release

    # def make_spec(self, local_provided, tool, rpmroot, buildoptions, macros, insource):
    #     req = [rsimple for r, rsimple in self.requires_full.items() if local_provided.provided(r, rsimple)]
    #     make = target_spec(self.specfname, tool) + ": %s %s %s %s " % (
    #         target_targetdir(tool),
    #         target_builddir(tool),
    #         target_rpmdir(rpmroot, tool),
    #         self.specfname,
    #     )
    #     make += " ".join([target_provides(i, tool) for i in req])
    #     make += "\n"
    #     # determine src and spec path
    #     sbase = os.path.basename(self.specfname)
    #     bdir = os.path.join(builddir(tool), sbase)
    #     specpath = os.path.abspath(self.specfname)
    #     rpmpath = os.path.abspath(rpmdir(rpmroot, tool))
    #     # build options for rpmbuild
    #     if len(macros) > 0:
    #         rpmbuild = " " + " ".join(['--define="%s"' % m for m in macros])
    #     else:
    #         rpmbuild = ""
    #     # get release info
    #     if insource and not self.keeprelease:
    #         relfile, release = self.load_release(tool)
    #     else:
    #         relfile, release = None, None
    #     # write build section
    #     make += "\t" + "@echo\n"
    #     make += "\t" + "@echo Building %s for %s\n" % (self.specfname, tool)
    #     make += "\t" + "@echo\n"
    #     if not insource:
    #         make += "\t" + "rm -rf %s\n" % bdir
    #     make += "\t" + "mkdir -p %s\n" % bdir
    #     if insource:
    #         make += "\t" + "rsync -a --delete %s/ %s/\n" % (self.srcpath, bdir)
    #         srcpath = "."
    #         specpath = self.specfname_rel
    #         buildoptions = buildoptions + " -p"
    #     else:
    #         srcpath = self.srcpath

    #     if release is not None:
    #         make += "\t" + '(cd {bdir} && sed -i "s/^Release:.*\\S/&.{release}/" {spec})\n'.format(
    #             bdir=bdir, release=release, spec=specpath
    #         )

    #     if len(req) > 0:
    #         make += (
    #             "\t"
    #             + commands.install_package_cmd(
    #                 tool=tool,
    #                 force=True,
    #                 extra_repo=rpmpath,
    #                 package=" ".join(['"%s"' % r for r in req]),
    #             )
    #             + "\n"
    #         )
    #     make += commands.make_section(
    #         bdir=bdir,
    #         tool=tool,
    #         rpmpath=rpmpath,
    #         specpath=specpath,
    #         buildoptions=buildoptions,
    #         srcpath=srcpath,
    #         rpmbuild=rpmbuild,
    #     )
    #     make += "\t(cd {bdir} && mv RPMS/*.rpm {rpmpath})\n".format(bdir=bdir, rpmpath=rpmpath)

    #     # finalize
    #     make += "\ttouch " + target_spec(self.specfname, tool) + "\n"
    #     if release is not None:
    #         make += "\t@echo {release} > {relfile}\n".format(release=release, relfile=relfile)
    #     # update success flag
    #     make += "\t@echo %s > %s\n" % (
    #         os.path.basename(specpath),
    #         current_build_successful_flag(tool),
    #     )
    #     make += "\t@echo %s\n" % success_txt_for_error
    #     make += "\texit 1\n"
    #     make += "\n"
    #     return make
