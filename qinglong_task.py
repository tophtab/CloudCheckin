import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
# Random start delay is opt-in for the Qinglong form: set CHECKIN_RANDOM_DELAY_MAX
# (minutes) to enable it.
DEFAULT_RANDOM_DELAY_MAX_MINUTES = 0
NO_DELAY_FLAG = "--no-delay"
DEFAULT_CURL_CFFI_LIB_DIR = "/ql/data/codercheckin_libs"


def _curl_cffi_lib_dir() -> Path | None:
    """Optional directory holding an isolated curl_cffi for this deployment.

    Qinglong may host other scripts that require a newer curl_cffi in the
    shared site-packages; codercheckin keeps its pinned version in a separate
    directory (see README) and imports it ahead of site-packages.
    """
    raw = os.environ.get("CHECKIN_CURL_CFFI_LIB_DIR", "").strip()
    path = Path(raw) if raw else Path(DEFAULT_CURL_CFFI_LIB_DIR)
    return path if path.is_dir() else None


def _bootstrap_paths() -> None:
    """Make the repo root importable for this process and spawned subprocesses.

    Qinglong runs each whitelisted wrapper from an arbitrary cwd inside a
    subscription subdirectory, and checkin_runner spawns platform modules via
    ``python -m``, which resolves against the inherited PYTHONPATH.
    """
    lib_dir = _curl_cffi_lib_dir()
    priority = [str(REPO_ROOT)]
    if lib_dir:
        priority.insert(0, str(lib_dir))

    for entry in priority:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    entries = [
        entry
        for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if entry
    ]
    for entry in priority:
        if entry not in entries:
            entries.insert(0, entry)
    os.environ["PYTHONPATH"] = os.pathsep.join(entries)


_bootstrap_paths()


# Imports must follow _bootstrap_paths() so this module stays importable from
# any cwd before the repo root is guaranteed to be on sys.path.
from checkin_runner import run_targets
from random_delay import apply_random_start_delay
from runtime_log import log


def _resolve_max_delay_seconds() -> int:
    raw_value = os.environ.get("CHECKIN_RANDOM_DELAY_MAX", "").strip()
    if not raw_value:
        return DEFAULT_RANDOM_DELAY_MAX_MINUTES * 60

    try:
        minutes = int(raw_value)
    except ValueError:
        log(f"Invalid CHECKIN_RANDOM_DELAY_MAX={raw_value!r}, ignoring")
        return DEFAULT_RANDOM_DELAY_MAX_MINUTES * 60

    if minutes < 0:
        log(f"CHECKIN_RANDOM_DELAY_MAX={raw_value!r} is negative, treating as 0")
        return 0

    return minutes * 60


def main(target: str, argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)

    if NO_DELAY_FLAG in arguments:
        log(f"Skipping random start delay ({NO_DELAY_FLAG})")
    else:
        max_delay_seconds = _resolve_max_delay_seconds()
        if max_delay_seconds <= 0:
            log("Random start delay is disabled")
        else:
            apply_random_start_delay(max_delay_seconds=max_delay_seconds)

    try:
        return run_targets([target])
    except Exception as err:
        log(err)
        return 1


if __name__ == "__main__":
    targets = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if len(targets) != 1:
        log(f"Usage: python {Path(__file__).name} <target> [{NO_DELAY_FLAG}]")
        sys.exit(2)
    try:
        sys.exit(main(targets[0]))
    except KeyboardInterrupt:
        log("Task stopped by user")
        sys.exit(0)
