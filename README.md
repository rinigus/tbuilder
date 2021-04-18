# TBuilder

This is a builder for projects defined by multiple RPM SPECs. It is
targeting Sailfish OS and is using `sfdk` or `mb2/sb2` provided by
Sailfish OS Application or Platform SDKs.

## Use

To define a project, create a directory with the following structure:

- config.xml
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
../tbuilder .
```

## Configuration

Configuration is given using `config.yaml` file. Example configuration
is given under `project` directory.

The following fields are required:

* `project` (string) giving a name of the project. The name is used
  while creating snapshots during building by `sfdk`.

* `targets` (list) with the targets as defined by `sfdk tools target
  list`

* `rpms` (string) directory to store generated RPMs

The following fields are optional:

* `buildoptions` (string) additional options to pass to `sfdk
  build`. For example, `-j4`.

* `macros` (list of strings) macros considered while parsing RPM SPEC
  and during the build.

* `insource` (list of strings) SPEC packages that have to be built
  inside source directory. In this case, the sources will be copied
  into the build directory and the build will be run with the copied
  sources. If it contains string `ALL` then all builds will be done
  assuming that this parameter is set.

* `provides` (dict with list of string values) additional symbols
  provided by RPM SPEC. In general, it is not required as provided
  symbols are detected automatically.


## Requirements

Requirements are

- If using from host PC, `sfdk` available in the PATH and
  working. Consider adding symlink from some standard PATH directory
  to Sailfish SDO `bin/sfdk`. Check that `sfdk` works, see
  [Tutorial](https://sailfishos.org/wiki/Tutorial_-_Building_packages_-_advanced_techniques)
  for description.

- If run from SDK shell, mb2/sb2 will be used. Note that you would
  have to install `make` into that shell as `make` is not installed by
  default in Application SDK. For that, login as root and run `zypper
  in make`.
