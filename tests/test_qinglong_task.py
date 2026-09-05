import importlib
import os
import sys

import pytest

import qinglong_task
from tests.log_assertions import assert_timestamped_lines


def test_main_runs_single_target_with_default_delay(monkeypatch) -> None:
    monkeypatch.delenv("CHECKIN_RANDOM_DELAY_MAX", raising=False)

    delay_calls = []

    def fake_delay(*, max_delay_seconds: int) -> int:
        delay_calls.append(max_delay_seconds)
        return 5

    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", fake_delay)

    run_calls = []
    monkeypatch.setattr(
        qinglong_task,
        "run_targets",
        lambda targets: run_calls.append(list(targets)) or 0,
    )

    assert qinglong_task.main("nodeseek", argv=[]) == 0
    assert run_calls == [["nodeseek"]]
    assert delay_calls == [30 * 60]


def test_main_skips_delay_with_flag(monkeypatch) -> None:
    def fail_delay(**kwargs):
        raise AssertionError("Delay should not run with --no-delay")

    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", fail_delay)
    monkeypatch.setattr(qinglong_task, "run_targets", lambda targets: 0)

    assert qinglong_task.main("v2ex", argv=["--no-delay"]) == 0


def test_main_converts_env_minutes_to_seconds(monkeypatch) -> None:
    monkeypatch.setenv("CHECKIN_RANDOM_DELAY_MAX", "10")

    delay_calls = []

    def fake_delay(*, max_delay_seconds: int) -> int:
        delay_calls.append(max_delay_seconds)
        return 5

    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", fake_delay)
    monkeypatch.setattr(qinglong_task, "run_targets", lambda targets: 0)

    assert qinglong_task.main("deepflood", argv=[]) == 0
    assert delay_calls == [600]


def test_main_zero_env_disables_delay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CHECKIN_RANDOM_DELAY_MAX", "0")

    def fail_delay(**kwargs):
        raise AssertionError("Delay should not run when disabled")

    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", fail_delay)
    monkeypatch.setattr(qinglong_task, "run_targets", lambda targets: 0)

    assert qinglong_task.main("nodeseek", argv=[]) == 0

    output_lines = assert_timestamped_lines(capsys.readouterr().out)
    assert any("disabled" in line for line in output_lines)


def test_main_returns_one_and_logs_on_target_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", lambda **kwargs: 0)

    def fail_run_targets(targets: list[str]) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(qinglong_task, "run_targets", fail_run_targets)

    assert qinglong_task.main("deepflood", argv=["--no-delay"]) == 1
    assert "boom" in capsys.readouterr().out


def test_main_invalid_env_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CHECKIN_RANDOM_DELAY_MAX", "abc")

    delay_calls = []

    def fake_delay(*, max_delay_seconds: int) -> int:
        delay_calls.append(max_delay_seconds)
        return 5

    monkeypatch.setattr(qinglong_task, "apply_random_start_delay", fake_delay)
    monkeypatch.setattr(qinglong_task, "run_targets", lambda targets: 0)

    assert qinglong_task.main("nodeseek", argv=[]) == 0
    assert delay_calls == [30 * 60]

    output_lines = assert_timestamped_lines(capsys.readouterr().out)
    assert any("Invalid CHECKIN_RANDOM_DELAY_MAX" in line for line in output_lines)


def test_bootstrap_propagates_repo_root_to_subprocess_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/opt/ql/scripts")

    qinglong_task._bootstrap_paths()

    entries = os.environ["PYTHONPATH"].split(os.pathsep)
    assert entries[0] == str(qinglong_task.REPO_ROOT)
    assert "/opt/ql/scripts" in entries


def test_bootstrap_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "")

    qinglong_task._bootstrap_paths()
    qinglong_task._bootstrap_paths()

    assert str(qinglong_task.REPO_ROOT) in sys.path
    assert os.environ["PYTHONPATH"].split(os.pathsep) == [str(qinglong_task.REPO_ROOT)]


def test_wrapper_scripts_bind_expected_targets() -> None:
    nodeseek_task = importlib.import_module("nodeseek_task")
    deepflood_task = importlib.import_module("deepflood_task")
    v2ex_task = importlib.import_module("v2ex_task")

    assert nodeseek_task.TARGET == "nodeseek"
    assert deepflood_task.TARGET == "deepflood"
    assert v2ex_task.TARGET == "v2ex"
