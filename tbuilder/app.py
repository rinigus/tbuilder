#!/usr/bin/env python3

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
import yaml  # pip PyYAML
import xml.etree.ElementTree as ET


# definition of dirs
def rpmdir(root, tool):
    return os.path.join(root, tool)


def builddir(tool):
    return os.path.join("build", tool)


def releasedir(tool):
    return os.path.join(builddir(tool), "release")


def targetdir(tool):
    return os.path.join(builddir(tool), "target")


def logdir(tool):
    return os.path.join(builddir(tool), "logs")


def current_build_successful_flag(tool):
    return os.path.join(builddir(tool), "last_package_success.txt")


success_txt_for_error = "@@@ THIS IS A SUCCESSFUL BUILD THAT WAS FINISHED FOR UPDATING PACKAGE DEPENDENCIES. IGNORE THE ERROR BELOW @@@"


# helper for running commands
def run_with_check(cmd, check_error=True, cwd=None):
    if isinstance(cmd, str):
        cmd = cmd.split()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    if proc.returncode and check_error:
        print("Error while executing", " ".join(cmd))
        print("Return code:", proc.returncode)
        print("STDOUT:\n" + proc.stdout.decode("utf-8"))
        print("STDERR:\n" + proc.stderr.decode("utf-8"))
        sys.exit(-2)

    return proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


# commands abstraction
class Commands:
    def __init__(self):
        self.project = ""
        self.allow_vendor_change = False
        # check whether to use sfdk or not
        if shutil.which("mb2") is not None and shutil.which("sb2") is not None:
            self.use_sfdk = False
        elif shutil.which("sfdk") is not None:
            self.use_sfdk = True
        else:
            print("Cannot find sfdk nor sb2/mb2")
            sys.exit(-1)

    def target_base(self, tool):
        return tool

    def target_snapshot(self, tool):
        return "%s.%s" % (tool, self.project)

    def make_snapshot(self, tool):
        if self.use_sfdk:
            cmd = "sfdk engine exec "
        else:
            cmd = ""
        cmd += "sdk-manage target snapshot --reset=force %s %s" % (
            tool,
            self.target_snapshot(tool),
        )
        proc = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(cmd)
        print(proc.stdout.decode("utf-8"))
        print(proc.stderr.decode("utf-8"))
        return proc.returncode == 0

    def createrepo(self, tool, rpmpath):
        if self.use_sfdk:
            cmd = "sfdk tools exec %s createrepo_c " % self.target_snapshot(tool)
        else:
            cmd = "sb2 -t %s -m sdk-install createrepo_c " % self.target_snapshot(tool)
        cmd += os.path.abspath(rpmpath)
        run_with_check(cmd)

    def install_package_cmd(self, tool, package, force=False, extra_repo=None):
        if self.use_sfdk:
            cmd = "sfdk tools exec %s " % self.target_snapshot(tool)
        else:
            cmd = "sb2 -t %s -m sdk-install -R " % self.target_snapshot(tool)
        cmd += "zypper "
        if extra_repo is not None:
            cmd += "-p " + os.path.abspath(extra_repo) + " "
        cmd += "in "
        if force:
            cmd += "--force-resolution "
        cmd += "-y --allow-unsigned-rpm "
        if self.allow_vendor_change:
            cmd += "--allow-vendor-change "
        cmd += package
        return cmd

    def install_package(self, tool, package, force=False, extra_repo=None):
        print("Installing", package, flush=True, end=": ")
        cmd = self.install_package_cmd(tool=tool, package=package, force=force, extra_repo=extra_repo)
        proc = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with open(os.path.join(logdir(tool), "zypper-install-" + package + ".log"), "w") as f:
            f.write(cmd + "\n" + proc.stdout.decode("utf-8"))
        if proc.returncode == 0:
            print("Installed")
        else:
            print("Failed this time")

    def make_section(self, tool, bdir, rpmpath, specpath, buildoptions, srcpath, rpmbuild):
        make = ""
        if self.use_sfdk:
            make += "\t" + "sfdk config no-fix-version\n"
            make += "\t" + "sfdk config target=" + tool + "\n"
            make += "\t" + "sfdk config --drop output-dir\n"
            # make += '\t' + 'sfdk config output-dir=' + rpmpath + '\n'
            make += "\t" + "sfdk config snapshot=%s \n" % self.project
            make += "\t" + "(cd %s && " % bdir
            make += "sfdk config specfile=" + specpath + " && "
            make += "sfdk build -d %s %s %s)\n" % (buildoptions, srcpath, rpmbuild)
        else:
            # make += '\t' + \
            #     '(cd {bdir} && mb2 -t {target} -o {output} -s {spec} --snapshot={snap} build -d {bopts} {src} {rpmbuild})\n'.format(
            #         bdir = bdir, target = tool, output = rpmpath, spec = specpath,
            #         snap = self.project, bopts = buildoptions, src = srcpath, rpmbuild = rpmbuild)
            make += (
                "\t"
                + "(cd {bdir} && mb2 -t {target} -s {spec} -X --snapshot={snap} build -d {bopts} {src} {rpmbuild})\n".format(
                    bdir=bdir,
                    target=tool,
                    output=rpmpath,
                    spec=specpath,
                    snap=self.project,
                    bopts=buildoptions,
                    src=srcpath,
                    rpmbuild=rpmbuild,
                )
            )
        return make

    def refresh_system(self, tool):
        tgt = self.target_base(tool)
        if self.use_sfdk:
            cmd = "sfdk tools exec %s zypper --non-interactive refresh" % tgt
        else:
            cmd = "sb2 -t %s -m sdk-install -R zypper --non-interactive refresh" % tgt
        print("Refreshing zypper cache for", tgt)
        s, e = run_with_check(cmd)
        print(s)

    def can_install_cmd(self, tool, rpmfname):
        fname = os.path.abspath(rpmfname)
        dname = os.path.dirname(fname)
        if self.use_sfdk:
            cmd = ["sfdk", "tools", "exec", self.target_snapshot(tool)]
        else:
            cmd = ["sb2", "-t", self.target_snapshot(tool), "-m", "sdk-install", "-R"]
        cmd.extend(["zypper", "-x", "-p", dname])
        cmd.extend(("in --dry-run --download-only -y --allow-unsigned-rpm").split())
        if self.allow_vendor_change:
            cmd.append("--allow-vendor-change")
        cmd.append(fname)
        return cmd

    def run_cmd(self, tool, cmd):
        if self.use_sfdk:
            # prepare sfdk to run
            run_with_check("sfdk config target=" + tool)
            run_with_check("sfdk config snapshot=%s" % self.project)
            return "sfdk build-shell %s" % cmd
        return "sb2 -t %s -m sdk-install %s" % (self.target_snapshot(tool), cmd)


