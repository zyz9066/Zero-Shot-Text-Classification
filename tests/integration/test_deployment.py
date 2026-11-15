from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal, get_args
from uuid import uuid4

import pytest
import yaml

from scripts.check_deployment import preflight

ROOT = Path(__file__).resolve().parents[2]
Gate = Literal[
    "helper",
    "context",
    "cpu-imports",
    "offline-regression",
    "app-readiness",
    "storage-readiness",
    "complete-record",
    "volume-backup",
    "volume-restore",
]
GATES = set(get_args(Gate))


class DeploymentError(AssertionError):
    """A failure containing only allowlisted operational metadata."""


def failure_summary(output: str) -> str:
    __tracebackhide__ = True
    details: list[str] = []
    categories = {
        "permission denied": (
            "permission_denied; Check owned resource and Docker permissions."
        ),
        "cannot connect to the docker daemon": (
            "daemon_unavailable; Check the supported local engine."
        ),
        "failed to resolve": (
            "image_resolution; Check pinned image availability and registry access."
        ),
        "uv sync": (
            "dependency_install; Check locked dependency availability for Linux amd64."
        ),
        "license": (
            "license_or_mount; Check authorized license status and external "
            "regular file."
        ),
        "address already in use": (
            "port_conflict; Check publication; do not stop unrelated services."
        ),
    }
    for marker, action in categories.items():
        if marker in output.lower():
            details.append(action)
    identities: set[str] = set()
    for line in (ROOT / ".dockerignore").read_text().splitlines():
        if line.startswith("!tests/") and line.endswith(".py"):
            path = line[1:]
            names = re.findall(
                r"^def (test_\w+)\(", (ROOT / path).read_text(encoding="utf-8"), re.M
            )
            identities.update(f"{path}::{name}" for name in names)
    failed = {
        f"{path}::{name}"
        for path, name in re.findall(
            r"(?:FAILED|ERROR) (tests/[\w/]+\.py)::(test_\w+)", output
        )
    }
    for identity in sorted(identities & failed):
        details.append(f"failed_test={identity}; Check this regression independently.")
    reasons = {
        "health_response",
        "tls",
        "transport",
        "configuration",
        "client_configuration",
        "credentials",
        "access_denied",
        "invalid_bucket",
        "write_uncertain",
        "cleanup_failed",
        "readback_failed",
    }
    for line in output.splitlines():
        if not line.startswith("{"):
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and isinstance(result.get("reason_code"), str):
            reason = result["reason_code"]
            if reason in reasons:
                details.append(
                    f"reason={reason}; Check the documented readiness/recovery action."
                )
    return "; ".join(details) or (
        "unclassified; Check the named operation/gate with non-sensitive fixtures "
        "and the README troubleshooting guide; raw output withheld."
    )


class TestEnvironment(dict[str, str]):
    __test__ = False

    def __repr__(self) -> str:
        return "<deployment environment: values withheld>"


def environment() -> TestEnvironment:
    keep = {
        "PATH",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
    }
    return TestEnvironment(
        (key, value) for key, value in os.environ.items() if key.upper() in keep
    )


