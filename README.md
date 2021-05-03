# TBuilder

This is a builder for projects defined by multiple RPM SPECs. It is
targeting Sailfish OS and is using `mb2/sb2` or `sfdk` provided by
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

* `options` (list of strings) specify project options. Currently, the
  following options can be set:
  * `allow-vendor-change` Allow to change vendor while installing packages
    from project RPMS directory

* `buildoptions` (string) additional options to pass to `sfdk
  build`. For example, `-j4`.

* `install` (list of strings) list of packages that are installed into
  the target during a build. Errors during installation are ignored
  and installation is attempted on every iteration of the build. This
  list allows you to specify packages that are needed for processing
  SPECs or are otherwise in the conflict with the installed target
  packages.

* `macros` (list of strings) macros considered while parsing RPM SPEC
  and during the build.

* `shadow_builds` (list of strings) SPEC packages that will be built
  using shadow builds approach (see SDK documentation).

* `skip_rpms` (list of strings) regex expressions that are matched
  against compiled RPM file basenames. If the filename matches (Python
  re.match) then the corresponding RPM is not loaded and its provided
  symbols are not considered. Useful for larger builds with some of
  RPMs not used a build dependencies for others.


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


## Caches

To speed up the builds, there are several caches used:

- `build/target/cache.yaml` Lists present and missing build requirements
  in the target itself. If you change the target, such as add new
  repositories, please remove this cache to get all requirements
  checked again.

- `build/target/cache_rpm.yaml` RPMs that are built in the project and
  were found to be installable in the target. It is assumed that if it
  was possible to install an RPM in the target once, it is possible to
  do so later as well. This allows to skip the corresponding check
  later in the build sequence. If for some reason you think that this
  condition is not satisfied after your updates, remove that cache and
  let TBuilder to regenerate it.
