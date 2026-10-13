"""T-01–T-20: offline Doctor logic and controlled process/filesystem evidence."""

import ast
import builtins
import importlib.util
import io
import itertools
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/environment_doctor.py"
LAUNCHER = ROOT / "scripts/doctor.sh"
SECRET = "synthetic-token-postgresql://operator:password@host/private-home\x1b[31m"


@pytest.fixture
def doctor(monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    spec = importlib.util.spec_from_file_location("environment_doctor", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def environment(doctor, monkeypatch, tmp_path):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    (root / "scripts").mkdir()
    for name in (
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "Makefile",
        "compose.test.yaml",
        "scripts/database.py",
        "scripts/init-postgres.sh",
    ):
        (root / name).write_text("unexecuted fixture\n")
    (root / "scripts/environment_doctor.py").write_bytes(SOURCE.read_bytes())
    (root / "scripts/doctor.sh").write_bytes(LAUNCHER.read_bytes())
    (root / ".git").write_text("gitdir: fixture-worktree-pointer\n")
    (root / ".env.test.local").write_text(SECRET)
    (root / ".env.test.local").chmod(0o600)
    (root / ".env.dev.local").write_text(SECRET)
    home = tmp_path / "fake home"
    (home / ".docker").mkdir(parents=True)
    (home / ".docker/config.json").write_text(SECRET)
    (home / "unrelated-resource").write_text(SECRET)
    environ = {"PATH": "/fixture/bin", "HOME": str(home), "UNRELATED_TOKEN": SECRET}
    monkeypatch.setattr(doctor, "__file__", str(root / "scripts/environment_doctor.py"))
    monkeypatch.setattr(doctor.os, "environ", environ)
    monkeypatch.setattr(doctor.sys, "version_info", (3, 12, 13))
    monkeypatch.setattr(doctor.sys, "platform", "linux")
    monkeypatch.setattr(
        doctor.os,
        "uname",
        lambda: SimpleNamespace(sysname="Linux", machine="x86_64", release="generic-linux"),
    )
    monkeypatch.setattr(doctor.struct, "calcsize", lambda _: 8)
    monkeypatch.setattr(doctor.shutil, "which", lambda name, **_: "/fixture/bin/" + name)
    responses = {
        ("uv", ("--version",)): doctor.Probe(out=b"uv 0.11.29 (x86_64-unknown-linux-gnu)\n"),
        ("git", ("--version",)): doctor.Probe(out=b"git version 2.43.0\n"),
        ("git", (*doctor.GIT_PREFIX, "--is-inside-work-tree")): doctor.Probe(out=b"true\n"),
        ("git", (*doctor.GIT_PREFIX, "--show-toplevel")): doctor.Probe(
            out=str(root).encode() + b"\n"
        ),
        ("docker", ("--version",)): doctor.Probe(out=b"Docker version 28.2.2, build abc1234\n"),
        ("docker", ("compose", "version", "--short")): doctor.Probe(out=b"v2.39.1\n"),
        ("docker", ("context", "show")): doctor.Probe(out=b"desktop-linux\n"),
        (
            "docker",
            ("context", "inspect", "--format", doctor.CONTEXT_FORMAT, "desktop-linux"),
        ): doctor.Probe(out=b"unix:///fixture/docker.sock\n"),
        ("docker", doctor.DAEMON_ARGS): doctor.Probe(out=b"28.2.2\n"),
    }
    calls = []

    def transcript(tool, args, cwd, env, **kwargs):
        assert cwd == root and env is environ
        if args[:2] == ("context", "inspect"):
            assert kwargs == {"context": "desktop-linux"}
        else:
            assert kwargs == {}
        calls.append((tool, args))
        result = responses[(tool, args)]  # Any unlisted invocation fails the test.
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(doctor, "run_probe", transcript)
    return SimpleNamespace(
        doctor=doctor, root=root, home=home, environ=environ, responses=responses, calls=calls
    )


def invoke(environment, capsys, profile="core"):
    code = environment.doctor.main(["--profile", profile])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert SECRET not in captured.out
    assert str(environment.root) not in captured.out
    assert str(environment.home) not in captured.out
    return code, captured.out


def snapshot(root):
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        content = path.read_bytes() if stat.S_ISREG(info.st_mode) else None
        result[str(path.relative_to(root))] = (
            info.st_mode,
            info.st_uid,
            info.st_size,
            info.st_mtime_ns,
            content,
        )
    return result


def test_t01_core_is_docker_free(environment, monkeypatch, capsys):
    original = environment.doctor.shutil.which

    def which(name, **kwargs):
        assert name != "docker"
        return original(name, **kwargs)

    monkeypatch.setattr(environment.doctor.shutil, "which", which)
    original_lstat = Path.lstat

    def lstat(path, *args, **kwargs):
        assert not path.name.startswith(".env")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    code, output = invoke(environment, capsys)
    assert code == 0
    assert "Core prerequisites: satisfied" in output
    assert "Test prerequisites: excluded" in output
    assert "NOT CHECKED   DB_RUNTIME" in output
    assert not any(tool == "docker" for tool, _ in environment.calls)


@pytest.mark.parametrize("minor", [8, 11, 13])
def test_t02_incompatible_python(environment, monkeypatch, capsys, minor):
    monkeypatch.setattr(environment.doctor.sys, "version_info", (3, minor, 0))
    code, output = invoke(environment, capsys)
    assert code == 1 and "Python 3.12 required" in output
    assert not environment.calls


@pytest.mark.parametrize(
    "issue,code,output,expected",
    [
        ("missing", 0, b"", 1),
        ("", 1, b"", 1),
        ("timeout", 0, b"", 2),
        ("overflow", 0, b"", 2),
        ("", 0, b"uv unknown\n", 2),
        ("", 0, b"uv 0.11.29 " + SECRET.encode(), 2),
    ],
)
def test_t03_uv_negative(environment, capsys, issue, code, output, expected):
    environment.responses[("uv", ("--version",))] = environment.doctor.Probe(
        code, output, issue=issue
    )
    actual, text = invoke(environment, capsys)
    assert actual == expected and "UV" in text
    assert environment.calls.count(("uv", ("--version",))) == 1


@pytest.mark.parametrize("fault", ["missing", "false", "wrong-root", "not-repo", "ambiguous"])
def test_t04_checkout_negative(environment, capsys, fault):
    doctor = environment.doctor
    if fault == "missing":
        key, result = ("git", ("--version",)), doctor.Probe(issue="missing")
    elif fault == "wrong-root":
        key = ("git", (*doctor.GIT_PREFIX, "--show-toplevel"))
        result = doctor.Probe(out=b"/unrelated/checkout\n")
    else:
        key = ("git", (*doctor.GIT_PREFIX, "--is-inside-work-tree"))
        result = {
            "false": doctor.Probe(out=b"false\n"),
            "not-repo": doctor.Probe(128, err=b"not a git repository"),
            "ambiguous": doctor.Probe(out=b"true\nfalse\n"),
        }[fault]
    environment.responses[key] = result
    code, output = invoke(environment, capsys)
    assert code == (2 if fault == "ambiguous" else 1)
    assert "CHECKOUT" in output


def test_t04_space_and_worktree_identity(environment, capsys):
    before = (environment.root / ".git").read_bytes()
    code, output = invoke(environment, capsys)
    assert code == 0 and "Expected Git worktree root observed" in output
    assert (environment.root / ".git").read_bytes() == before


def test_t05_make_optional(environment, monkeypatch, capsys):
    monkeypatch.setattr(environment.doctor.shutil, "which", lambda *a, **k: None)
    code, output = invoke(environment, capsys)
    assert code == 0 and "WARN          MAKE" in output and "direct uv" in output


@pytest.mark.parametrize("fault", ["missing", "stopped", "denied", "unknown"])
def test_t06_docker_negative_core_independent(environment, capsys, fault):
    doctor = environment.doctor
    key = ("docker", ("--version",)) if fault == "missing" else ("docker", doctor.DAEMON_ARGS)
    results = {
        "missing": doctor.Probe(issue="missing"),
        "stopped": doctor.Probe(1, err=b"Cannot connect to the Docker daemon " + SECRET.encode()),
        "denied": doctor.Probe(1, err=b"permission denied " + SECRET.encode()),
        "unknown": doctor.Probe(1, err=SECRET.encode()),
    }
    environment.responses[key] = results[fault]
    assert invoke(environment, capsys)[0] == 0
    code, output = invoke(environment, capsys, "test")
    assert code == (2 if fault == "unknown" else 1)
    assert "Core prerequisites: satisfied" in output


@pytest.mark.parametrize(
    "name",
    [
        b"--help\n",
        b"a/b\n",
        b"a;b\n",
        b"$(secret)\n",
        b"desktop\nother\n",
        b"\x1b[31msecret\n",
        b"",
        b"bad name\n",
    ],
)
def test_t07_context_name_refusal(environment, capsys, name):
    environment.responses[("docker", ("context", "show"))] = environment.doctor.Probe(out=name)
    code, output = invoke(environment, capsys, "test")
    assert code == 2 and "Current-context proof ambiguous" in output
    assert not any(
        args[:2] == ("context", "inspect") or args == environment.doctor.DAEMON_ARGS
        for _, args in environment.calls
    )


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        (b"tcp://remote:2375\n", 1),
        (b"ssh://remote\n", 1),
        (b"npipe:////pipe/docker_engine\n", 1),
        (b"unix://relative\n", 2),
        (b"unix:///one\nunix:///two\n", 2),
        (b"unix:///one?secret\n", 2),
        (b"", 2),
    ],
)
def test_t07_endpoint_refusal(environment, capsys, endpoint, expected):
    key = (
        "docker",
        ("context", "inspect", "--format", environment.doctor.CONTEXT_FORMAT, "desktop-linux"),
    )
    environment.responses[key] = environment.doctor.Probe(out=endpoint)
    code, _ = invoke(environment, capsys, "test")
    assert code == expected
    assert ("docker", environment.doctor.DAEMON_ARGS) not in environment.calls


