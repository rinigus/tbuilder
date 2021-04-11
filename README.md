# TBuilder

This is a take on building projects defined by multiple RPM SPECs. It
is targeting Sailfish OS and is using `sfdk` provided by Sailfish OS
SDK. It works, but is rather limited and should be mainly considered
for smaller projects.

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

With the project defined, `generate` script will create `Makefile`. To
build packages, run `make` in the project directory:

```
cd project
../generate .
make
```

`make` will build one package in a time, according to the detected
dependencies. See below (drawbacks) for main issue with the dependency
detection.


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

* `provides` (dict with list of string values) additional symbols
  provided by RPM SPEC that are not detected by `rpmspec` query but
  can be used by other packages. This option is added for handling 


## Requirements

Requirements are

- `sfdk` available in the PATH and working. Consider adding symlink
  from some standard PATH directory to Sailfish SDO `bin/sfdk`. Check
  that `sfdk` works, see
  [Tutorial](https://sailfishos.org/wiki/Tutorial_-_Building_packages_-_advanced_techniques)
  for description.

- `rpmspec` in the PATH. Many distributions allow you to install it
  even when some other packaging format is used.


## Drawbacks

Main drawback is in inability to determine all symbols provided by a
package. For example, `pkgconfig(lib)` is set to be provided
automatically and can be used as a build requirement. Right now,
`generate` script is not able to determine these package-provided
symbols and will ignore them. So, maybe completely different approach
should be taken. See issue
[#1](https://github.com/rinigus/tbuilder/issues/1) for discussion on
possible solutions.