# global commands instance
commands = Commands()


# shared by spec and rpm classes
def query(tool, exe, specname, q, macros=[], check_error=True, cwd=None):
    cmd = commands.run_cmd(tool, exe).split()
    cmd.extend(["-q", q])
    for m in macros:
        cmd.append("--define=%s" % m)
    cmd.append(specname)
    stdout, stderr = run_with_check(cmd, check_error, cwd=cwd)

    # stdout = proc.stdout.decode('utf-8')
    result = []
    result_full = {}
    for l in stdout.split("\n"):
        r = l.split()
        if len(r) > 0:
            rr = r[0].strip()
            result.append(rr)
            result_full[l.strip()] = rr
    return result, result_full


def install_extras(tool, install, repo):
    if len(install) == 0:
        return
    print("Install extra packages requested in the project configuration")
    for p in install:
        commands.install_package(tool, p, force=True, extra_repo=repo)
    print()


# processing of targets
def tf(s):
    # replace chars that may cause issues for make or filesystem
    return re.sub("[():%]", "_", s)


def target_dir(name):
    return tf(os.path.join(name, ".directory"))


def target_builddir(tool):
    return tf(target_dir(builddir(tool)))


def target_targetdir(tool):
    return tf(target_dir(targetdir(tool)))


def target_rpmdir(root, tool):
    return tf(target_dir(rpmdir(root, tool)))


def target_generic(name, tool):
    return tf(os.path.join(targetdir(tool), name))


def target_spec(s, tool):
    return tf(target_generic(os.path.basename(s), tool))


def target_provides(p, tool):
    p = p.replace("/", "_")
    return tf(target_generic(p, tool))


# make snippets
def make_dir(dname):
    return (
        target_dir(dname)
        + ":\n"
        + "\tmkdir -p "
        + dname
        + "\n"
        + "\ttouch "
        + target_dir(dname)
        + "\n"
        + "\n"
    )


