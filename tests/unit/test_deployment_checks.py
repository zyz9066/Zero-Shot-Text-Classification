from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
import urllib3
import yaml
from minio.error import InvalidResponseError, S3Error, ServerError

from app.config.settings import MinIOServiceSettings
from scripts import check_deployment as checks


@pytest.fixture
def local_launcher(tmp_path: Path) -> tuple[Path, Path, str]:
    if os.name != "nt":
        pytest.skip("local launcher targets Windows")
    shell = shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is required to exercise the local launcher")
    root = tmp_path / "project"
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).resolve().parents[2] / "scripts" / "local.ps1",
        root / "scripts" / "local.ps1",
    )
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        """
$global:answers = [System.Collections.Generic.Queue[string]]::new()
foreach ($line in [IO.File]::ReadAllLines($env:TEST_ANSWERS)) {
    $global:answers.Enqueue($line)
}
function Read-Host { param($Prompt) return $global:answers.Dequeue() }
function Get-Credential {
    param($Message)
    if ($env:TEST_CANCEL_CREDENTIAL -eq '1') { return $null }
    $credential = [PSCustomObject]@{ UserName = $env:TEST_USER }
    $credential | Add-Member -MemberType ScriptMethod -Name GetNetworkCredential `
        -Value { return [PSCustomObject]@{ Password = $env:TEST_SECRET } }
    return $credential
}
function uv {
    Add-Content -LiteralPath $env:TEST_LOG -Value ('uv ' + ($args -join ' '))
    $global:LASTEXITCODE = if ($env:TEST_UV_FAIL -eq '1') { 1 } else { 0 }
}
function docker {
    Add-Content -LiteralPath $env:TEST_LOG -Value ('docker ' + ($args -join ' '))
    if (($args -contains 'up') -and ($args -notcontains 'app')) {
        if ($env:MINIO_ACCESS_KEY -ne $env:TEST_USER -or
            $env:MINIO_SECRET_KEY -ne $env:TEST_SECRET) {
            throw 'App credentials were not passed to Compose.'
        }
    }
    $global:LASTEXITCODE = if ($env:TEST_DOCKER_FAIL -eq '1') { 1 } else { 0 }
}
try {
    & (Join-Path $env:TEST_ROOT 'scripts/local.ps1') $env:TEST_ACTION
    if ($env:MINIO_ACCESS_KEY -ne 'original-access' -or
        $env:MINIO_SECRET_KEY -ne 'original-secret') {
        throw 'Caller environment was not restored.'
    }
} catch {
    Write-Error $_
    exit 1
}
""",
        encoding="utf-8",
    )
    return root, harness, shell


def run_local_launcher(
    launcher: tuple[Path, Path, str],
    action: str,
    answers: list[str] | None = None,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    root, harness, shell = launcher
    answers_file = root.parent / "answers.txt"
    answers_file.write_text("\n".join(answers or []) + "\n", encoding="utf-8")
    env = os.environ.copy()
    for key in (
        "MINIO_LICENSE_FILE",
        "MINIO_ROOT_USER_FILE",
        "MINIO_ROOT_PASSWORD_FILE",
        "MINIO_BUCKET",
    ):
        env.pop(key, None)
    env.update(
        TEST_ROOT=str(root),
        TEST_ACTION=action,
        TEST_ANSWERS=str(answers_file),
        TEST_LOG=str(root.parent / "commands.txt"),
        TEST_USER="test-access-" + uuid4().hex,
        TEST_SECRET="test-secret-" + uuid4().hex,
        MINIO_ACCESS_KEY="original-access",
        MINIO_SECRET_KEY="original-secret",
        **overrides,
    )
    return subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-File", str(harness)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_local_launcher_setup_start_and_non_destructive_lifecycle(
    local_launcher: tuple[Path, Path, str],
) -> None:
    root, _, _ = local_launcher
    paths = [str(root.parent / name) for name in ("license", "user", "password")]
    result = run_local_launcher(
        local_launcher, "start", [*paths, "zeroshot-learning-test"]
    )
    assert result.returncode == 0, result.stderr
    config = (root / ".env").read_text(encoding="utf-8")
    assert all(path in config for path in paths)
    assert "MINIO_BUCKET='zeroshot-learning-test'" in config
    assert "MINIO_ACCESS_KEY" not in config and "MINIO_SECRET_KEY" not in config
    assert "test-secret-" not in result.stdout + result.stderr + config
    commands = (root.parent / "commands.txt").read_text(encoding="utf-8")
    assert "config --quiet" in commands and "up -d --build" in commands
    assert "readiness is not yet verified" in result.stdout

    for action in ("stop", "status", "check"):
        result = run_local_launcher(local_launcher, action)
        assert result.returncode == 0, result.stderr
    commands = (root.parent / "commands.txt").read_text(encoding="utf-8")
    assert " stop" in commands and " ps" in commands
    assert "storage --write-probe" in commands
    assert "--volumes" not in commands
    assert (root / ".env").read_text(encoding="utf-8") == config


