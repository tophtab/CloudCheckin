import os
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, TypeAlias

from config import MIN_CURL_CFFI_VERSION
from cookiecloud.client import resolve_cookie_value
from runtime_log import log


@dataclass(frozen=True)
class TargetConfig:
    module_name: str
    cookie_env: str
    domains: tuple[str, ...]


TARGETS = {
    "nodeseek": TargetConfig(
        module_name="nodeseek.nodeseek",
        cookie_env="NODESEEK_COOKIE",
        domains=("nodeseek.com", "www.nodeseek.com"),
    ),
    "deepflood": TargetConfig(
        module_name="deepflood.deepflood",
        cookie_env="DEEPFLOOD_COOKIE",
        domains=("deepflood.com", "www.deepflood.com"),
    ),
    "v2ex": TargetConfig(
        module_name="v2ex.v2ex",
        cookie_env="V2EX_COOKIE",
        domains=("v2ex.com", "www.v2ex.com"),
    ),
}
MODULES = {target: config.module_name for target, config in TARGETS.items()}

RECENT_OUTPUT_LINE_LIMIT = 40
TARGET_MAX_ATTEMPTS = 3
TARGET_RETRY_DELAY_SECONDS = 30

RecentOutput: TypeAlias = deque[tuple[str, str]]


class TargetExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        target: str,
        returncode: int | None,
        recent_output: list[tuple[str, str]],
    ) -> None:
        self.target = target
        self.returncode = returncode
        self.recent_output = list(recent_output)
        super().__init__(_format_failure_message(target, returncode, recent_output))


class MultipleTargetExecutionError(TargetExecutionError):
    def __init__(self, failures: list[TargetExecutionError]) -> None:
        if not failures:
            raise ValueError("MultipleTargetExecutionError requires at least one failure")

        self.failures = list(failures)
        first_failure = failures[0]
        self.target = first_failure.target
        self.returncode = first_failure.returncode
        self.recent_output = list(first_failure.recent_output)
        RuntimeError.__init__(self, _format_multiple_failure_message(failures))


def parse_targets() -> list[str]:
    raw_targets = os.environ.get(
        "CHECKIN_TARGETS",
        "nodeseek,deepflood,v2ex",
    )
    targets = [item.strip().lower() for item in raw_targets.split(",") if item.strip()]

    if not targets:
        raise ValueError("Environment variable CHECKIN_TARGETS is empty")

    unknown = [target for target in targets if target not in TARGETS]
    if unknown:
        raise ValueError(
            "Unknown check-in targets: "
            + ", ".join(unknown)
            + ". Supported targets: "
            + ", ".join(TARGETS.keys())
        )

    return targets


def validate_target_cookies(
    targets: list[str],
    *,
    resolve_cookie=resolve_cookie_value,
) -> None:
    failures: list[str] = []

    log("Validating startup cookie configuration...")
    for target in targets:
        config = TARGETS[target]
        cookie, source = resolve_cookie(
            config.cookie_env,
            list(config.domains),
        )
        if cookie:
            log(f"Startup validation: target '{target}' has cookie from {source}")
            continue

        domains = ", ".join(config.domains)
        failures.append(f"{target} ({config.cookie_env}; domains: {domains})")
        log(
            f"Startup validation: target '{target}' has no cookie from environment "
            "or Cookie Cloud"
        )

    if failures:
        raise ValueError(
            "Startup validation failed: no cookie available for configured target(s): "
            + "; ".join(failures)
            + ". Configure the direct cookie environment variable or Cookie Cloud with "
            "matching domain cookies."
        )

    log("Startup cookie validation completed")


def _forward_stream(
    stream: IO[str],
    destination: IO[str],
    stream_name: str,
    recent_output: RecentOutput,
) -> None:
    for chunk in iter(stream.readline, ""):
        destination.write(chunk)
        destination.flush()

        line = chunk.rstrip("\r\n")
        if line:
            recent_output.append((stream_name, line))