def test_ic01_explicit_current_context(environment, capsys):
    code, output = invoke(environment, capsys, "test")
    assert code == 0 and "Local Unix endpoint signal" in output
    calls = environment.calls
    show = ("docker", ("context", "show"))
    inspect = (
        "docker",
        ("context", "inspect", "--format", environment.doctor.CONTEXT_FORMAT, "desktop-linux"),
    )
    assert (
        calls.index(show)
        < calls.index(inspect)
        < calls.index(("docker", environment.doctor.DAEMON_ARGS))
    )
    assert "desktop-linux" not in output and "docker.sock" not in output


def test_t08_missing_config(environment, capsys):
    path = environment.root / ".env.test.local"
    path.unlink()
    assert invoke(environment, capsys)[0] == 0
    code, output = invoke(environment, capsys, "test")
    assert code == 1 and "FAIL          TEST_CONFIG" in output
    assert not path.exists()


@pytest.mark.parametrize(
    "fault", ["symlink", "dangling", "directory", "fifo", "mode", "special", "uid", "denied"]
)
def test_t09_config_lstat_only(environment, monkeypatch, capsys, fault):
    path = environment.root / ".env.test.local"
    if fault in ("symlink", "dangling", "directory", "fifo"):
        path.unlink()
        if fault in ("symlink", "dangling"):
            path.symlink_to(
                environment.root / (".env.dev.local" if fault == "symlink" else "absent")
            )
        elif fault == "directory":
            path.mkdir()
        else:
            os.mkfifo(path)
    elif fault in ("mode", "special"):
        path.chmod(0o644 if fault == "mode" else 0o4600)
    elif fault == "uid":
        monkeypatch.setattr(environment.doctor.os, "getuid", lambda: path.lstat().st_uid + 1)
    else:
        original = Path.lstat

        def lstat(candidate, *args, **kwargs):
            if candidate == path:
                raise PermissionError(SECRET)
            return original(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", lstat)
    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", lambda *a, **k: pytest.fail("Doctor opened a file"))
        guard.setattr(builtins, "open", lambda *a, **k: pytest.fail("Doctor read file contents"))
        code, output = invoke(environment, capsys, "test")
    assert code == (2 if fault == "denied" else 1)
    assert "TEST_CONFIG" in output


@pytest.mark.parametrize(
    "name",
    [
        "PGHOST",
        "PGSERVICE",
        "PG" + SECRET,
        "COMPOSE_FILE",
        "PITLAB_DATABASE_URL",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
        "DOCKER_" + SECRET,
    ],
)
@pytest.mark.parametrize("value", ["", SECRET])
def test_t10_routing_names_only(environment, capsys, name, value):
    environment.environ[name] = value
    assert invoke(environment, capsys)[0] == 0
    environment.calls.clear()
    code, output = invoke(environment, capsys, "test")
    assert code == 1 and "Restricted names present" in output
    assert not any(tool == "docker" for tool, _ in environment.calls)


def test_t10_mapping_values_never_read_for_routing(doctor):
    class NamesOnly(dict):
        def __getitem__(self, key):
            pytest.fail("Routing value read")

    result = doctor.routing_check(NamesOnly({"DOCKER_HOST": SECRET}))
    assert result.state == doctor.FAIL and SECRET not in result.reason


@pytest.mark.parametrize(
    "platform,sysname,machine,release,expected,wsl",
    [
        ("linux", "Linux", "x86_64", "generic", 0, "WSL2 not established"),
        ("linux", "Linux", "x86_64", "microsoft-standard-WSL2", 0, "WSL2 kernel signal only"),
        ("linux", "Linux", "x86_64", "Microsoft", 0, "WSL generation ambiguous"),
        ("darwin", "Darwin", "arm64", "mock", 0, ""),
        ("darwin", "Darwin", "x86_64", "mock-rosetta", 1, "native ARM64 not established"),
        ("linux", "Linux", "aarch64", "mock", 1, ""),
        ("unknown", "Unknown", "x86_64", "mock", 2, ""),
        ("linux", "Linux", "bad\narch", "mock", 2, ""),
    ],
)
def test_t11_platform_evidence(
    environment, monkeypatch, capsys, platform, sysname, machine, release, expected, wsl
):
    monkeypatch.setattr(environment.doctor.sys, "platform", platform)
    monkeypatch.setattr(
        environment.doctor.os,
        "uname",
        lambda: SimpleNamespace(sysname=sysname, machine=machine, release=release),
    )
    environment.environ["WSL_DISTRO_NAME"] = "not proof"
    code, output = invoke(environment, capsys)
    assert code == expected and wsl in output
    assert "macOS verified" not in output and "WSL2 verified" not in output


def test_ic02_missing_wsl_signal_preserves_linux_core(environment, monkeypatch, capsys):
    monkeypatch.setattr(
        environment.doctor.os,
        "uname",
        lambda: SimpleNamespace(sysname="Linux", machine="x86_64", release=None),
    )
    code, output = invoke(environment, capsys)
    assert code == 0 and "Kernel signal unavailable; Linux Core independent" in output


def test_t11_32_bit_process_refused(environment, monkeypatch, capsys):
    monkeypatch.setattr(environment.doctor.struct, "calcsize", lambda _: 4)
    assert invoke(environment, capsys)[0] == 1


@pytest.mark.parametrize("prior_fail", [False, True])
def test_t12_t20_interrupted_diagnosis_never_satisfies_test(environment, capsys, prior_fail):
    environment.responses[("git", ("--version",))] = RuntimeError(SECRET)
    if prior_fail:
        environment.responses[("uv", ("--version",))] = environment.doctor.Probe(issue="missing")
    code, output = invoke(environment, capsys, "test")
    assert code == (1 if prior_fail else 2)
    assert "Test prerequisites: indeterminate" in output


@pytest.mark.parametrize(
    "id,key,output",
    [
        ("GIT", ("git", ("--version",)), b"git version ???\n"),
        ("COMPOSE_V2", ("docker", ("compose", "version", "--short")), b"unknown\n"),
        ("DOCKER_DAEMON", ("docker", ("info", "--format", "{{.ServerVersion}}")), b"\xff\n"),
    ],
)
def test_t12_malformed_observations(environment, capsys, id, key, output):
    environment.responses[key] = environment.doctor.Probe(out=output)
    code, text = invoke(environment, capsys, "test")
    assert code == 2 and id in text and "NOT CHECKED" in text


@pytest.mark.parametrize("result", ["stdout", "stderr", "exception"])
def test_t13_hostile_diagnostics(environment, capsys, result):
    doctor = environment.doctor
    bad = {
        "stdout": doctor.Probe(out=b"uv 0.11.29 " + SECRET.encode()),
        "stderr": doctor.Probe(out=b"uv 0.11.29\n", err=SECRET.encode()),
        "exception": RuntimeError(SECRET),
    }
    environment.responses[("uv", ("--version",))] = bad[result]
    code, output = invoke(environment, capsys)
    assert code == 2 and "NOT CHECKED" in output and "Traceback" not in output


@pytest.mark.parametrize(
    "args,expected",
    [
        (["--help"], 0),
        (["--profile", "bad"], 64),
        ([SECRET], 64),
        (["--profile", "core", "--profile", "core"], 64),
        (["--help", "--profile", "core"], 64),
        (["--profile"], 64),
    ],
)
def test_t14_arguments_before_observations(environment, capsys, args, expected):
    assert environment.doctor.main(args) == expected
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err and "Usage:" in captured.out
    assert not environment.calls


def test_t15_t16_t18_t19_no_reads_writes_or_db(environment, monkeypatch, capsys):
    before = snapshot(environment.root), snapshot(environment.home)
    imported = builtins.__import__

    def import_guard(name, *args, **kwargs):
        assert not name.startswith(
            ("pit_research_lab", "sqlalchemy", "psycopg", "alembic", "database")
        )
        return imported(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Forbidden file, DB, network or process operation")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "__import__", import_guard)
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(io, "open", forbidden)
        guard.setattr(os, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        for name in ("chmod", "mkdir", "unlink", "rename", "replace", "remove"):
            guard.setattr(os, name, forbidden)
        first = invoke(environment, capsys, "test")
        second = invoke(environment, capsys, "test")
        assert first == second and first[0] == 0
    assert (snapshot(environment.root), snapshot(environment.home)) == before
    assert not any("database.py" in argument for _, args in environment.calls for argument in args)
    tree = ast.parse(SOURCE.read_text())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"eval", "exec", "load_config", "probe_database"}
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports <= {
        "__future__",
        "os",
        "re",
        "selectors",
        "shutil",
        "stat",
        "struct",
        "subprocess",
        "sys",
        "time",
        "pathlib",
        "typing",
    }


def test_t17_core_summary_independent(environment, capsys):
    environment.responses[("docker", environment.doctor.DAEMON_ARGS)] = environment.doctor.Probe(
        issue="missing"
    )
    code, output = invoke(environment, capsys, "test")
    assert code == 1 and "Core prerequisites: satisfied" in output
    assert "Test prerequisites: incomplete (failure)" in output


@pytest.mark.parametrize(
    "states", list(itertools.product(["PASS", "WARN", "FAIL", "NOT CHECKED"], repeat=3))
)
def test_t20_aggregation(doctor, states):
    checks = [
        doctor.Check("A", states[0], "fixture"),
        doctor.Check("B", states[1], "fixture"),
        doctor.Check("OPTIONAL", states[2], "fixture", False),
        doctor.Check("DB_RUNTIME", doctor.NC, "excluded", False),
    ]
    required = states[:2]
    expected = 1 if "FAIL" in required else (0 if required == ("PASS", "PASS") else 2)
    assert doctor.exit_code(checks) == expected


def test_t19_child_environment(doctor):
    ambient = {
        "PATH": "/fixture/bin",
        "HOME": "/fixture/home",
        "WSL_INTEROP": "/fixture/interop",
        "PGHOST": SECRET,
        "DOCKER_HOST": SECRET,
        "GIT_CONFIG_COUNT": "1",
        "PYTHONPATH": SECRET,
        "UNRELATED_TOKEN": SECRET,
    }
    for tool in ("uv", "git", "docker"):
        child = doctor.child_environment(tool, ambient)
        assert SECRET not in child.values()
        assert child["LANG"] == child["LC_ALL"] == "C"
        assert child["PATH"] == ambient["PATH"]
        assert ("HOME" in child) == (tool == "docker")
        assert ("WSL_INTEROP" in child) == (tool == "docker")
    git = doctor.child_environment("git", ambient)
    assert git["GIT_OPTIONAL_LOCKS"] == "0" and git["GIT_CONFIG_GLOBAL"] == "/dev/null"


@pytest.mark.parametrize(
    "tool,args,budget",
    [
        ("uv", ("--version",), 3),
        ("docker", ("info", "--format", "{{.ServerVersion}}"), 5),
        (
            "docker",
            ("context", "inspect", "--format", "{{.Endpoints.docker.Host}}", "desktop-linux"),
            3,
        ),
    ],
)
def test_ic03_deadlines_and_context_allowlist(doctor, monkeypatch, tmp_path, tool, args, budget):
    real_popen = subprocess.Popen
    waits, children = [], []
    monkeypatch.setattr(doctor.shutil, "which", lambda *a, **k: "/fixture/tool")

    def popen(argv, **kwargs):
        assert argv == ["/fixture/tool", *args]
        child = real_popen(
            [sys.executable, "-I", "-S", "-B", "-c", "import os; os.write(1,b'observation\\n')"],
            **kwargs,
        )
        wait = child.wait

        def record_wait(*a, **k):
            waits.append(k.get("timeout"))
            return wait(*a, **k)

        child.wait = record_wait
        children.append(child)
        return child

    monkeypatch.setattr(doctor.subprocess, "Popen", popen)
    context = "desktop-linux" if args[:2] == ("context", "inspect") else None
    result = doctor.run_probe(tool, args, tmp_path, {}, context=context)
    assert result.code == 0 and result.out == b"observation\n" and not result.issue
    assert 0 < waits[0] <= budget and waits[-1] is None
    assert children[0].poll() is not None


@pytest.mark.parametrize(
    "tool,args,context",
    [
        ("uv", ("sync",), None),
        ("git", ("status",), None),
        ("make", ("db-test-preflight",), None),
        ("python", ("scripts/database.py", "preflight", "test"), None),
        ("docker", ("ps",), None),
        ("docker", ("volume", "ls"), None),
        ("docker", ("compose", "config"), None),
        ("docker", ("context", "use", "default"), None),
        ("docker", ("context", "inspect", "--format", "{{.Endpoints.docker.Host}}"), None),
        (
            "docker",
            ("context", "inspect", "--format", "{{.Endpoints.docker.Host}}", "--help"),
            "--help",
        ),
        (
            "docker",
            ("context", "inspect", "--format", "{{.Endpoints.docker.Host}}", "other"),
            "default",
        ),
    ],
)
def test_t18_t19_closed_allowlist(doctor, monkeypatch, tmp_path, tool, args, context):
    monkeypatch.setattr(
        doctor.subprocess, "Popen", lambda *a, **k: pytest.fail("Forbidden child created")
    )
    result = doctor.run_probe(tool, args, tmp_path, {}, context=context)
    assert result.issue == "forbidden" and result.out == result.err == b""


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("success", ""),
        ("stdout-overflow", "overflow"),
        ("stderr-overflow", "overflow"),
        ("both-overflow", "overflow"),
        ("both-stall", "timeout"),
        ("closed-stall", "timeout"),
    ],
)
def test_ic03_t12_t19_bounded_runner(doctor, monkeypatch, tmp_path, mode, expected):
    code = {
        "success": "import os; os.write(1, b'uv 0.11.29\\n'); os.write(2, b'note')",
        "stdout-overflow": "import os,time; os.write(2,b'note'); os.write(1,b'x'*100000); time.sleep(60)",
        "stderr-overflow": "import os,time; os.write(1,b'note'); os.write(2,b'x'*100000); time.sleep(60)",
        "both-overflow": "import os,time; [os.write(fd,b'x'*1024) for _ in range(8) for fd in (1,2)]; time.sleep(60)",
        "both-stall": "import os,time; [os.write(fd,b'x'*4096) for fd in (1,2)]; time.sleep(60)",
        "closed-stall": "import os,time; os.close(1); os.close(2); time.sleep(60)",
    }[mode]
    real_popen = subprocess.Popen
    children, observed = [], []
    monkeypatch.setattr(doctor.shutil, "which", lambda *a, **k: "/fixture/uv")

    def popen(args, **kwargs):
        assert args == ["/fixture/uv", "--version"]
        assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["cwd"] == tmp_path
        assert kwargs["env"] == {"PATH": "/fixture", "LANG": "C", "LC_ALL": "C"}
        observed.append(kwargs)
        child = real_popen([sys.executable, "-I", "-S", "-B", "-c", code], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(doctor.subprocess, "Popen", popen)
    before = snapshot(tmp_path)
    result = doctor.run_probe("uv", ("--version",), tmp_path, {"PATH": "/fixture", "TOKEN": SECRET})
    assert result.issue == expected
    assert len(children) == len(observed) == 1
    child = children[0]
    assert child.poll() is not None and child.stdout.closed and child.stderr.closed
    if expected:
        assert child.returncode < 0 and result.out == result.err == b""
    else:
        assert result.out == b"uv 0.11.29\n" and result.err == b"note"
    assert snapshot(tmp_path) == before


def shell_fixture(tmp_path):
    scripts = tmp_path / "checkout with spaces/scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "doctor.sh"
    launcher.write_bytes(LAUNCHER.read_bytes())
    (scripts / "environment_doctor.py").write_bytes(SOURCE.read_bytes())
    binaries = tmp_path / "bin"
    binaries.mkdir()
    return launcher, binaries


def shell_run(launcher, binaries, args=()):
    return subprocess.run(
        ["/bin/sh", str(launcher), *args],
        cwd=binaries.parent,
        env={"PATH": str(binaries), "HOME": str(binaries.parent)},
        capture_output=True,
        text=True,
        shell=False,
        timeout=10,
    )


def stub(binaries, name, body):
    path = binaries / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o700)


