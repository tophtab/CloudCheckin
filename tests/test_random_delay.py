import random_delay
from tests.log_assertions import assert_timestamped_lines


def test_apply_random_start_delay_respects_custom_max(capsys) -> None:
    randint_calls = []
    sleep_calls = []

    def randint(start: int, end: int) -> int:
        randint_calls.append((start, end))
        return 7

    result = random_delay.apply_random_start_delay(
        randint=randint,
        sleep=sleep_calls.append,
        max_delay_seconds=120,
    )

    assert result == 7
    assert randint_calls == [(0, 120)]
    assert sleep_calls == [7]

    output = capsys.readouterr().out
    assert_timestamped_lines(output)
    assert "(7 seconds)" in output


def test_apply_random_start_delay_zero_max_disables_delay(capsys) -> None:
    randint_calls = []
    sleep_calls = []

    def randint(start: int, end: int) -> int:
        randint_calls.append((start, end))
        return 5

    result = random_delay.apply_random_start_delay(
        randint=randint,
        sleep=sleep_calls.append,
        max_delay_seconds=0,
    )

    assert result == 0
    assert randint_calls == []
    assert sleep_calls == []
    assert capsys.readouterr().out == ""
