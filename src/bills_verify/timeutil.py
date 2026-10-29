from __future__ import annotations

from datetime import datetime, timezone


def parse_ts(value) -> datetime:
    """Acepta epoch (int/float/str numérica) o ISO 8601; devuelve datetime en UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    s = str(value).strip()
    if s.replace(".", "", 1).isdigit():
        return datetime.fromtimestamp(float(s), tz=timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