class LocalProvided:
    # symbols provided by local RPMs
    def __init__(self, tool):
        self.tool = tool
        self._provided = set()

    def provided(self, r, rsimple):
        return rsimple in self._provided

    def add_provided(self, rsimple, refname):
        pold = copy.copy(self._provided)
        if isinstance(rsimple, set):
            self._provided.update(rsimple)
            for p in rsimple:
                self._write_target_if_absent(p, refname)
        else:
            self._provided.add(rsimple)
            self._write_target_if_absent(rsimple, refname)
        return pold != self._provided

    def cleanup(self):
        # remove all target files that are not known about
        known_fnames = [target_provides(p, self.tool) for p in self._provided]
        to_delete = []
        for f in sorted(glob.glob(os.path.join(targetdir(tool), "*"))):
            if f.endswith(".spec"):
                # target made by spec compilation
                pass
            elif f not in known_fnames:
                to_delete.append(f)
        for f in to_delete:
            print("Removing unknown target file:", f)
            os.remove(f)

    def print_provided(self):
        if len(self._provided) < 10:
            p = list(self._provided)
            p.sort()
            print("Available local provided symbols:", " ".join(p), "\n")
        elif len(self._provided) > 0:
            print("Available local provided symbols:", len(self._provided), "symbols\n")

    def _write_target_if_absent(self, p, refname):
        tname = target_provides(p, self.tool)
        stat = os.stat(refname)
        if not os.path.exists(tname):
            f = open(tname, "w")
            f.write(refname)
        else:
            # modify timestamp only if target_provides is older than RPM.
            # this is to avoid touching timestamps as much as possible.
            # otherwise, have seen some rebuilds triggered by incorrect
            # timestamps
            sp = os.stat(tname)
            if sp.st_mtime_ns < stat.st_mtime_ns:
                os.utime(tname, ns=(stat.st_atime_ns, stat.st_mtime_ns))


class RPM:
    # handle RPM
    cache_fname = "cache_rpm.yaml"
    current_cache = []
    current_cache_fname = None
    log_prefix = "zypper-rpm-log-"

    def __init__(self, tool, rpmfname):
        print(rpmfname, flush=True, end=": ")
        self.tool = tool
        self.rpmfname = rpmfname
        self.short_rpmfname = os.path.basename(self.rpmfname)
        self.name = query(tool, "rpm", rpmfname, "--queryformat=%{NAME} ", check_error=False)[0][0]
        self.mtime = os.path.getmtime(rpmfname)
        self.provides = set(query(tool, "rpm", rpmfname, "--provides", check_error=False)[0])
        self.missing = []
        self.log_check_fname = os.path.join(logdir(self.tool), RPM.log_prefix + self.short_rpmfname + ".xml")
        print("Done")

    def can_use(self, skip_rpms):
        # skip the check if requested in the project config
        for p in skip_rpms:
            if p.match(self.short_rpmfname):
                return False

        # expect that if RPM was installable once, it will hold later in the build
        if RPM.is_cached(self.rpmfname):
            return True
        print(
            "Checking whether %s can be used:" % self.short_rpmfname,
            end=" ",
            flush=True,
        )
        self.missing = []
        cmd = commands.can_install_cmd(self.tool, self.rpmfname)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        s = proc.stdout.decode("utf-8")
        root = ET.fromstring(s)
        if proc.returncode:
            # cannot install
            ## log the output of zypper for details
            with open(self.log_check_fname, "w") as f:
                f.write(s)
            ## process output
            for i in root.iter("description"):
                # limit error message to 100 chars and use only the last one with a problem
                d = i.text.split("\n")[0][:100]
                if len(self.missing) == 0 or d.startswith("Problem"):
                    self.missing = [d]
            print("No")
            return False
        # should have received positive reply
        for i in root.iter("solvable"):
            print("Yes")
            RPM.add_to_cache(self.rpmfname)
            return True
        # check if it is installed already
        for i in root.iter("message"):
            if i.text.find(" is already installed.") > 0:
                print("Yes, installed already")
                RPM.add_to_cache(self.rpmfname)
                return True
        # not expected
        print("Unexpected reply from zypper")
        print("Used command: ", " ".join(cmd))
        print("Response:")
        print(proc.stdout.decode("utf-8"))
        print("ERR:")
        print(proc.stderr.decode("utf-8"))
        break_on_purpose_please_notify_developers
        return False

    @staticmethod
    def update_cache(tool):
        RPM.current_cache = []
        bdir = builddir(tool)
        RPM.current_cache_fname = os.path.join(bdir, RPM.cache_fname)
        if os.path.exists(RPM.current_cache_fname):
            with open(RPM.current_cache_fname, "r") as f:
                c = yaml.safe_load(f)
                if isinstance(c, list):
                    RPM.current_cache = c

    @staticmethod
    def add_to_cache(fname):
        RPM.current_cache.append(fname)
        if RPM.current_cache_fname is None:
            return
        with open(RPM.current_cache_fname, "w") as f:
            yaml.safe_dump(RPM.current_cache, f)

    @staticmethod
    def is_cached(fname):
        return fname in RPM.current_cache