def test_local_launcher_preserves_existing_config_and_stops_on_failures(
    local_launcher: tuple[Path, Path, str],
) -> None:
    root, _, _ = local_launcher
    config = "MINIO_BUCKET='existing-bucket'\n"
    (root / ".env").write_text(config, encoding="utf-8")
    result = run_local_launcher(local_launcher, "start", TEST_UV_FAIL="1")
    assert result.returncode != 0
    assert (root / ".env").read_text(encoding="utf-8") == config
    assert "docker " not in (root.parent / "commands.txt").read_text(encoding="utf-8")
    result = run_local_launcher(local_launcher, "start", TEST_CANCEL_CREDENTIAL="1")
    assert result.returncode != 0
    assert (root / ".env").read_text(encoding="utf-8") == config
    assert "docker " not in (root.parent / "commands.txt").read_text(encoding="utf-8")
    result = run_local_launcher(local_launcher, "start", TEST_DOCKER_FAIL="1")
    assert result.returncode != 0
    assert "Docker Compose failed" in result.stderr
    assert "test-secret-" not in result.stdout + result.stderr
    assert (root / ".env").read_text(encoding="utf-8") == config


def test_local_launcher_failed_setup_and_app_only(
    local_launcher: tuple[Path, Path, str],
) -> None:
    root, _, _ = local_launcher
    paths = [str(root.parent / name) for name in ("license", "user", "password")]
    result = run_local_launcher(local_launcher, "start", paths, TEST_UV_FAIL="1")
    assert result.returncode != 0
    assert not (root / ".env").exists()
    result = run_local_launcher(local_launcher, "start", ["C:relative", *paths[1:], ""])
    assert result.returncode != 0
    assert "absolute paths" in result.stderr
    assert not (root / ".env").exists()
    result = run_local_launcher(local_launcher, "app")
    assert result.returncode == 0, result.stderr
    assert not (root / ".env").exists()
    commands = (root.parent / "commands.txt").read_text(encoding="utf-8")
    assert "up -d --build app" in commands
    assert "compose.minio.yaml" not in commands