def test_t02_shell_missing_python(tmp_path):
    launcher, binaries = shell_fixture(tmp_path)
    before = snapshot(tmp_path)
    result = shell_run(launcher, binaries)
    assert result.returncode == 1 and "Python 3.12 missing" in result.stdout
    assert result.stderr == "" and snapshot(tmp_path) == before


@pytest.mark.parametrize("preferred", [True, False])
def test_t02_shell_preference_and_flags(tmp_path, preferred):
    launcher, binaries = shell_fixture(tmp_path)
    body = (
        '[ "$1" = -I ] && [ "$2" = -S ] && [ "$3" = -B ] || exit 99\n'
        '[ "$4" = "' + str(launcher.parent / "environment_doctor.py") + '" ] || exit 99\n'
        '[ "$5" = --profile ] && [ "$6" = core ] || exit 99\n'
        "printf '%s\\n' 'selected interpreter'\nexit 0\n"
    )
    stub(binaries, "python3.12" if preferred else "python3", body)
    if preferred:
        stub(binaries, "python3", "printf '%s' 'wrong fallback'\nexit 99\n")
    result = shell_run(launcher, binaries)
    assert (
        result.returncode == 0 and result.stdout == "selected interpreter\n" and result.stderr == ""
    )


@pytest.mark.parametrize("exit_status,expected", [(1, 1), (2, 2), (64, 64), (127, 1), (99, 2)])
def test_t02_shell_broken_preferred_no_fallback(tmp_path, exit_status, expected):
    launcher, binaries = shell_fixture(tmp_path)
    stub(
        binaries,
        "python3.12",
        "printf '%s' 'synthetic secret' >&2\nexit " + str(exit_status) + "\n",
    )
    stub(binaries, "python3", "printf '%s' 'wrong fallback'\nexit 0\n")
    result = shell_run(launcher, binaries)
    assert result.returncode == expected and "wrong fallback" not in result.stdout
    assert "synthetic secret" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "args,expected",
    [
        (("--help",), 0),
        ((SECRET,), 64),
        (("--profile", "bad"), 64),
        (("--profile", "core", "--profile", "test"), 64),
        (("--help", "--profile", "test"), 64),
    ],
)
def test_t14_shell_no_probe(tmp_path, args, expected):
    launcher, binaries = shell_fixture(tmp_path)
    stub(binaries, "python3.12", "printf '%s' 'UNEXPECTED PROBE'\nexit 99\n")
    result = shell_run(launcher, binaries, args)
    assert result.returncode == expected and "Usage:" in result.stdout
    assert "UNEXPECTED PROBE" not in result.stdout and SECRET not in result.stdout + result.stderr