class Spec:
    # handle SPEC
    def __init__(self, s, macros, keeprelease=False):
        print(s, flush=True, end=": ")
        self.specfname = s
        self.keeprelease = keeprelease
        # determine src and spec abs path
        ## handle case where we can have relative symbolic links
        ## as well as rpm within the source dir which is symlink.
        ## for these cases, resolve symlink late
        slink = os.readlink(s)
        rpmdir, specfname_rel = os.path.split(slink)
        self.srcpath, rpmpath_rel = os.path.split(rpmdir)
        self.specfname_rel = os.path.join(rpmpath_rel, specfname_rel)
        # handle relative path
        if not os.path.isabs(self.srcpath):
            self.srcpath = os.path.abspath(os.path.join(os.path.dirname(s), self.srcpath))
        # fill data using queries
        self.name = query(
            tool,
            "rpmspec",
            self.specfname_rel,
            "--queryformat=%{NAME} ",
            macros,
            cwd=self.srcpath,
        )[0][0]
        self.requires, self.requires_full = query(
            tool,
            "rpmspec",
            self.specfname_rel,
            "--buildrequires",
            macros,
            cwd=self.srcpath,
        )
        self.requires = set(self.requires)
        self.missing = set()
        print(self.name)

    def __str__(self):
        return "{name}: {specfname}  / requires: {requires} / missing: {missing}".format(**self.__dict__)

    def can_build(self, system_provided, local_provided):
        self.missing = set()
        for r, rsimple in self.requires_full.items():
            if not local_provided.provided(r, rsimple) and not system_provided.provided(r, rsimple):
                self.missing.add(r)
        return len(self.missing) == 0

    def load_release(self, tool):
        rfile = os.path.join(releasedir(tool), os.path.basename(self.specfname))
        release = 0
        if os.path.exists(rfile):
            with open(rfile, "r") as f:
                t = f.read()
                try:
                    release = int(t)
                except:
                    pass
        release += 1
        return rfile, release

    def make_spec(self, local_provided, tool, rpmroot, buildoptions, macros, insource):
        req = [rsimple for r, rsimple in self.requires_full.items() if local_provided.provided(r, rsimple)]
        make = target_spec(self.specfname, tool) + ": %s %s %s %s " % (
            target_targetdir(tool),
            target_builddir(tool),
            target_rpmdir(rpmroot, tool),
            self.specfname,
        )
        make += " ".join([target_provides(i, tool) for i in req])
        make += "\n"
        # determine src and spec path
        sbase = os.path.basename(self.specfname)
        bdir = os.path.join(builddir(tool), sbase)
        specpath = os.path.abspath(self.specfname)
        rpmpath = os.path.abspath(rpmdir(rpmroot, tool))
        # build options for rpmbuild
        if len(macros) > 0:
            rpmbuild = " " + " ".join(['--define="%s"' % m for m in macros])
        else:
            rpmbuild = ""
        # get release info
        if insource and not self.keeprelease:
            relfile, release = self.load_release(tool)
        else:
            relfile, release = None, None
        # write build section
        make += "\t" + "@echo\n"
        make += "\t" + "@echo Building %s for %s\n" % (self.specfname, tool)
        make += "\t" + "@echo\n"
        if not insource:
            make += "\t" + "rm -rf %s\n" % bdir
        make += "\t" + "mkdir -p %s\n" % bdir
        if insource:
            make += "\t" + "rsync -a --delete %s/ %s/\n" % (self.srcpath, bdir)
            srcpath = "."
            specpath = self.specfname_rel
            buildoptions = buildoptions + " -p"
        else:
            srcpath = self.srcpath

        if release is not None:
            make += "\t" + '(cd {bdir} && sed -i "s/^Release:.*\\S/&.{release}/" {spec})\n'.format(
                bdir=bdir, release=release, spec=specpath
            )

        if len(req) > 0:
            make += (
                "\t"
                + commands.install_package_cmd(
                    tool=tool,
                    force=True,
                    extra_repo=rpmpath,
                    package=" ".join(['"%s"' % r for r in req]),
                )
                + "\n"
            )
        make += commands.make_section(
            bdir=bdir,
            tool=tool,
            rpmpath=rpmpath,
            specpath=specpath,
            buildoptions=buildoptions,
            srcpath=srcpath,
            rpmbuild=rpmbuild,
        )
        make += "\t(cd {bdir} && mv RPMS/*.rpm {rpmpath})\n".format(bdir=bdir, rpmpath=rpmpath)

        # finalize
        make += "\ttouch " + target_spec(self.specfname, tool) + "\n"
        if release is not None:
            make += "\t@echo {release} > {relfile}\n".format(release=release, relfile=relfile)
        # update success flag
        make += "\t@echo %s > %s\n" % (
            os.path.basename(specpath),
            current_build_successful_flag(tool),
        )
        make += "\t@echo %s\n" % success_txt_for_error
        make += "\texit 1\n"
        make += "\n"
        return make


