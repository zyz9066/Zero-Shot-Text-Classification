from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import urlsplit
from uuid import uuid4

import urllib3
from minio.error import InvalidResponseError, S3Error, ServerError
from urllib3.exceptions import HTTPError, SSLError
from urllib3.response import HTTPResponse

from app.config.loader import load_minio_settings
from app.config.settings import ConfigurationError, MinIOServiceSettings
from app.services.prediction_store import (
    MinioClient,
    PredictionStorageConfigurationError,
    create_minio_client,
)

Outcome = Literal[
    "ready",
    "unavailable",
    "configuration_error",
    "rejected",
    "indeterminate",
    "cleanup_failed",
]


@dataclass(frozen=True)
class CheckResult:
    component: str
    operation: str
    outcome: Outcome
    reason_code: str
    next_action: str
    probe_id: str = ""
    object_key: str = ""

    def to_dict(self) -> dict[str, str]:
        result = {
            "component": self.component,
            "operation": self.operation,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "next_action": self.next_action,
        }
        if self.probe_id:
            result.update(probe_id=self.probe_id, object_key=self.object_key)
        return result


@runtime_checkable
class ProbeClient(MinioClient, Protocol):
    def get_object(self, bucket_name: str, object_name: str) -> HTTPResponse: ...

    def remove_object(self, bucket_name: str, object_name: str) -> object: ...


def preflight(environ: Mapping[str, str] | None = None) -> CheckResult:
    environment = os.environ if environ is None else environ
    for key in (
        "MINIO_LICENSE_FILE",
        "MINIO_ROOT_USER_FILE",
        "MINIO_ROOT_PASSWORD_FILE",
    ):
        value = environment.get(key, "")
        action = f"Supply {key} as an external readable regular file; do not print it."
        if not value.strip():
            return CheckResult(
                "deployment",
                "preflight",
                "configuration_error",
                f"{key.lower()}_missing",
                action,
            )
        try:
            path = Path(value)
            if not path.is_file():
                return CheckResult(
                    "deployment",
                    "preflight",
                    "configuration_error",
                    f"{key.lower()}_not_file",
                    action,
                )
            with path.open("rb") as stream:
                content = (
                    stream.read(1) if key == "MINIO_LICENSE_FILE" else stream.read()
                )
            if not content:
                reason = "empty"
            elif key != "MINIO_LICENSE_FILE" and (
                content != content.strip() or b"\n" in content or b"\r" in content
            ):
                reason = "whitespace"
            else:
                if key != "MINIO_LICENSE_FILE":
                    content.decode("utf-8")
                continue
        except (OSError, UnicodeError, ValueError):
            reason = "unreadable"
        return CheckResult(
            "deployment",
            "preflight",
            "configuration_error",
            f"{key.lower()}_{reason}",
            action + " Use nonempty files; credential values have no extra "
            "whitespace or newlines.",
        )
    return CheckResult(
        "deployment",
        "preflight",
        "ready",
        "files_readable",
        "File checks passed, not license authenticity. Check node health and "
        "explicitly probe storage permission with authorized credentials.",
    )


def health(component: Literal["app", "minio"], url: str | None = None) -> CheckResult:
    base = (
        url
        if url is not None
        else (
            "http://127.0.0.1:8501" if component == "app" else "http://127.0.0.1:9000"
        )
    )
    try:
        parsed = urlsplit(base)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("base URL")
        if parsed.port == 0:
            raise ValueError("service port")
    except ValueError:
        return CheckResult(
            component,
            "health",
            "configuration_error",
            "invalid_url",
            "Use an HTTP/HTTPS service base URL without credentials, query or path. "
            "Choose the API, not the console; keep TLS certificate validation enabled.",
        )
    http = urllib3.PoolManager(retries=False, timeout=5.0, cert_reqs="CERT_REQUIRED")
    paths = (
        ["/_stcore/health"]
        if component == "app"
        else ["/minio/health/live", "/minio/health/ready"]
    )
    try:
        for path in paths:
            response = http.request(
                "GET" if component == "app" else "HEAD",
                base.rstrip("/") + path,
                preload_content=False,
            )
            try:
                valid = response.status == 200
                if component == "app":
                    valid = valid and response.read(16).strip().lower() == b"ok"
                else:
                    valid = (
                        valid
                        and "text/html"
                        not in response.headers.get("Content-Type", "").lower()
                    )
                if not valid:
                    return CheckResult(
                        component,
                        "health",
                        "unavailable",
                        "health_response",
                        "Check startup, the API/application port and node readiness. "
                        "Preserve volumes; a responding console is not API readiness.",
                    )
            finally:
                try:
                    response.close()
                finally:
                    response.release_conn()
    except SSLError:
        return CheckResult(
            component,
            "health",
            "unavailable",
            "tls",
            "Align HTTP/TLS and trusted certificates; do not bypass validation.",
        )
    except (HTTPError, OSError):
        return CheckResult(
            component,
            "health",
            "unavailable",
            "transport",
            "Start the component; verify host/container address and API port.",
        )
    finally:
        http.clear()
    return CheckResult(
        component,
        "health",
        "ready",
        "component_health",
        "Application shell/node health only; this does not prove licensed S3 writes.",
    )


