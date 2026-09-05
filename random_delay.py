import random
import time
from collections.abc import Callable

from runtime_log import log


MAX_RANDOM_START_DELAY_SECONDS = 30 * 60


def format_duration(seconds: float) -> str:
    remaining_seconds = max(0, int(seconds))
    hours, remaining_seconds = divmod(remaining_seconds, 60 * 60)
    minutes, remaining_seconds = divmod(remaining_seconds, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if remaining_seconds or not parts:
        parts.append(f"{remaining_seconds}s")
    return " ".join(parts)


def apply_random_start_delay(
    *,
    randint: Callable[[int, int], int] = random.randint,
    sleep: Callable[[float], None] = time.sleep,
    max_delay_seconds: int = MAX_RANDOM_START_DELAY_SECONDS,
) -> int:
    if max_delay_seconds <= 0:
        return 0

    delay_seconds = randint(0, max_delay_seconds)
    log(
        "Scheduled check-in random start delay: "
        f"{format_duration(delay_seconds)} ({delay_seconds} seconds)"
    )
    sleep(delay_seconds)
    return delay_seconds