def test_local_launcher_config_is_accepted_by_real_preflight(
    local_launcher: tuple[Path, Path, str],
) -> None:
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is required to exercise dotenv preflight")
    root, _, _ = local_launcher
    files = [root.parent / f"local $ {name}" for name in ("license", "user", "secret")]
    for path in files:
        path.write_text("test-value", encoding="utf-8")
    result = run_local_launcher(
        local_launcher, "start", [*(str(path) for path in files), ""]
    )
    assert result.returncode == 0, result.stderr
    env = os.environ.copy()
    for name in (
        "MINIO_LICENSE_FILE",
        "MINIO_ROOT_USER_FILE",
        "MINIO_ROOT_PASSWORD_FILE",
    ):
        env.pop(name, None)
    result = subprocess.run(
        [
            uv,
            "run",
            "--no-sync",
            "--project",
            str(Path(__file__).resolve().parents[2]),
            "--env-file",
            ".env",
            "--locked",
            "python",
            str(
                Path(__file__).resolve().parents[2] / "scripts" / "check_deployment.py"
            ),
            "preflight",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["outcome"] == "ready"
    assert "MINIO_BUCKET='zeroshot_learning_output'" in (root / ".env").read_text(
        encoding="utf-8"
    )


class Client:
    def __init__(self) -> None:
        self.content = b""
        self.puts = 0
        self.removed: list[str] = []
        self.put_error: Exception | None = None
        self.bucket_error: Exception | None = None
        self.read_error: Exception | None = None
        self.cleanup_error: Exception | None = None
        self.corrupt = False

    def bucket_exists(self, name: str) -> bool:
        if self.bucket_error:
            raise self.bucket_error
        return True

    def make_bucket(self, name: str) -> None:
        raise AssertionError("Existing bucket must not be recreated")

    def put_object(
        self, bucket: str, key: str, data: BytesIO, length: int, content_type: str
    ) -> None:
        self.puts += 1
        self.content = data.read()
        if self.put_error:
            raise self.put_error

    def get_object(self, bucket: str, key: str) -> urllib3.response.HTTPResponse:
        if self.read_error:
            raise self.read_error
        data = self.content + b"extra" if self.corrupt else self.content
        return urllib3.response.HTTPResponse(body=BytesIO(data), preload_content=False)

    def remove_object(self, bucket: str, key: str) -> None:
        if self.cleanup_error:
            raise self.cleanup_error
        self.removed.append(key)


def settings() -> MinIOServiceSettings:
    return MinIOServiceSettings(
        endpoint="minio:9000",
        secure=False,
        access_key=uuid4().hex,
        secret_key=uuid4().hex,
        bucket="zeroshot-learning-test",
    )


def test_probe_acknowledges_reads_and_cleans_only_owned_key() -> None:
    client = Client()
    result = checks.storage(settings(), client)
    assert result.outcome == "ready"
    assert client.puts == 1
    assert client.removed == [result.object_key]
    assert result.object_key.startswith("healthchecks/")
    assert not result.object_key.startswith("predictions/")
    assert json.loads(client.content)["probe_id"] == result.probe_id


@pytest.mark.parametrize("error", [TimeoutError(), urllib3.exceptions.ProtocolError()])
def test_uncertain_put_is_never_retried_or_deleted(error: Exception) -> None:
    client = Client()
    client.put_error = error
    result = checks.storage(settings(), client)
    assert result.outcome == "indeterminate"
    assert result.reason_code == "write_uncertain"
    assert client.puts == 1 and not client.removed
    assert result.object_key and "retry" in result.next_action.lower()


def test_authoritative_rejection_is_not_license_guess_or_uncertainty() -> None:
    client = Client()
    client.put_error = S3Error(
        response=urllib3.response.HTTPResponse(status=403),
        code="AccessDenied",
        message=uuid4().hex,
        resource=None,
        request_id=None,
        host_id=None,
    )
    result = checks.storage(settings(), client)
    assert result.outcome == "rejected"
    assert result.reason_code == "access_denied"
    assert not client.removed


@pytest.mark.parametrize("status", [500, 503, 0])
def test_s3_put_without_authoritative_rejection_retains_uncertain_identity(
    status: int,
) -> None:
    client = Client()
    token = uuid4().hex
    client.put_error = S3Error(
        response=urllib3.response.HTTPResponse(status=status, body=token.encode()),
        code="InternalError",
        message=token,
        resource=token,
        request_id=token,
        host_id=token,
    )
    result = checks.storage(settings(), client)
    assert result.outcome == "indeterminate"
    assert result.reason_code == "write_uncertain"
    assert client.puts == 1 and not client.removed
    assert (
        result.probe_id and result.object_key == f"healthchecks/{result.probe_id}.json"
    )
    assert "absence and definitive non-completion" in result.next_action
    assert token not in json.dumps(result.to_dict())


@pytest.mark.parametrize("phase", ["bucket", "put"])
@pytest.mark.parametrize("kind", ["html", "server"])
def test_sdk_protocol_failures_never_leak_body_or_retry(phase: str, kind: str) -> None:
    token = uuid4().hex
    error = (
        InvalidResponseError(200, "text/html", token)
        if kind == "html"
        else ServerError(token, 503)
    )
    client = Client()
    if phase == "bucket":
        client.bucket_error = error
    else:
        client.put_error = error
    result = checks.storage(settings(), client)
    assert result.outcome == ("unavailable" if phase == "bucket" else "indeterminate")
    assert token not in json.dumps(result.to_dict())
    assert not client.removed
    assert client.puts == (0 if phase == "bucket" else 1)


@pytest.mark.parametrize("mode", ["mismatch", "read", "cleanup", "both"])
def test_acknowledged_readback_failure_still_cleans_and_retains_errors(
    mode: str,
) -> None:
    client = Client()
    client.corrupt = mode == "mismatch"
    if mode in {"read", "both"}:
        client.read_error = TimeoutError()
    if mode in {"cleanup", "both"}:
        client.cleanup_error = TimeoutError()
    result = checks.storage(settings(), client)
    assert result.outcome != "ready"
    assert client.puts == 1
    if mode in {"mismatch", "read"}:
        assert client.removed == [result.object_key]
    else:
        assert result.outcome == "cleanup_failed"
    if mode == "both":
        assert "readback" in result.reason_code and "cleanup" in result.reason_code


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "newline", "valid"])
def test_preflight_file_inputs_are_checked_without_disclosure(
    tmp_path: Path, kind: str
) -> None:
    token = uuid4().hex
    license_file = tmp_path / token
    user = tmp_path / "user"
    password = tmp_path / "password"
    user.write_text(uuid4().hex)
    password.write_text(uuid4().hex)
    if kind == "directory":
        license_file.mkdir()
    elif kind != "missing":
        license_file.write_text("" if kind == "empty" else uuid4().hex)
    if kind == "newline":
        password.write_text(uuid4().hex + "\n")
    result = checks.preflight(
        {
            "MINIO_LICENSE_FILE": str(license_file),
            "MINIO_ROOT_USER_FILE": str(user),
            "MINIO_ROOT_PASSWORD_FILE": str(password),
        }
    )
    assert (result.outcome == "ready") == (kind == "valid")
    output = json.dumps(result.to_dict())
    assert token not in output and str(tmp_path) not in output
    assert password.read_text() not in output


