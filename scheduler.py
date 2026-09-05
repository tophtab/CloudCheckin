import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from checkin_runner import (
    TargetExecutionError,
    parse_targets,
    run_targets,
    validate_target_cookies,
)
from random_delay import (
    MAX_RANDOM_START_DELAY_SECONDS,
    apply_random_start_delay,
    format_duration,
)
from runtime_log import log


DEFAULT_CRON = "30 3 * * *"
DEFAULT_TIMEZONE = "Asia/Shanghai"
WAIT_STATUS_INTERVAL_SECONDS = 60 * 60


def load_schedule_config() -> tuple[str, str, ZoneInfo]:
    timezone_name = os.environ.get("TZ", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    cron_expression = os.environ.get("CHECKIN_CRON", DEFAULT_CRON).strip() or DEFAULT_CRON

    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as err:
        raise ValueError(f"Unknown timezone: {timezone_name}") from err

    if not croniter.is_valid(cron_expression):
        raise ValueError(f"Invalid CHECKIN_CRON expression: {cron_expression}")

    return cron_expression, timezone_name, timezone


def get_next_run(now: datetime, cron_expression: str) -> datetime:
    return croniter(cron_expression, now).get_next(datetime)


def format_timestamp(value: datetime) -> str:
    zone_name = getattr(value.tzinfo, "key", None) or value.tzname()
    offset = value.utcoffset()

    if offset is None:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    offset_hours, offset_minutes = divmod(total_minutes, 60)
    offset_text = f"UTC{sign}{offset_hours:02d}:{offset_minutes:02d}"
    timestamp = value.strftime("%Y-%m-%d %H:%M:%S")

    if zone_name:
        return f"{timestamp} {zone_name} ({offset_text})"
    return f"{timestamp} ({offset_text})"


def sleep_until(
    target_time: datetime,
    *,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] | None = None,
    status_log_interval_seconds: int = WAIT_STATUS_INTERVAL_SECONDS,
) -> None:
    now_factory = now or (lambda: datetime.now(target_time.tzinfo))
    last_status_log: datetime | None = None

    while True:
        current_time = now_factory()
        seconds_remaining = (target_time - current_time).total_seconds()
        if seconds_remaining <= 0:
            return

        should_log_status = last_status_log is None or (
            current_time - last_status_log
        ).total_seconds() >= status_log_interval_seconds
        if should_log_status:
            log(
                "Waiting for next run at "
                f"{format_timestamp(target_time)} "
                f"({format_duration(seconds_remaining)} remaining)"
            )
            last_status_log = current_time

        sleep(min(seconds_remaining, 60))


def main() -> int:
    cron_expression, timezone_name, timezone = load_schedule_config()
    targets = parse_targets()
    validate_target_cookies(targets)
    scheduler_started_at = datetime.now(timezone)

    log(
        f"Scheduler started at {format_timestamp(scheduler_started_at)} with "
        f"TZ={timezone_name}, CHECKIN_CRON={cron_expression}, "
        f"CHECKIN_TARGETS={','.join(targets)}"
    )

    while True:
        now = datetime.now(timezone)
        next_run = get_next_run(now, cron_expression)
        log(f"Next run scheduled at {format_timestamp(next_run)}")
        sleep_until(next_run)
        apply_random_start_delay()

        started_at = datetime.now(timezone)
        log(f"Starting scheduled check-in at {format_timestamp(started_at)}")
        try:
            run_targets(targets)
        except TargetExecutionError:
            finished_at = datetime.now(timezone)
            log(f"Scheduled check-in failed at {format_timestamp(finished_at)}")
            raise
        finished_at = datetime.now(timezone)
        log(f"Scheduled check-in finished at {format_timestamp(finished_at)}")
        continue


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Scheduler stopped by user")
        sys.exit(0)
    except Exception as err:
        log(err)
        sys.exit(1)
