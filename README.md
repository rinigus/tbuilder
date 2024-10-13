# TBuilder

This is a builder for projects defined by multiple RPM SPECs. It is
targeting Sailfish OS and is using 
[docker-sailfishos-builder containers](https://github.com/sailfishos-open/docker-sailfishos-builder).

## Use

To define a project, create a directory with the following structure:

- config.yaml
- spec/
  - symlink to SPEC (absolute or relative) in source directory
  - symlink to SPEC2 ...

SPEC files in the source directories have to be located under some
subdirectory of the main source. This is common as SPECs are
positioned under `rpm` directory. Using symlinks, the builder will be
able to locate main source of the package in question.

With the project defined, `tbuilder` will handle dependencies and will
build packages:

```
cd project
tbuilder .
```

## Configuration

Configuration is given using `config.yaml` file. Example configuration
is given under `project` directory.

The following fields are required:

* `targets` (list) with each target in the form version-arch . Ex: 4.6.0.13-aarch64

* `rpms` (string) directory to store generated RPMs

The following fields are optional:

* `repositories` (list of strings) specify additional repositories required by the 
  project. Strings are processed by replacing @VERSION@ and @ARCH@ with the 
  target SFOS version and architecture, respectively. Ex: add 
  "https://repo.sailfishos.org/obs/sailfishos:/chum/@VERSION@_@ARCH@/" for Chum.

* `shallow_clones`: if set to non-zero (as `1`), tbuilder assumes that the submodules
  in source directories are not checked out with full sources, but have only packaging
  part. In this case, local sources will be ignored and used only to find out git remote
  and corresponding commit ID. Found repository and commit ID will be used during the build
  to download sources from the remote and build them. Such approach allows to reduce storage
  requirements and can help to build larger projects.


## Requirements and installation

Requirements are

- `podman` 
- if CPU emulation is needed, QEMU configured to run the platforms of interest.

For instructions, see [docker-sailfishos-builder](https://github.com/sailfishos-open/docker-sailfishos-builder).

To install, create Python virtual environment and install via `pip`:

```
python -m venv
. venv/bin/activate
pip install git+https://github.com/rinigus/tbuilder.git
```

To build project, run `tbuilder .` in the project directory.