def _rejection(error: S3Error) -> tuple[str, str]:
    reasons = {
        "InvalidBucketName": (
            "invalid_bucket",
            "Explicitly set a valid MINIO_BUCKET; never rename silently.",
        ),
        "InvalidAccessKeyId": (
            "credentials",
            "Verify app credentials in the launch process; do not print them.",
        ),
        "SignatureDoesNotMatch": (
            "credentials",
            "Verify credentials, clock and HTTP/TLS/API settings.",
        ),
        "AccessDenied": (
            "access_denied",
            "Inspect authorized license status and bucket/object permissions; this "
            "response alone does not prove a license cause.",
        ),
    }
    code = error.code
    if code is not None and code in reasons:
        return reasons[code]
    return (
        "s3_rejected",
        "Unclassified S3 rejection: inspect authorized license/permissions; no retry.",
    )


def storage(
    settings: MinIOServiceSettings | None = None, client: ProbeClient | None = None
) -> CheckResult:
    try:
        selected = load_minio_settings() if settings is None else settings
    except ConfigurationError as error:
        return CheckResult(
            "storage",
            "write_probe",
            "configuration_error",
            "configuration",
            f"Check {error.issue.setting_name} in the application launch process and "
            "recreate after environment changes; do not disclose its value.",
        )
    if client is None:
        try:
            created = create_minio_client(selected)
        except PredictionStorageConfigurationError:
            return CheckResult(
                "storage",
                "write_probe",
                "configuration_error",
                "client_configuration",
                "Check MINIO_ENDPOINT, MINIO_SECURE and app credentials.",
            )
        if not isinstance(created, ProbeClient):
            return CheckResult(
                "storage",
                "write_probe",
                "configuration_error",
                "client_contract",
                "The storage client lacks required read/cleanup operations.",
            )
        client = created
    try:
        if not client.bucket_exists(selected.bucket):
            client.make_bucket(selected.bucket)
    except S3Error as error:
        reason, action = _rejection(error)
        return CheckResult("storage", "write_probe", "rejected", reason, action)
    except ValueError:
        return CheckResult(
            "storage",
            "write_probe",
            "configuration_error",
            "invalid_bucket",
            "Explicitly set a valid MINIO_BUCKET; otherwise preserve the original.",
        )
    except SSLError:
        return CheckResult(
            "storage",
            "write_probe",
            "unavailable",
            "tls",
            "Align MINIO_SECURE and the API certificates; never bypass TLS checks.",
        )
    except (InvalidResponseError, ServerError, HTTPError, OSError):
        return CheckResult(
            "storage",
            "write_probe",
            "unavailable",
            "transport",
            "Check server startup and API endpoint from this process.",
        )

    probe_id = str(uuid4())
    key = f"healthchecks/{probe_id}.json"
    payload = json.dumps(
        {"probe_id": probe_id, "purpose": "deployment-readiness"}, sort_keys=True
    ).encode("utf-8")
    try:
        client.put_object(
            selected.bucket, key, BytesIO(payload), len(payload), "application/json"
        )
    except ValueError:
        return CheckResult(
            "storage",
            "write_probe",
            "configuration_error",
            "write_configuration",
            "Check the exact bucket and API configuration; no retry was attempted.",
            probe_id,
            key,
        )
    except (S3Error, InvalidResponseError, ServerError, HTTPError, OSError) as error:
        if isinstance(error, S3Error):
            status = getattr(error.response, "status", None)
            if isinstance(status, int) and 400 <= status < 500:
                reason, action = _rejection(error)
                return CheckResult(
                    "storage", "write_probe", "rejected", reason, action, probe_id, key
                )
        return CheckResult(
            "storage",
            "write_probe",
            "indeterminate",
            "write_uncertain",
            "Inspect this exact key with authorized access; do not retry or delete "
            "unless absence and definitive non-completion are both established.",
            probe_id,
            key,
        )

    read_reason = ""
    try:
        response = client.get_object(selected.bucket, key)
        try:
            if response.read(len(payload) + 1) != payload:
                read_reason = "readback_mismatch"
        finally:
            try:
                response.close()
            finally:
                response.release_conn()
    except (InvalidResponseError, ServerError, S3Error, HTTPError, OSError):
        read_reason = "readback_failed"
    try:
        client.remove_object(selected.bucket, key)
    except (InvalidResponseError, ServerError, S3Error, HTTPError, OSError):
        return CheckResult(
            "storage",
            "write_probe",
            "cleanup_failed",
            f"{read_reason}_cleanup_failed" if read_reason else "cleanup_failed",
            "Cleanup failed for the acknowledged probe key"
            + (" and readback also failed." if read_reason else ".")
            + " Inspect/remove only this exact owned key when authorized.",
            probe_id,
            key,
        )
    if read_reason:
        return CheckResult(
            "storage",
            "write_probe",
            "rejected",
            read_reason,
            "Acknowledged probe cleaned, but readback failed; investigate API/storage.",
            probe_id,
            key,
        )
    return CheckResult(
        "storage",
        "write_probe",
        "ready",
        "write_read_cleanup_confirmed",
        "Licensed/authorized write, exact readback and owned-key cleanup confirmed.",
        probe_id,
        key,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe local deployment diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--component", choices=["app", "minio"], required=True)
    health_parser.add_argument("--url", help="HTTP/HTTPS service base URL")
    storage_parser = subparsers.add_parser("storage")
    storage_parser.add_argument("--write-probe", action="store_true", required=True)
    args = parser.parse_args(argv)
    if args.command == "preflight":
        result = preflight()
    elif args.command == "health":
        result = health("app" if args.component == "app" else "minio", args.url)
    else:
        result = storage()
    print(json.dumps(result.to_dict(), sort_keys=True))
    return (
        0
        if result.outcome == "ready"
        else (2 if result.outcome == "configuration_error" else 1)
    )


if __name__ == "__main__":
    raise SystemExit(main())