def test_t16_direct_and_launcher_no_site_or_bytecode(tmp_path):
    launcher, binaries = shell_fixture(tmp_path)
    # Test current interpreter without venv/site/project dependencies; no real tools.
    interpreter = str(Path(sys.executable).resolve())
    stub(binaries, "python3.12", 'exec "' + interpreter + '" "$@"\n')
    (binaries / "typing.py").write_text("raise RuntimeError('untrusted import')\n")
    (binaries / "sitecustomize.py").write_text("raise RuntimeError('site initialization')\n")
    before = snapshot(tmp_path)
    first = shell_run(launcher, binaries)
    second = shell_run(launcher, binaries)
    direct = subprocess.run(
        [interpreter, "-I", "-S", "-B", str(launcher.parent / "environment_doctor.py")],
        cwd=tmp_path,
        env={"PATH": str(binaries), "PYTHONPATH": str(binaries)},
        capture_output=True,
        text=True,
        shell=False,
        timeout=10,
    )
    assert first.returncode == second.returncode == direct.returncode == 1
    assert first.stdout == second.stdout
    assert "Core prerequisites: incomplete (failure)" in direct.stdout
    assert "Doctor did not complete successfully" in first.stdout
    assert direct.stderr == first.stderr == second.stderr == ""
    assert snapshot(tmp_path) == before


