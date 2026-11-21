"""Retrying the first database connection while Azure SQL resumes from a pause."""

import pytest

from app.db import connect_with_retry


class Refused(Exception):
    pass


def test_returns_once_the_database_answers() -> None:
    calls: list[int] = []
    waits: list[float] = []

    def connect() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise Refused
        return "connection"

    assert connect_with_retry(connect, Refused, sleep=waits.append) == "connection"
    assert len(calls) == 3
    assert waits == [2, 4]


def test_gives_up_after_the_last_attempt() -> None:
    waits: list[float] = []

    def connect() -> str:
        raise Refused

    with pytest.raises(Refused):
        connect_with_retry(connect, Refused, attempts=6, sleep=waits.append)
    assert waits == [2, 4, 8, 15, 15]


def test_other_errors_are_not_retried() -> None:
    def connect() -> str:
        raise ValueError("bad connection string")

    with pytest.raises(ValueError):
        connect_with_retry(connect, Refused, sleep=lambda _: None)
