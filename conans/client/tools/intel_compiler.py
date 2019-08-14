import collections
import json
import os
import uuid
import subprocess
import sys

from contextlib import contextmanager

from conans.client.tools.env import environment_append
from conans.client.tools.oss import check_output
from conans.client.tools.win import _system_registry_key
from conans.model.version import Version


def _get_installation(settings, compiler=None, arch=None, version=None):
    compiler = compiler or (settings.get_safe("compiler") and settings.compiler)
    if compiler != "intel":
        return

    version = version or (compiler == "intel" and compiler.get_safe("version"))
    base_compiler = compiler.get_safe("base")
    if base_compiler == "gcc":
        # We try the default install location
        year = "20%s" % Version(version).major(fill=False)
        default_install_directory = os.path.join(
            os.sep, "opt", "intel", "compiler_and_libraries_%s" % year, "linux")
        return default_install_directory if os.path.isdir(default_install_directory) else None
    elif base_compiler == "Visual Studio":
        from six.moves import winreg

        arch = arch or settings.get_safe("arch")

        if arch == "x86":
            arch = "IA32"
        elif arch == "x86_64":
            arch = "EM64T"
        else:
            return None

        sub_key = (
            version
            and _system_registry_key(
                winreg.HKEY_LOCAL_MACHINE,
                rf"SOFTWARE\WOW6432Node\Intel\Suites\{version}\Defaults\C++\{arch}",
                "SubKey",
            )
        )

        return (
            version
            and sub_key
            and _system_registry_key(
                winreg.HKEY_LOCAL_MACHINE,
                rf"SOFTWARE\WOW6432Node\Intel\Suites\{version}\{sub_key}\C++",
                "LatestDir",
            )
        )
    else:
        return None


def _compilervars_command(settings, compiler=None, arch=None, version=None, force=False):
    if "PSTLROOT" in os.environ and not force:
        return "echo Conan:compilervars already set"

    arch = arch or settings.get_safe("arch")

    install_dir = _get_installation(
        settings=settings, compiler=compiler, arch=arch, version=version
    )
    if not install_dir:
        return None

    if arch == "x86":
        arch = "ia32"
    elif arch == "x86_64":
        arch = "intel64"
    else:
        return None

    base_compiler = compiler.get_safe("base")
    if base_compiler == "Visual Studio":
        command = ["call", os.path.join(install_dir, "bin",
                                        "compilervars.bat"), "-arch", arch]
        base_version = compiler.get_safe("base.version")
        if base_version:
            _visuals = {
                "8": "vs2005",
                "9": "vs2008",
                "10": "vs2010",
                "11": "vs2012",
                "12": "vs2013",
                "14": "vs2015",
                "15": "vs2017",
                "16": "vs2019",
            }
            command.append(_visuals[base_version])
        return command
    else:
        return [".", os.path.join(install_dir, "bin", "compilervars.sh"), "-arch ", arch]


def compilervars_command(settings, compiler=None, arch=None, version=None, force=False):
    res = _compilervars_command(settings, compiler, arch, version, force)
    if res:
        return subprocess.list2cmdline(res)
    return None


def _get_env(command):
    uuid_str = uuid.uuid4().hex
    command = command[:]
    command.extend((
        "&&"
        "echo", uuid_str,
        "&&",
        sys.executable, "-c", "import json, os; print(json.dumps(dict.os.environ))"
    ))
    check_output(command)
    output = check_output(command)

    return json.loads(output[output.find(uuid_str) + len(uuid_str):])


def _env_diff(command):
    _make_ordered_set = (
        dict.fromkeys
        if sys.version_info >= (3, 7)
        else collections.OrderedDict.fromkeys
    )

    new_env = _get_env(command)
    case_insensitive = sys.platform == "win32"

    ret = {}
    for var, new_value in new_env.items():
        old_value = os.environ.get(var)

        if old_value is None:
            ret[var] = new_value
            continue

        if case_insensitive:
            new_value = new_value.lower()
            old_value = old_value.lower()

        if old_value == new_value:
            continue

        old_values = old_value.split(os.pathsep)
        new_values = new_value.split(os.pathsep)

        if len(old_values) == 1 and len(new_values) == 1:
            ret[var] = new_value
            continue

        clean_new_values = _make_ordered_set(value for value in new_values if value)

        ret[var] = [value for value in clean_new_values if value not in old_values]
    return ret


def compilervars_dict(*args, **kwds):
    command = _compilervars_command(*args, **kwds)

    return (command or {}) and _env_diff(command)


@contextmanager
def compilervars(*args, **kwds):
    with environment_append(compilervars_dict(*args, **kwds)):
        yield
