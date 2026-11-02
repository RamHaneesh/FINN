"""Daily portfolio refresh, independent of browser sessions and research jobs."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def queue_daily_refresh(store, now=None):
    local = (now or datetime.now(timezone.utc)).astimezone(IST)
    if (local.hour, local.minute) < (18, 30):
        return None
    # On restart after 18:30, catch up today's run once; never replay older days.
    return store.enqueue_daily_refresh(local.date().isoformat())