def test_t01_t16_standalone_positive_fixture(environment, tmp_path):
    binaries = tmp_path / "tools"
    binaries.mkdir()
    interpreter = str(Path(sys.executable).resolve())
    stub(binaries, "python3.12", 'exec "' + interpreter + '" "$@"\n')
    stub(binaries, "uv", "[ \"$*\" = --version ] || exit 99\nprintf '%s\\n' 'uv 0.11.29'\n")
    git_body = (
        'case "$*" in\n'
        '"--version") printf "%s\\n" "git version 2.43.0" ;;\n'
        '"--no-optional-locks -c core.fsmonitor=false rev-parse --is-inside-work-tree") printf "true\\n" ;;\n'
        '"--no-optional-locks -c core.fsmonitor=false rev-parse --show-toplevel") printf "%s\\n" "'
        + str(environment.root)
        + '" ;;\n*) exit 99 ;;\nesac\n'
    )
    stub(binaries, "git", git_body)
    stub(
        binaries,
        "docker",
        (
            'case "$*" in\n'
            '"--version") printf "%s\\n" "Docker version 28.2.2, build abc1234" ;;\n'
            '"compose version --short") printf "%s\\n" "2.39.1" ;;\n'
            '"context show") printf "%s\\n" "desktop-linux" ;;\n'
            '"context inspect --format {{.Endpoints.docker.Host}} desktop-linux") printf "%s\\n" "unix:///fixture/docker.sock" ;;\n'
            '"info --format {{.ServerVersion}}") printf "%s\\n" "28.2.2" ;;\n'
            "*) exit 99 ;;\nesac\n"
        ),
    )
    before = snapshot(tmp_path)
    results = []
    for _ in range(2):
        result = subprocess.run(
            ["/bin/sh", str(environment.root / "scripts/doctor.sh"), "--profile", "test"],
            cwd=tmp_path,
            env={"PATH": str(binaries), "HOME": str(environment.home)},
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
        )
        assert result.returncode == 0 and result.stderr == ""
        assert "Core prerequisites: satisfied" in result.stdout
        assert "Test prerequisites: satisfied" in result.stdout
        assert "NOT CHECKED   DB_RUNTIME" in result.stdout
        assert SECRET not in result.stdout and str(environment.home) not in result.stdout
        results.append(result.stdout)
    assert results[0] == results[1] and snapshot(tmp_path) == before
