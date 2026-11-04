from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo


def local_instant(day, local_time, zone):
    # Resolve nonexistent DST wall times forward; ambiguous times run once (fold=0).
    wall = datetime.combine(day, local_time, zone)
    return wall.astimezone(dt_timezone.utc)


def first_run(now, local_time, tz_name):
    zone = ZoneInfo(tz_name)
    day = now.astimezone(zone).date()
    candidate = local_instant(day, local_time, zone)
    if candidate <= now:
        candidate = local_instant(day + timedelta(days=1), local_time, zone)
    return candidate


def following_run(previous, config):
    zone = ZoneInfo(config.timezone)
    day = previous.astimezone(zone).date() + timedelta(days=config.every_days)
    return local_instant(day, config.local_time, zone)