def test_configuration_error_names_setting_not_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ["MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_SECURE", "false")
    assert checks.main(["storage", "--write-probe"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "configuration_error"
    assert "MINIO_ACCESS_KEY" in result["next_action"]


def test_health_is_bounded_and_does_not_accept_console_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class Http:
        def request(
            self, method: str, url: str, **kwargs: object
        ) -> urllib3.response.HTTPResponse:
            calls.append((method, url))
            return urllib3.response.HTTPResponse(
                status=200, headers={"Content-Type": "text/html"}, body=b"console"
            )

        def clear(self) -> None:
            pass

    def factory(**kwargs: object) -> Http:
        assert kwargs["retries"] is False
        assert kwargs["timeout"] == 5.0
        return Http()

    monkeypatch.setattr(checks.urllib3, "PoolManager", factory)
    result = checks.health("minio", "http://minio:9000")
    assert result.outcome == "unavailable"
    assert calls == [("HEAD", "http://minio:9000/minio/health/live")]


@pytest.mark.parametrize(
    "url", ["file:///private", "http://user:password@host", "http://host/?secret"]
)
def test_health_rejects_unsafe_url_without_echoing_it(url: str) -> None:
    result = checks.health("app", url)
    assert result.outcome == "configuration_error"
    assert url not in json.dumps(result.to_dict())


def test_bucket_rejection_never_silently_renames_or_writes() -> None:
    client = Client()

    def reject(name: str) -> bool:
        assert name == "zeroshot_learning_output"
        raise S3Error(
            response=urllib3.response.HTTPResponse(status=400),
            code="InvalidBucketName",
            message=uuid4().hex,
            resource=None,
            request_id=None,
            host_id=None,
        )

    client.bucket_exists = reject
    original = settings()
    result = checks.storage(
        replace(original, bucket="zeroshot_learning_output"), client
    )
    assert result.reason_code == "invalid_bucket"
    assert client.puts == 0 and not client.removed


@pytest.mark.parametrize("failure", ["tls", "timeout"])
def test_health_transport_failure_is_safe_and_explicit(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    token = uuid4().hex

    class Http:
        def request(self, *args: object, **kwargs: object) -> None:
            if failure == "tls":
                raise urllib3.exceptions.SSLError(token)
            raise TimeoutError(token)

        def clear(self) -> None:
            pass

    monkeypatch.setattr(checks.urllib3, "PoolManager", lambda **kwargs: Http())
    result = checks.health("app")
    assert result.outcome == "unavailable"
    assert token not in json.dumps(result.to_dict())
    assert result.reason_code == ("tls" if failure == "tls" else "transport")


def test_preflight_unreadable_file_does_not_expose_os_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / uuid4().hex
    path.write_bytes(uuid4().bytes)
    secret = uuid4().hex

    def deny(*args: object, **kwargs: object) -> None:
        raise PermissionError(secret)

    monkeypatch.setattr(Path, "open", deny)
    result = checks.preflight({"MINIO_LICENSE_FILE": str(path)})
    assert result.outcome == "configuration_error"
    assert "unreadable" in result.reason_code
    assert secret not in json.dumps(result.to_dict())


@pytest.mark.parametrize("gate", ["lint", "format", "type", "test"])
def test_required_tools_fail_on_real_disposable_regressions(
    tmp_path: Path, gate: str
) -> None:
    source = tmp_path / "regression.py"
    sources = {
        "lint": "import os\n",
        "format": "value=1\n",
        "type": "def result() -> int:\n    return 'wrong type'\n",
        "test": "def test_regression():\n    assert False\n",
    }
    source.write_text(sources[gate])
    commands = {
        "lint": ["ruff", "check", str(source)],
        "format": ["ruff", "format", "--check", str(source)],
        "type": [
            "mypy",
            "--strict",
            "--cache-dir",
            str(tmp_path / "mypy"),
            str(source),
        ],
        "test": ["pytest", str(source), "-q"],
    }
    result = subprocess.run(
        [sys.executable, "-m", *commands[gate]],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=60,
    )
    assert result.returncode == 1, f"{gate} did not report the intended regression"
    markers = {
        "lint": "F401",
        "format": "would be reformatted",
        "type": "[return-value]",
        "test": "FAILED",
    }
    assert markers[gate] in result.stdout


@pytest.mark.skipif(sys.platform != "linux", reason="CI shell fixtures target Linux")
@pytest.mark.parametrize(
    ("provided", "exit_code"), [(False, 0), (False, 7), (True, 0), (True, 7)]
)
def test_actual_ci_storage_script_eligibility_and_nonzero_propagation(
    tmp_path: Path, provided: bool, exit_code: int
) -> None:
    workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    steps = yaml.safe_load(workflow.read_text())["jobs"]["prediction-storage"]["steps"]
    script = next(
        step["run"]
        for step in steps
        if step.get("name") == "Run eligible isolated storage validation"
    )
    assert shutil.which("bash")
    tool = tmp_path / "uv"
    tool.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    tool.chmod(0o700)
    token = uuid4().hex if provided else ""
    summary = tmp_path / "summary"
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "AISTOR_TEST_LICENSE": token,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    result = subprocess.run(
        ["bash", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == exit_code
    assert not token or token not in result.stdout + result.stderr
    assert ("SKIPPED:" in result.stdout) == (not provided)
    assert not (tmp_path / "zeroshot-aistor-test.license").exists()


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize(
    "boundary",
    ["docker", "helper", "helper-exit", "helper-cleanup", "constructor", "credentials"],
)
def test_deployment_failure_reports_exclude_credentials(
    tmp_path: Path, verbose: bool, boundary: str
) -> None:
    __tracebackhide__ = True
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "test_reporting.py"
    source.write_text(
        "import importlib.util,json,os,subprocess\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        f"spec=importlib.util.spec_from_file_location('deployment',"
        f"{str(root / 'tests' / 'integration' / 'test_deployment.py')!r})\n"
        "deployment=importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(deployment)\n"
        "def test_failed_operation(monkeypatch,tmp_path):\n"
        "    env=deployment.environment()\n"
        "    env['MINIO_ACCESS_KEY']=os.environ['REPORT_ACCESS']\n"
        "    env['MINIO_SECRET_KEY']=os.environ['REPORT_SECRET']\n"
        "    def fail(*args,**kwargs):\n"
        "        __tracebackhide__=True\n"
        f"        if {boundary in {'helper-exit', 'helper-cleanup'}}:\n"
        "            operation=args[0][1]\n"
        "            if operation=='create':\n"
        "                return subprocess.CompletedProcess(args,0,'owned-helper','')\n"
        "            if operation=='inspect':\n"
        "                return subprocess.CompletedProcess(args,0,json.dumps([{\n"
        "                    'Config':{'Env':[os.environ['REPORT_SECRET']],"
        "'Labels':{'com.docker.compose.project':'test-project'}},\n"
        "                    'HostConfig':{'NetworkMode':'none',"
        "'PortBindings':{}}}]),'')\n"
        "            if operation=='wait':\n"
        "                return subprocess.CompletedProcess(args,0,'7','')\n"
        "            if operation=='logs':\n"
        "                return subprocess.CompletedProcess(args,0,"
        "os.environ['REPORT_SECRET'],'')\n"
        f"            if operation=='start' or (operation=='rm' and "
        f"{boundary == 'helper-exit'}):\n"
        "                return subprocess.CompletedProcess(args,0,'','')\n"
        "        return subprocess.CompletedProcess(args,1,"
        "os.environ['REPORT_SECRET'],os.environ['REPORT_ACCESS'])\n"
        "    monkeypatch.setattr(deployment.subprocess,'run',fail)\n"
        f"    if {boundary == 'docker'}:\n"
        "        deployment.docker('build',env=env)\n"
        f"    elif {boundary in {'helper', 'helper-exit', 'helper-cleanup'}}:\n"
        "        deployment.run_owned('test-project','fixture:local',env=env)\n"
        f"    elif {boundary == 'credentials'}:\n"
        "        monkeypatch.setattr(deployment,'docker',lambda *args,**kwargs:'')\n"
        "        monkeypatch.setattr(deployment,'uuid4',"
        "lambda:SimpleNamespace(hex=os.environ['REPORT_SECRET']))\n"
        "        monkeypatch.setattr(deployment,'preflight',"
        "lambda env:SimpleNamespace(outcome='rejected'))\n"
        "        deployment.Deployment({'project':'test-project',"
        "'runtime':'fixture:local','validation':'fixture:local'},tmp_path,"
        "tmp_path/'license')\n"
        "    else:\n"
        "        monkeypatch.setattr(deployment,'environment',lambda:env)\n"
        "        deployment.Deployment({'project':'test-project',"
        "'runtime':'fixture:local','validation':'fixture:local'},tmp_path)\n"
    )
    report = tmp_path / "report.xml"
    env = {
        **os.environ,
        "PYTHONPATH": str(root),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "REPORT_ACCESS": uuid4().hex,
        "REPORT_SECRET": uuid4().hex,
    }
    args = ["-vv", "--showlocals", "--tb=long"] if verbose else ["-q"]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(source), *args, f"--junitxml={report}"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr + report.read_text(encoding="utf-8")
    if any(env[key] in output for key in ["REPORT_ACCESS", "REPORT_SECRET"]):
        pytest.fail(
            "Generated credential disclosed in pytest output/artifact", pytrace=False
        )
    assert result.returncode == 1
    expected = (
        "exit 7"
        if boundary.startswith("helper-")
        else "preflight"
        if boundary == "credentials"
        else "exit 1"
    )
    assert expected in output


@pytest.fixture
def deployment_helpers() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "integration" / "test_deployment.py"
    spec = importlib.util.spec_from_file_location("deployment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("operation", ["build", "start"])
def test_docker_failure_has_safe_category_and_recovery(
    monkeypatch: pytest.MonkeyPatch, deployment_helpers: ModuleType, operation: str
) -> None:
    token = uuid4().hex

    def fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, token, "permission denied " + token)

    monkeypatch.setattr(deployment_helpers.subprocess, "run", fail)
    with pytest.raises(AssertionError) as failure:
        deployment_helpers.docker(operation)
    message = str(failure.value)
    assert f"Docker {operation} failed (exit 1)" in message
    assert "permission_denied" in message and "Check" in message
    assert token not in message


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_helper_failure_preserves_test_identity_and_cleanup_error_safely(
    monkeypatch: pytest.MonkeyPatch,
    deployment_helpers: ModuleType,
    cleanup_fails: bool,
) -> None:
    token = uuid4().hex
    calls: list[str] = []

    def execute(*args: str, **kwargs: object) -> str:
        calls.append(args[0])
        if args[0] == "create":
            return "owned-helper"
        if args[0] == "inspect":
            return json.dumps(
                {
                    "Config": {"Labels": {"com.docker.compose.project": "owned"}},
                    "HostConfig": {"NetworkMode": "none", "PortBindings": {}},
                }
            ).join(["[", "]"])
        if args[0] == "wait":
            return "7"
        if args[0] == "logs":
            return (
                "FAILED tests/unit/test_deployment_checks.py::"
                "test_probe_acknowledges_reads_and_cleans_only_owned_key["
                + token
                + "] - payload "
                + token
                + "\nFAILED tests/unapproved.py::test_"
                + token
                + '\n{"outcome":"unavailable","reason_code":"health_response",'
                '"next_action":"' + token + '"}\n'
                '{"reason_code":"' + token + '"}'
            )
        if args[0] == "rm" and cleanup_fails:
            raise deployment_helpers.DeploymentError(
                "Docker rm failed (exit 1); permission_denied; "
                "Check owned resource permissions."
            )
        return ""

    monkeypatch.setattr(deployment_helpers, "docker", execute)
    with pytest.raises(AssertionError) as failure:
        deployment_helpers.run_owned(
            "owned", "fixture:local", gate="offline-regression"
        )
    message = str(failure.value)
    assert "exit 7" in message and "offline-regression" in message
    assert (
        "tests/unit/test_deployment_checks.py::"
        "test_probe_acknowledges_reads_and_cleans_only_owned_key"
    ) in message
    assert "health_response" in message and "Check" in message
    assert ("cleanup failed" in message) == cleanup_fails
    assert token not in message and "unapproved" not in message
    assert calls[-1] == "rm"


@pytest.mark.parametrize("explicit_unowned", [False, True])
def test_image_anonymous_volume_is_not_an_unowned_explicit_mount(
    monkeypatch: pytest.MonkeyPatch,
    deployment_helpers: ModuleType,
    explicit_unowned: bool,
) -> None:
    instance = deployment_helpers.Deployment.__new__(deployment_helpers.Deployment)
    instance.project = "owned"
    instance.containers = []
    instance.volumes = set()
    instance.network = ""
    instance.retain = False
    anonymous = uuid4().hex + uuid4().hex
    calls: list[tuple[str, ...]] = []
    info = {
        "Id": "owned-container",
        "Config": {
            "Labels": {"com.docker.compose.project": "owned"},
            "Volumes": {"/data": {}},
        },
        "State": {"Running": True},
        "HostConfig": {
            "PortBindings": {},
            "Binds": [anonymous + ":/data"] if explicit_unowned else [],
        },
        "NetworkSettings": {
            "Networks": {"owned": {"NetworkID": "owned-network", "Aliases": ["minio"]}}
        },
        "Mounts": [
            {"Type": "volume", "Name": anonymous, "Destination": "/data"},
            {"Type": "volume", "Name": "owned-data", "Destination": "/mnt/data"},
        ],
    }

    def execute(*args: str, **kwargs: object) -> str:
        calls.append(args)
        if args[0] == "inspect":
            return json.dumps([info])
        if args[:2] == ("network", "inspect"):
            return json.dumps([{"Labels": {"com.docker.compose.project": "owned"}}])
        if args[:2] == ("volume", "inspect"):
            labels = (
                {} if args[2] == anonymous else {"com.docker.compose.project": "owned"}
            )
            return json.dumps([{"Labels": labels}])
        return ""

    monkeypatch.setattr(deployment_helpers, "docker", execute)
    monkeypatch.setattr(instance, "compose", lambda *args: "")
    if explicit_unowned:
        with pytest.raises(AssertionError, match="Unexpected unowned volume"):
            instance.start("minio")
        assert not instance.volumes
    else:
        instance.start("minio")
        assert instance.volumes == {"owned-data"}
        instance.close()
        assert ("rm", "-f", "-v", "owned-container") in calls
        assert ("volume", "rm", "owned-data") in calls
        assert not any(args[:3] == ("volume", "rm", anonymous) for args in calls)
