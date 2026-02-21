from __future__ import annotations

from datetime import datetime, timezone

PRIMARY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_timestamp_components(cleaned: str) -> tuple[datetime, str]:
    valid_length = len(cleaned) in (16, 19)
    if not valid_length:
        raise ValueError(
            "Invalid timestamp format. Expected 'YYYY-MM-DD HH:mm:ss' (or HH:mm)."
        )

    if (
        cleaned[4] != "-"
        or cleaned[7] != "-"
        or cleaned[10] != " "
        or cleaned[13] != ":"
        or (len(cleaned) == 19 and cleaned[16] != ":")
    ):
        raise ValueError(
            "Invalid timestamp format. Expected 'YYYY-MM-DD HH:mm:ss' (or HH:mm)."
        )

    try:
        year = int(cleaned[0:4])
        month = int(cleaned[5:7])
        day = int(cleaned[8:10])
        hour = int(cleaned[11:13])
        minute = int(cleaned[14:16])
        second = int(cleaned[17:19]) if len(cleaned) == 19 else 0
    except ValueError as exc:
        raise ValueError(
            "Invalid timestamp format. Expected 'YYYY-MM-DD HH:mm:ss' (or HH:mm)."
        ) from exc

    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ValueError(
            "Invalid timestamp format. Expected 'YYYY-MM-DD HH:mm:ss' (or HH:mm)."
        ) from exc

    normalized = cleaned if len(cleaned) == 19 else f"{cleaned}:00"
    return dt, normalized


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp must be a non-empty string.")

    cleaned = value.strip()
    dt, _normalized = _parse_timestamp_components(cleaned)
    return dt


def to_epoch_seconds(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def parse_timestamp_to_epoch(value: str) -> tuple[str, int]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp must be a non-empty string.")

    cleaned = value.strip()
    dt, normalized = _parse_timestamp_components(cleaned)
    return normalized, to_epoch_seconds(dt)


def format_timestamp(dt: datetime) -> str:
    return dt.strftime(PRIMARY_TIMESTAMP_FORMAT)
