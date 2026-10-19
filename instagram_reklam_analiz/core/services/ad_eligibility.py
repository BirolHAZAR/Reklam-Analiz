"""Shared read policy for currently active advertising entities."""
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def is_current_campaign(row, *, today=None, now=None, zone=None):
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    if row.get("status") not in {"ACTIVE", "ENABLED"}:
        return False
    if row.get("effective_status", row["status"]) not in {"ACTIVE", "ENABLED"}:
        return False
    for keys, is_end in ((("start_time", "startDateTime", "start_date"), False),
                         (("stop_time", "end_time", "endDateTime", "end_date"), True)):
        value = next((row.get(key) for key in keys if row.get(key)), None)
        if not value:
            continue
        value = str(value)
        if len(value) == 10:
            try:
                day = parse_date(value)
            except ValueError:
                return False
            if day is None or ((is_end and day < today) or (not is_end and day > today)):
                return False
        else:
            try:
                stamp = parse_datetime(value)
            except ValueError:
                return False
            if stamp:
                if timezone.is_naive(stamp):
                    from zoneinfo import ZoneInfo
                    stamp = timezone.make_aware(stamp, ZoneInfo(zone) if zone else None)
                if (is_end and stamp <= now) or (not is_end and stamp > now):
                    return False
            else:
                return False
    return True