class SystemProvided:
    # follows system provided symbols
    def __init__(self, tool):
        self.system_provided = set()
        self.system_missing = set()
        self.tool = tool
        self._cachefname = "cache.yaml"
        self._was_updated = False
        # load cache if it is available
        bdir = builddir(tool)
        self._current_cache = os.path.join(bdir, self._cachefname)
        if os.path.exists(self._current_cache):
            with open(self._current_cache, "r") as f:
                c = yaml.safe_load(f)
                if isinstance(c, dict):
                    self.system_provided = set(c.get("system_provided", []))
                    self.system_missing = set(c.get("system_missing", []))

    def provided(self, r, rsimple):
        if r in self.system_provided:
            return True
        if r in self.system_missing:
            return False

        # hack, as for some reason those get undetected
        if r.startswith("rpmlib("):
            return True

        self._was_updated = True
        print("Check for availibility in the system:", r, flush=True, end=" : ")
        in_system = self._system_has(r)

        if in_system:
            print("Available")
            self.system_provided.add(r)
            self.system_provided.add(rsimple)
            return True
        else:
            print("Requires building")
            self.system_missing.add(r)
            return False

    def _system_has(self, r):
        cmd = commands.run_cmd(self.tool, "zypper -x search --provides --match-exact").split()
        cmd.append(r)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # zypper returns non-zero if failing to find
        if proc.returncode:
            return False  # assume that it just failed to find
        s = proc.stdout.decode("utf-8")
        root = ET.fromstring(s)
        for i in root.iter("solvable"):
            return True
        return False

    def was_checking(self):
        if not self._was_updated:
            return False
        self._was_updated = False
        return True

    def write_cache(self):
        with open(self._current_cache, "w") as f:
            c = dict(
                system_provided=list(self.system_provided),
                system_missing=list(self.system_missing),
            )
            yaml.safe_dump(c, f)


class TargetDirTracker:
    # state of the targets in targets dir
    def __init__(self, tool):
        self.targets = dict()
        self.tool = tool
        self.update()

    def update(self):
        # return True if some targets got updated
        tgts = dict()
        for f in glob.glob(os.path.join(targetdir(self.tool), "*")):
            stat = os.stat(f)
            tgts[f] = stat.st_mtime_ns
        if tgts == self.targets:
            return False
        self.targets = tgts
        return True


