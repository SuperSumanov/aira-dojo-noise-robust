"""Shared run/Card metadata filters for preference-pair builders."""
from __future__ import annotations

import datetime
from typing import Mapping, Sequence

from ..download_and_resolve.cards import Card


def _validate_integer_range(
    name: str, value_range: tuple[int, int] | None
) -> tuple[int, int] | None:
    if value_range is None:
        return None
    if len(value_range) != 2:
        raise ValueError(f"{name} must contain exactly two integers")
    lower, upper = value_range
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in value_range
    ):
        raise ValueError(f"{name} must contain exactly two integers")
    if lower > upper:
        raise ValueError(f"{name} lower bound must not exceed its upper bound")
    return lower, upper


def _validate_date_range(
    date_range: tuple[str, str] | None,
) -> tuple[datetime.date, datetime.date] | None:
    if date_range is None:
        return None
    if len(date_range) != 2 or any(not isinstance(value, str) for value in date_range):
        raise ValueError("date must contain exactly two ISO date strings")
    try:
        lower, upper = (datetime.date.fromisoformat(value) for value in date_range)
    except ValueError as error:
        raise ValueError("date values must use YYYY-MM-DD format") from error
    if lower > upper:
        raise ValueError("date lower bound must not exceed its upper bound")
    return lower, upper


def _date_from_run_id(run_id: str) -> datetime.date:
    try:
        raw_date = run_id.rsplit("__", 1)[1]
        return datetime.date.fromisoformat(raw_date)
    except (IndexError, ValueError) as error:
        raise ValueError(
            f"Run ID {run_id!r} does not end with '__YYYY-MM-DD'"
        ) from error


def filter_pair_cards(
    cards_by_run_id: Mapping[str, Sequence[Card]],
    *,
    time_limit: tuple[int, int] | None = None,
    execution_timeout: tuple[int, int] | None = None,
    client: str | None = None,
    hardware: str | None = None,
    date: tuple[str, str] | None = None,
) -> dict[str, list[Card]]:
    """Filter Cards and runs using inclusive ranges and substring matches."""
    resolved_time_limit = _validate_integer_range("time_limit", time_limit)
    resolved_execution_timeout = _validate_integer_range(
        "execution_timeout", execution_timeout
    )
    resolved_date_range = _validate_date_range(date)
    if client is not None and not isinstance(client, str):
        raise ValueError("client must be a string")
    if hardware is not None and not isinstance(hardware, str):
        raise ValueError("hardware must be a string")

    filtered_cards_by_run_id: dict[str, list[Card]] = {}
    for run_id, run_cards in cards_by_run_id.items():
        if resolved_date_range is not None:
            run_date = _date_from_run_id(run_id)
            if not resolved_date_range[0] <= run_date <= resolved_date_range[1]:
                continue

        filtered_run_cards = []
        for card in run_cards:
            if resolved_time_limit is not None and not (
                card.time_limit is not None
                and resolved_time_limit[0] <= card.time_limit <= resolved_time_limit[1]
            ):
                continue
            if resolved_execution_timeout is not None and not (
                card.execution_timeout is not None
                and resolved_execution_timeout[0]
                <= card.execution_timeout
                <= resolved_execution_timeout[1]
            ):
                continue
            if client is not None and (
                card.client is None or client not in card.client
            ):
                continue
            if hardware is not None and (
                card.hardware is None or hardware not in card.hardware
            ):
                continue
            filtered_run_cards.append(card)

        if filtered_run_cards:
            filtered_cards_by_run_id[run_id] = filtered_run_cards

    return filtered_cards_by_run_id