def docker(*args: str, env: dict[str, str] | None = None) -> str:
    # Subprocess results and inspect output can contain credentials.
    __tracebackhide__ = True
    operation = (
        args[0]
        if args
        and args[0]
        in {
            "build",
            "create",
            "start",
            "stop",
            "wait",
            "inspect",
            "logs",
            "exec",
            "compose",
            "image",
            "network",
            "volume",
            "rm",
            "context",
        }
        else "operation"
    )
    try:
        result = subprocess.run(
            ["docker", *args],
            env=environment() if env is None else env,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        raise DeploymentError(
            f"Docker {operation} exceeded its bounded deadline; "
            "Check owned service state and runtime capacity; preserve volumes."
        ) from None
    except OSError:
        raise DeploymentError(
            f"Docker {operation} could not launch; Check the CLI and local engine."
        ) from None
    if result.returncode:
        raise DeploymentError(
            f"Docker {operation} failed (exit {result.returncode}); "
            + failure_summary(result.stdout + "\n" + result.stderr)
        )
    return result.stdout.strip()


def eligibility() -> None:
    if os.environ.get("RUN_DEPLOYMENT_TESTS") != "1":
        pytest.skip("SKIPPED: RUN_DEPLOYMENT_TESTS=1 is required for container checks")
    if shutil.which("docker") is None:
        pytest.skip("SKIPPED: Docker CLI is unavailable")
    result = subprocess.run(
        ["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"],
        env=environment(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode:
        pytest.skip("SKIPPED: Docker engine is unavailable before execution")
    assert result.stdout.strip() in {"linux/x86_64", "linux/amd64"}, (
        "Configured engine is not supported Linux amd64"
    )
    endpoint = environment().get("DOCKER_HOST") or docker(
        "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
    )
    assert endpoint.startswith(("npipe:", "unix:")), (
        "Only a local Docker transport may receive the source context"
    )


def run_owned(
    project: str,
    *args: str,
    network: str = "none",
    env: dict[str, str] | None = None,
    gate: Gate = "helper",
) -> str:
    __tracebackhide__ = True
    if gate not in GATES:
        raise DeploymentError("Unknown validation gate; Check the fixture invocation.")
    container = docker(
        "create",
        "--network",
        network,
        "--name",
        project + "-helper-" + uuid4().hex[:12],
        "--label",
        "com.docker.compose.project=" + project,
        *args,
        env=env,
    )
    failure: DeploymentError | None = None
    try:
        info = json.loads(docker("inspect", container))[0]
        if (
            info["Config"]["Labels"]["com.docker.compose.project"] != project
            or info["HostConfig"]["NetworkMode"] != network
            or info["HostConfig"]["PortBindings"]
        ):
            raise DeploymentError(
                "Helper isolation failed; Check owned labels/network/no-port contract."
            )
        docker("start", container)
        exit_code = docker("wait", container)
        if exit_code != "0":
            status = (
                exit_code if re.fullmatch(r"\d{1,3}", exit_code) else "invalid-status"
            )
            try:
                summary = failure_summary(docker("logs", container))
            except DeploymentError as error:
                summary = f"Logs unavailable: {error}"
            raise DeploymentError(
                f"Owned validation helper failed (exit {status}); "
                f"gate={gate}; {summary}"
            )
        return docker("logs", container)
    except DeploymentError as error:
        failure = error
        raise
    finally:
        try:
            info = json.loads(docker("inspect", container))[0]
            if info["Config"]["Labels"]["com.docker.compose.project"] != project:
                raise DeploymentError(
                    "Helper cleanup ownership mismatch; Check exact owned IDs."
                )
            docker("rm", "-f", container)
        except DeploymentError as cleanup:
            raise DeploymentError(
                f"{failure}; cleanup failed: {cleanup}"
                if failure
                else f"Helper cleanup failed: {cleanup}"
            ) from None


@pytest.fixture(scope="session")
def images(tmp_path_factory: pytest.TempPathFactory):
    eligibility()
    context = tmp_path_factory.mktemp("deployment-context")
    project = "zeroshot-test-" + uuid4().hex
    allowed = [
        line[1:]
        for line in (ROOT / ".dockerignore").read_text().splitlines()
        if line.startswith("!") and not line.endswith("/")
    ]
    assert all("*" not in path for path in allowed)
    for relative in dict.fromkeys([".dockerignore", *allowed]):
        source = ROOT / relative
        assert source.is_file(), f"Allowlisted source is missing: {relative}"
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    forbidden = [
        ".env",
        "secrets/minio.license",
        "models/weights.bin",
        "configs/labels.yaml",
        "configs/labels.yaml.initialized",
        "tests/unlisted-" + uuid4().hex + ".py",
        "tests/__pycache__/runtime.pyc",
        "backups/runtime.tar",
    ]
    for relative in forbidden:
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(uuid4().bytes)
    runtime = project + "-app:local"
    validation = project + "-validation:local"
    built: list[str] = []
    try:
        for target, tag in [("runtime", runtime), ("validation", validation)]:
            docker("build", "--target", target, "-t", tag, str(context))
            built.append(tag)
        yield {
            "project": project,
            "runtime": runtime,
            "validation": validation,
            "context": context,
            "forbidden": forbidden,
        }
    finally:
        for tag in reversed(built):
            docker("image", "rm", tag)


class Deployment:
    def __init__(self, images: dict, directory: Path, license_file: Path | None = None):
        __tracebackhide__ = True
        self.project = images["project"] + "-" + uuid4().hex[:12]
        self.validation = images["validation"]
        self.env = environment()
        self.empty_env = directory / "compose.env"
        self.empty_env.write_text("")
        self.env["COMPOSE_PROJECT_NAME"] = self.project
        self.env["COMPOSE_DISABLE_ENV_FILE"] = "1"
        self.files = ["-f", str(ROOT / "compose.yaml")]
        self.containers: list[str] = []
        self.volumes: set[str] = set()
        self.network = ""
        self.retain = False
        docker("image", "tag", images["runtime"], self.project + "-app:local")
        if license_file is not None:
            self.files += ["-f", str(ROOT / "compose.minio.yaml")]
            self.env["MINIO_LICENSE_FILE"] = str(license_file.resolve())
            self.env["MINIO_ACCESS_KEY"] = uuid4().hex
            self.env["MINIO_SECRET_KEY"] = uuid4().hex
            for key, credential in [
                ("MINIO_ROOT_USER_FILE", self.env["MINIO_ACCESS_KEY"]),
                ("MINIO_ROOT_PASSWORD_FILE", self.env["MINIO_SECRET_KEY"]),
            ]:
                path = directory / key
                path.write_text(credential)
                self.env[key] = str(path)
            if preflight(self.env).outcome != "ready":
                raise DeploymentError(
                    "Deployment preflight failed; Check external license/root files."
                )

    def compose(self, *args: str) -> str:
        __tracebackhide__ = True
        return docker(
            "compose",
            "--env-file",
            str(self.empty_env),
            "-p",
            self.project,
            *self.files,
            *args,
            env=self.env,
        )

    def start(self, service: str) -> str:
        __tracebackhide__ = True
        self.compose(
            "run",
            "-d",
            "--no-deps",
            "--use-aliases",
            "--name",
            self.project + "-" + service,
            service,
        )
        info = json.loads(docker("inspect", self.project + "-" + service))[0]
        container = info["Id"]
        self.containers.append(container)
        labels = info["Config"]["Labels"]
        assert labels["com.docker.compose.project"] == self.project
        if not info["State"]["Running"]:
            raise DeploymentError(
                "Owned service startup failed; "
                + failure_summary(docker("logs", container))
            )
        assert not info["HostConfig"]["PortBindings"], "Host publication is forbidden"
        networks = info["NetworkSettings"]["Networks"]
        assert len(networks) == 1
        self.network = next(iter(networks.values()))["NetworkID"]
        network = json.loads(docker("network", "inspect", self.network))[0]
        assert network["Labels"]["com.docker.compose.project"] == self.project
        assert service in next(iter(networks.values()))["Aliases"]
        for mount in info["Mounts"]:
            if mount["Type"] == "volume":
                name = mount["Name"]
                volume = json.loads(docker("volume", "inspect", name))[0]
                if (volume.get("Labels") or {}).get(
                    "com.docker.compose.project"
                ) == self.project:
                    self.volumes.add(name)
                elif not (
                    re.fullmatch(r"[0-9a-f]{64}", name)
                    and mount["Destination"] in (info["Config"].get("Volumes") or {})
                    and not info["HostConfig"].get("VolumesFrom")
                    and not any(
                        bind.startswith(name + ":")
                        for bind in (info["HostConfig"].get("Binds") or [])
                    )
                    and not any(
                        entry.get("Source") == name
                        for entry in (info["HostConfig"].get("Mounts") or [])
                    )
                ):
                    raise DeploymentError(
                        "Unexpected unowned volume; Check explicit mounts and "
                        "image-declared anonymous volumes."
                    )
        return container

    def helper(self, *command: str, gate: Gate = "helper") -> str:
        __tracebackhide__ = True
        assert self.network
        network = json.loads(docker("network", "inspect", self.network))[0]
        assert network["Labels"]["com.docker.compose.project"] == self.project
        flags: list[str] = []
        for key in [
            "MINIO_ENDPOINT",
            "MINIO_SECURE",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "MINIO_TEST_BUCKET",
            "MINIO_BUCKET",
        ]:
            if key in self.env:
                flags += ["--env", key]
        return run_owned(
            self.project,
            *flags,
            "--entrypoint",
            "python",
            self.validation,
            *command,
            network=self.network,
            env=self.env,
            gate=gate,
        )

    def close(self) -> None:
        __tracebackhide__ = True
        for container in reversed(self.containers):
            info = json.loads(docker("inspect", container))[0]
            assert (
                info["Config"]["Labels"]["com.docker.compose.project"] == self.project
            )
            if self.retain:
                docker("stop", container)
            else:
                docker("rm", "-f", "-v", container)
        if self.retain:
            print("Diagnostic resources retained, stopped; project:", self.project)
        else:
            if self.network:
                network = json.loads(docker("network", "inspect", self.network))[0]
                assert network["Labels"]["com.docker.compose.project"] == self.project
                docker("network", "rm", self.network)
            for name in self.volumes:
                volume = json.loads(docker("volume", "inspect", name))[0]
                assert volume["Labels"]["com.docker.compose.project"] == self.project
                docker("volume", "rm", name)
        docker("image", "rm", self.project + "-app:local")


def test_filtered_context_and_distinct_image_targets(images: dict, tmp_path: Path):
    context = images["context"]
    base = next(
        line.split()[1]
        for line in (ROOT / "Dockerfile").read_text().splitlines()
        if line.startswith("FROM python:")
    )
    inspection = tmp_path / "Dockerfile.inspection"
    inspection.write_text(
        f"FROM {base}\nCOPY . /context\n"
        'CMD ["python", "-c", "import pathlib,json; '
        'print(json.dumps([str(p.relative_to(\\"/context\\")) '
        'for p in pathlib.Path(\\"/context\\").rglob(\\"*\\") if p.is_file()]))"]\n'
    )
    tag = images["project"] + "-inspection:local"
    try:
        docker("build", "-f", str(inspection), "-t", tag, str(context))
        actual = json.loads(run_owned(images["project"], tag, gate="context"))
        assert not set(images["forbidden"]) & set(actual)
        assert "tests/integration/test_deployment.py" in actual
        for target in ["runtime", "validation"]:
            code = (
                "import importlib.util,pathlib,torch,transformers,ssl;"
                "assert torch.__version__.endswith('+cpu');"
                "assert torch.tensor([1,2,3]).sum().item()==6;"
                "assert pathlib.Path('/etc/ssl/certs/ca-certificates.crt').is_file();"
                "assert pathlib.Path('/opt/app/tests').exists()=="
                f"{target == 'validation'};"
                f"assert (importlib.util.find_spec('pytest') is not None)=="
                f"{target == 'validation'};"
                f"assert not any(pathlib.Path('/opt/app',p).exists() for p in "
                f"{images['forbidden']!r});"
                "print('CPU/import/context target checks passed')"
            )
            run_owned(
                images["project"],
                "--read-only",
                "--env",
                "HF_HUB_OFFLINE=1",
                "--env",
                "TRANSFORMERS_OFFLINE=1",
                "--entrypoint",
                "python",
                images[target],
                "-c",
                code,
                gate="cpu-imports",
            )
        print(
            run_owned(
                images["project"],
                "--env",
                "HF_HUB_OFFLINE=1",
                "--env",
                "TRANSFORMERS_OFFLINE=1",
                "--entrypoint",
                "python",
                images["validation"],
                "-m",
                "pytest",
                "tests",
                "-q",
                "-rs",
                gate="offline-regression",
            )
        )
    finally:
        docker("image", "rm", tag)


def test_app_only_no_ports_and_durable_sidecars(images: dict, tmp_path: Path):
    deployment = Deployment(images, tmp_path)
    try:
        rendered = json.loads(deployment.compose("config", "--format", "json"))
        services = rendered["services"]
        assert set(services) == {"app"}
        assert services["app"]["ports"][0]["host_ip"] == "127.0.0.1"
        assert not services["app"].get("depends_on")
        container = deployment.start("app")
        health_code = (
            "import time;from scripts.check_deployment import health;"
            "end=time.monotonic()+60\n"
            "while time.monotonic()<end:\n"
            " r=health('app','http://app:8501')\n"
            " if r.outcome=='ready':break\n"
            " time.sleep(1)\n"
            "else:\n"
            " import json;print(json.dumps(r.to_dict()));raise SystemExit(1)\n"
        )
        deployment.helper("-c", health_code, gate="app-readiness")
        tracked = list(deployment.containers)
        with pytest.raises(AssertionError, match="helper failed \\(exit 7\\)"):
            deployment.helper("-c", "raise SystemExit(7)")
        assert deployment.containers == tracked
        nested_failure = (
            "import pytest\n"
            "class Regression:\n"
            " def pytest_runtest_call(self,item):\n"
            "  raise AssertionError('generated non-sensitive regression')\n"
            "raise SystemExit(pytest.main(['tests/unit/test_deployment_checks.py',"
            "'-k','test_probe_acknowledges_reads_and_cleans_only_owned_key','-q'],"
            "plugins=[Regression()]))"
        )
        with pytest.raises(
            DeploymentError,
            match="gate=offline-regression;.*failed_test=tests/unit/"
            "test_deployment_checks.py::"
            "test_probe_acknowledges_reads_and_cleans_only_owned_key",
        ):
            deployment.helper("-c", nested_failure, gate="offline-regression")
        assert not docker(
            "ps",
            "-aq",
            "--filter",
            "label=com.docker.compose.project=" + deployment.project,
            "--filter",
            "name=" + deployment.project + "-helper-",
        ), "Owned helper remained after a failed command"
        seed = (
            "import os;from pathlib import Path;"
            "from app.services.label_manager import LabelManager;"
            "from app.services.model_provider import get_model_manager;"
            "assert os.getuid()==10001;"
            "assert not os.getenv('MINIO_ACCESS_KEY');"
            "assert not os.getenv('MINIO_SECRET_KEY');"
            "LabelManager(Path('/runtime/labels/catalog.yaml')).create"
            "('Deployment fixture',['Sports','News']);"
            "manager=get_model_manager();"
            "model=manager.list_status()[0].model_id\n"
            "with manager.model_use_guard(model):pass\n"
            "p=manager.model_directory(model);p.mkdir(parents=True,exist_ok=True);"
            "(p/'fixture.bin').write_bytes(b'non-model fixture');"
            "[(Path(d)/'fixture').write_bytes(b'cache fixture') for d in "
            "['/runtime/hf-home','/runtime/hub-cache','/runtime/hf-home/hub',"
            "'/runtime/xdg-cache']]"
        )
        docker("exec", container, "python", "-c", seed)
        snapshot = (
            "import json,hashlib;from pathlib import Path;"
            "print(json.dumps({str(p.relative_to('/runtime')):"
            "[hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_uid]"
            " for p in Path('/runtime').rglob('*') if p.is_file()}))"
        )
        before = json.loads(docker("exec", container, "python", "-c", snapshot))
        assert any(name.endswith(".initialized") for name in before)
        assert any(name.endswith(".use.lock") and "/" not in name for name in before)
        docker("stop", container)
        original = next(iter(deployment.volumes))
        backup = deployment.project + "-backup"
        restored = deployment.project + "-restored"
        for volume in [backup, restored]:
            docker(
                "volume",
                "create",
                "--label",
                "com.docker.compose.project=" + deployment.project,
                volume,
            )
            owned = json.loads(docker("volume", "inspect", volume))[0]
            assert owned["Labels"]["com.docker.compose.project"] == deployment.project
            deployment.volumes.add(volume)
        utility = next(
            line.split()[1]
            for line in (ROOT / "Dockerfile").read_text().splitlines()
            if line.startswith("FROM python:")
        )
        run_owned(
            deployment.project,
            "--mount",
            f"type=volume,src={original},dst=/data,readonly",
            "--mount",
            f"type=volume,src={backup},dst=/backup",
            utility,
            "python",
            "-c",
            "import tarfile;t=tarfile.open('/backup/runtime.tar','w');"
            "t.add('/data',arcname='.');t.close()",
            gate="volume-backup",
        )
        run_owned(
            deployment.project,
            "--mount",
            f"type=volume,src={restored},dst=/runtime",
            "--mount",
            f"type=volume,src={backup},dst=/backup,readonly",
            utility,
            "python",
            "-c",
            "import tarfile;t=tarfile.open('/backup/runtime.tar');"
            "t.extractall('/runtime',filter='tar');t.close();" + snapshot,
            gate="volume-restore",
        )
        restored_snapshot = json.loads(
            run_owned(
                deployment.project,
                "--mount",
                f"type=volume,src={restored},dst=/runtime,readonly",
                utility,
                "python",
                "-c",
                snapshot,
                gate="volume-restore",
            )
        )
        assert restored_snapshot == before
        docker("start", container)
        assert json.loads(docker("exec", container, "python", "-c", snapshot)) == before
        docker("rm", "-f", container)
        deployment.containers.remove(container)
        container = deployment.start("app")
        assert json.loads(docker("exec", container, "python", "-c", snapshot)) == before
    finally:
        deployment.close()


def test_isolated_prediction_storage(request: pytest.FixtureRequest, tmp_path: Path):
    if os.environ.get("RUN_DEPLOYMENT_TESTS") != "1":
        pytest.skip("SKIPPED: RUN_DEPLOYMENT_TESTS=1 is required")
    if "MINIO_LICENSE_FILE" not in os.environ:
        pytest.skip(
            "SKIPPED: authorized MINIO_LICENSE_FILE unavailable; local alternative: "
            "set RUN_DEPLOYMENT_TESTS=1 and external license, then uv run --locked "
            "pytest tests/integration/test_deployment.py "
            "-k isolated_prediction_storage "
            "-q -rs"
        )
    license_file = Path(os.environ["MINIO_LICENSE_FILE"])
    assert license_file.is_file() and license_file.stat().st_size > 0, (
        "Configured license must be an existing nonempty regular file"
    )
    images = request.getfixturevalue("images")
    deployment = Deployment(images, tmp_path, license_file)
    try:
        deployment.start("minio")
        deployment.env.update(
            MINIO_ENDPOINT="minio:9000",
            MINIO_SECURE="false",
            MINIO_TEST_BUCKET="zeroshot-test-" + uuid4().hex,
        )
        wait = (
            "import time;from scripts.check_deployment import health;"
            "end=time.monotonic()+60\n"
            "while time.monotonic()<end:\n"
            " r=health('minio','http://minio:9000')\n"
            " if r.outcome=='ready':break\n"
            " time.sleep(1)\n"
            "else:\n"
            " import json;print(json.dumps(r.to_dict()));raise SystemExit(1)\n"
        )
        deployment.helper("-c", wait, gate="storage-readiness")
        run = (
            "import subprocess,xml.etree.ElementTree as ET;"
            "p=subprocess.run(['pytest','tests/integration/test_prediction_storage.py',"
            "'-q','--junitxml=/tmp/record.xml'],capture_output=True);"
            "root=ET.parse('/tmp/record.xml').getroot();"
            "cases=[c for c in root.iter('testcase') if "
            "c.attrib.get('name')=='test_minio_prediction_write_and_read'];"
            "passed=p.returncode==0 and len(cases)==1 and len(cases[0])==0;"
            "print('Service-backed complete-record test passed' if passed else "
            "'FAILED tests/integration/test_prediction_storage.py::"
            "test_minio_prediction_write_and_read');"
            "raise SystemExit(0 if passed else 1)"
        )
        deployment.helper("-c", run, gate="complete-record")
    except AssertionError:
        deployment.retain = True
        raise
    finally:
        deployment.close()


def test_normal_compose_ports_are_loopback():
    app = yaml.safe_load((ROOT / "compose.yaml").read_text())
    storage = yaml.safe_load((ROOT / "compose.minio.yaml").read_text())
    assert app["services"]["app"]["ports"] == ["127.0.0.1:8501:8501"]
    assert storage["services"]["minio"]["ports"] == [
        "127.0.0.1:9000:9000",
        "127.0.0.1:9001:9001",
    ]