##########################################################
## main
def main():

    parser = argparse.ArgumentParser(description="Generate project build files")

    parser.add_argument("project_directory", help="Directory containing project files")

    args = parser.parse_args()

    project = args.project_directory
    if not os.path.isdir(project):
        print("Project directory does not exist or is not a directory:", project)
        sys.exit(-1)

    # change to project dir
    os.chdir(project)

    # load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    project_name = config.get("project", "")
    targets = config.get("targets", [])
    rpmrootdir = config.get("rpms", "")
    macros = config.get("macros", [])
    project_options = config.get("options", [])
    buildoptions = config.get("buildoptions", "")
    shadow_builds = config.get("shadow_builds", [])
    install_extra_packages = config.get("install", [])
    skip_rpms = config.get("skip_rpms", [])
    specdir = "spec"
    repodir = "repodata"

    # check for required parameters
    if len(project_name) < 1:
        print("No project name specified in the project config.yaml")
        sys.exit(-1)
    if len(targets) < 1:
        print("No targets specified in the project config.yaml")
        sys.exit(-1)
    if len(rpmrootdir) < 1:
        print("No RPMS directory specified in the project config.yaml")
        sys.exit(-1)

    # add subdir to required keys
    shadow_builds = [os.path.join(specdir, k) for k in shadow_builds]

    # prepare re expressions
    skip_rpms = [re.compile(s) for s in skip_rpms]

    # check specified options
    if "allow-vendor-change" in project_options:
        commands.allow_vendor_change = True
    keeprelease = "keep-release-from-spec" in project_options

    commands.project = project_name

    # main loop
    summary = {}
    for tool in targets:
        print("Starting builds for", tool, "\n")

        # initialize for each target
        commands.refresh_system(tool)
        print("Create snapshot if it is missing or reset it")
        commands.make_snapshot(tool)

        # remove createrepo-generated repodata
        repodir_full = os.path.join(rpmdir(rpmrootdir, tool), repodir)
        if os.path.exists(repodir_full):
            shutil.rmtree(repodir_full)

        # prepare directories
        rdir = rpmdir(rpmrootdir, tool)
        bdir = builddir(tool)
        os.makedirs(rdir, exist_ok=True)
        os.makedirs(bdir, exist_ok=True)
        os.makedirs(releasedir(tool), exist_ok=True)
        os.makedirs(targetdir(tool), exist_ok=True)
        os.makedirs(logdir(tool), exist_ok=True)

        # install requested packages, could be used already during loading of SPECs
        install_extras(tool, install_extra_packages, rdir)

        # load SPECs and their properties
        print("Loading SPECs:\n")
        specs = {}
        for f in sorted(glob.glob(os.path.join(specdir, "*.spec"))):
            s = Spec(f, macros, keeprelease)
            specs[s.name] = s
        print()

        # track states
        system_provided = SystemProvided(tool)
        targets_state = TargetDirTracker(tool)
        RPM.update_cache(tool)

        # load RPMs
        print("Loading RPMs:\n")
        rpms = {}
        for rpmfname in sorted(glob.glob(os.path.join(rdir, "*.rpm"))):
            rpms[rpmfname] = RPM(tool, rpmfname)
        print()

        # start build loop
        Done = False
        Error = False
        first_iteration = True
        while not Done:

            if not first_iteration:
                # reset snapshot and install requested packages
                commands.make_snapshot(tool)
                install_extras(tool, install_extra_packages, rdir)

            # remove successful build indicator if exists
            flag = current_build_successful_flag(tool)
            if os.path.exists(flag):
                os.remove(flag)

            # query provided symbols in current ready RPMs
            local_provided = LocalProvided(tool)

            # update with new RPMs
            rpmfiles = []
            for rpmfname in sorted(glob.glob(os.path.join(rdir, "*.rpm"))):
                rpmfiles.append(rpmfname)
                if rpmfname not in rpms:
                    rpms[rpmfname] = RPM(tool, rpmfname)

            # keep only one version of rpm with the same name
            rpms_by_name = collections.defaultdict(list)
            for _, r in rpms.items():
                rpms_by_name[r.name].append(r)
            for _, rlist in rpms_by_name.items():
                if len(rlist) > 1:
                    rlist.sort(key=lambda x: x.mtime)
                    # remove all but the last file
                    for r in rlist[:-1]:
                        print("Removing old build:", r.rpmfname)
                        os.remove(r.rpmfname)
                        del rpms[r.rpmfname]

            # drop missing RPMs
            to_del = []
            for rk in rpms:
                if rk not in rpmfiles:
                    to_del.append(rk)
            for rk in to_del:
                del rpms[rk]

            # remove old logs
            for f in glob.glob(os.path.join(logdir(tool), RPM.log_prefix + "*")):
                os.remove(f)

            # as dependencies are checked by zypper, no need to iterate as we
            # populate local_provided
            for _, r in rpms.items():
                if r.can_use(skip_rpms):
                    local_provided.add_provided(r.provides, r.rpmfname)
            print()

            # write out which RPMs cannot be used
            hadmissing = False
            rkeys = list(rpms.keys())
            rkeys.sort()
            for rk in rkeys:
                r = rpms[rk]
                if len(r.missing) > 0:
                    print("-", os.path.basename(r.rpmfname), "not used:", " ".join(r.missing))
                    hadmissing = True
            if hadmissing:
                print()

            # remove unknown target files that we cannot use
            local_provided.cleanup()

            # print out locally provided symbols used in the build
            local_provided.print_provided()

            # determine whether packages are missing something preventing the build
            tomake = []
            skipped = []
            missing_txt = []
            for k, s in specs.items():
                if s.can_build(system_provided, local_provided):
                    tomake.append(k)
                else:
                    mt = "- {name}({spec}) has missing dependencies: ".format(name=s.name, spec=s.specfname)
                    mt += " ".join(s.missing)
                    missing_txt.append(mt)
                    skipped.append(k)

            if system_provided.was_checking():
                print()
                system_provided.write_cache()

            if len(missing_txt) > 0:
                missing_txt.sort()
                print("\n".join(missing_txt))

            tomake.sort()
            skipped.sort()

            # summarize findings
            print()
            print("Packages included into the current build:", " ".join(tomake))

            # generate Makefile
            main_deps = ""

            make = "# This is generated Makefile and can be overwritten by a script\n\n"
            make += "all: all_packages\n\n"

            main_deps += " ".join([target_spec(specs[s].specfname, tool) for s in tomake]) + " "

            # create directories
            make += make_dir(builddir(tool))
            make += make_dir(targetdir(tool))
            make += make_dir(rpmdir(rpmrootdir, tool))

            for k, s in specs.items():
                # skip packages that we cannot build yet
                if k not in tomake:
                    continue

                make += s.make_spec(
                    local_provided=local_provided,
                    tool=tool,
                    rpmroot=rpmrootdir,
                    buildoptions=buildoptions,
                    macros=macros,
                    insource=(s.specfname not in shadow_builds),
                )

            make += "all_packages: %s\n\t@echo\n\t@echo All done\n\t@echo\n\n" % main_deps

            # disable parallel execution
            make += ".NOTPARALLEL:\n\n"

            # write Makefile
            makefname = os.path.join(bdir, "Makefile")
            with open(makefname, "w") as f:
                f.write(make)

            # start make in the background
            logfname = os.path.join(logdir(tool), "build.log")
            print(
                "\nStarting build with the log available at",
                os.path.join(project, logfname),
                "\n",
            )
            with open(logfname, "w") as flog:
                po = subprocess.Popen(
                    ["make", "-f", makefname],
                    bufsize=0,
                    stdout=flog,
                    stderr=subprocess.STDOUT,
                )
                result = po.wait()
                if result != 0:
                    # let's see if it was triggered
                    flag = current_build_successful_flag(tool)
                    if os.path.exists(flag):
                        with open(flag, "r") as fflag:
                            package_last = fflag.read()
                        print("Build successful:", package_last)
                    else:
                        print("Error while running Make. See log for details")
                        summary[tool] = "Error while running Make. See {log} for details".format(
                            log=os.path.join(project, logfname)
                        )
                        Error = True
                        break
                else:
                    print("Build successful\n")

            # current summary for this toolkit
            summary[tool] = (
                "Build packages: " + " ".join(tomake) + "\n\nSkipped packages: " + " ".join(skipped) + "\n"
            )

            # update conditions
            first_iteration = False
            changed = targets_state.update()
            if not changed:
                print("Nothing new, stopping for target", tool, "\n")
                Done = True
            else:
                print("Targets changed or updated, continue building\n")

        # generate repo data after the build
        print("Install createrepo if it is missing")
        commands.install_package(tool, "createrepo_c")
        commands.createrepo(tool, rpmdir(rpmrootdir, tool))

        # list packages in the order they were built
        ready = [
            (os.stat(t).st_mtime, os.path.basename(t)) for t in glob.glob(os.path.join(targetdir(tool), "*.spec"))
        ]
        ready.sort()
        summary[tool] += "\nPackages were built in the following order:\n"
        for p in ready:
            summary[tool] += datetime.datetime.fromtimestamp(p[0]).strftime("%x %X") + " " + p[1] + "\n"

        if Error:
            break

    print("\nAll builds finished\n")

    for t, s in summary.items():
        print(t, "\n")
        print(s, "\n\n")

    if Error:
        sys.exit(7)