def _run_target_process(
    target: str,
    module_name: str,
) -> tuple[int, list[tuple[str, str]]]:
    recent_output: RecentOutput = deque(maxlen=RECENT_OUTPUT_LINE_LIMIT)
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as err:
        recent_output.append(("stderr", f"Failed to start module '{module_name}': {err}"))
        raise TargetExecutionError(
            target=target,
            returncode=None,
            recent_output=list(recent_output),
        ) from err
    assert process.stdout is not None
    assert process.stderr is not None

    stdout_thread = threading.Thread(
        target=_forward_stream,
        args=(process.stdout, sys.stdout, "stdout", recent_output),
    )
    stderr_thread = threading.Thread(
        target=_forward_stream,
        args=(process.stderr, sys.stderr, "stderr", recent_output),
    )

    stdout_thread.start()
    stderr_thread.start()
    returncode = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    return returncode, list(recent_output)


def _format_failure_output_lines(recent_output: list[tuple[str, str]]) -> list[str]:
    if not recent_output:
        return ["  (no stdout/stderr output captured)"]

    return [f"  [{stream_name}] {line}" for stream_name, line in recent_output]


def _format_failure_message(
    target: str,
    returncode: int | None,
    recent_output: list[tuple[str, str]],
) -> str:
    output_lines = "\n".join(_format_failure_output_lines(recent_output))
    return (
        f"{_format_failure_summary(target, returncode)}\n"
        f"Recent output from failed target '{target}':\n"
        f"{output_lines}"
    )


def _format_multiple_failure_message(failures: list[TargetExecutionError]) -> str:
    sections: list[str] = [f"{len(failures)} check-in targets failed:"]
    for failure in failures:
        sections.append(
            _format_failure_message(
                failure.target,
                failure.returncode,
                failure.recent_output,
            )
        )
    return "\n\n".join(sections)


def _format_failure_summary(target: str, returncode: int | None) -> str:
    if returncode is None:
        return f"Check-in target '{target}' failed before it could start"

    return f"Check-in target '{target}' failed with exit code {returncode}"


def _print_failure_output(target: str, recent_output: list[tuple[str, str]]) -> None:
    log(f"Recent output from failed target '{target}':")
    for line in _format_failure_output_lines(recent_output):
        log(line)


def _major_minor(version: str) -> tuple[int, int] | None:
    parts = version.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None


def validate_curl_cffi_version() -> None:
    """Fail fast when the curl_cffi actually imported is older than the floor."""
    try:
        import curl_cffi
    except ImportError:
        raise RuntimeError(
            "curl_cffi is not importable; install it with "
            '`pip3 install "curl_cffi>=0.14"`'
        ) from None

    installed = str(getattr(curl_cffi, "__version__", ""))
    parsed = _major_minor(installed)
    if parsed is None or parsed < _major_minor(MIN_CURL_CFFI_VERSION):
        raise RuntimeError(
            f"imported curl_cffi {installed or 'unknown'} is older than the "
            f"supported floor {MIN_CURL_CFFI_VERSION}; upgrade with "
            "`pip3 install -U curl_cffi`"
        )


# Enforced at import time so a wrong curl_cffi aborts before any delay,
# cookie resolution, or network request happens.
validate_curl_cffi_version()


def run_targets(
    targets: list[str],
    *,
    max_attempts: int = TARGET_MAX_ATTEMPTS,
    retry_delay_seconds: int = TARGET_RETRY_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    failures: list[TargetExecutionError] = []

    for target in targets:
        module_name = TARGETS[target].module_name
        log(f"Starting check-in target '{target}' ({module_name})")
        target_error: TargetExecutionError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                returncode, recent_output = _run_target_process(target, module_name)
                if returncode == 0:
                    target_error = None
                    break
                target_error = TargetExecutionError(
                    target=target,
                    returncode=returncode,
                    recent_output=recent_output,
                )
            except TargetExecutionError as err:
                target_error = err

            log(_format_failure_summary(target_error.target, target_error.returncode))
            _print_failure_output(target_error.target, target_error.recent_output)

            if attempt < max_attempts:
                log(
                    f"Retrying check-in target '{target}' with attempt "
                    f"{attempt + 1}/{max_attempts} after "
                    f"{retry_delay_seconds} seconds"
                )
                sleep(retry_delay_seconds)

        if target_error is not None:
            failures.append(target_error)
            continue

        log(f"Check-in target '{target}' succeeded")

    if len(failures) == 1:
        raise failures[0]
    if failures:
        raise MultipleTargetExecutionError(failures)

    return 0
