"""Prior-year delivery, active measurable targets, and ungraded context."""
import calendar
from datetime import date, datetime, timedelta
import re

from finn.analysis.compare import compare


def review_period(as_of, snapshot=None, facts=()):
    annual = (snapshot or {}).get("annual", [])
    ends = [date.fromisoformat(row["end"]) for row in annual if row.get("end") and date.fromisoformat(row["end"]) <= as_of]
    if not ends:
        ends = [fact.period_end for fact in facts if fact.period_start and fact.period_end and 300 <= (fact.period_end-fact.period_start).days <= 380 and fact.period_end <= as_of]
    anchor = max(ends) if ends else date(as_of.year, 3, 31)
    end = date(as_of.year, anchor.month, min(anchor.day, calendar.monthrange(as_of.year, anchor.month)[1]))
    if end > as_of:
        end = date(end.year-1, end.month, min(end.day, calendar.monthrange(end.year-1, end.month)[1]))
    previous_end = date(end.year-1, end.month, min(end.day, calendar.monthrange(end.year-1, end.month)[1]))
    return {"label": f"FY{end.year}", "start": str(previous_end+timedelta(days=1)), "end": str(end), "calendar_verified": bool(ends)}


def measurable(statement, as_of):
    return (statement.narrative_type == "guidance" and (statement.lower is not None or statement.upper is not None)
            and statement.period_start is not None and statement.period_end is not None
            and statement.stated_on is not None and statement.stated_on <= min(as_of, statement.period_end)
            and statement.basis != "unknown" and statement.scope != "unknown"
            and statement.currency_basis != "unknown" and statement.unit != "unknown")


def collapse_revisions(comparisons, distinct_targets=False):
    grouped = {}
    for item in comparisons:
        n = item["narrative"]
        key = tuple(n[field] for field in ["metric", "period_start", "period_end", "basis", "scope", "currency_basis", "unit"])
        if distinct_targets:
            key += (n["lower"], n["upper"])
        grouped.setdefault(key, []).append(item)
    result = []
    for values in grouped.values():
        values.sort(key=lambda item: item["narrative"]["stated_on"])
        latest = dict(values[-1])
        latest["prior_guidance"] = [item["narrative"] for item in values[:-1]]
        result.append(latest)
    return sorted(result, key=lambda item: (item["narrative"]["period_end"], item["narrative"]["metric"]))


def guidance_review(statements, facts, as_of, snapshot=None):
    period = review_period(as_of, snapshot, facts)
    start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
    completed, active, context = [], [], []
    for statement in statements:
        comparison = compare(statement, facts, as_of).model_dump(mode="json")
        clear = measurable(statement, as_of)
        in_year = bool(statement.period_start and statement.period_end and start <= statement.period_start <= statement.period_end <= end)
        if clear and in_year and period["calendar_verified"] and comparison["status"] in {"Met", "Missed"}:
            completed.append(comparison)
        elif clear and statement.period_end > as_of:
            active.append(comparison)
        else:
            if statement.narrative_type == "aspiration":
                reason = "Long-term aspiration"
            elif statement.narrative_type in {"unclear", "directional"}:
                reason = "Qualitative or directional statement"
            elif not clear:
                reason = "Target period or reporting basis needs clarification"
            elif not in_year:
                reason = "Other completed period"
            elif not period["calendar_verified"]:
                reason = "Financial-year calendar needs verification"
            else:
                reason = "Matching actual not yet established"
            comparison["context_reason"] = reason
            context.append(comparison)
    # Preserve changed historical targets as separate graded comparisons; collapse only repetitions.
    completed, active = collapse_revisions(completed, distinct_targets=True), collapse_revisions(active)
    return {"period": period, "completed": completed, "active": active, "context": context,
            "met": sum(item["status"] == "Met" for item in completed), "missed": sum(item["status"] == "Missed" for item in completed)}


def transcript_month(link):
    if link.published_on:
        return link.published_on
    match = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d{2})\b", link.title)
    return datetime.strptime(match.group(), "%b %Y").date() if match else None


def select_transcripts(links, period, as_of, limit=6):
    """Sample prior-year calls, the subsequent results call, and one latest active call."""
    transcripts = [link for link in links if link.kind.value == "transcript"]
    dated = [(link, transcript_month(link)) for link in transcripts]
    dated = [(link, day) for link, day in dated if day and day <= as_of]
    start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
    buckets = {}
    for link, day in sorted(dated, key=lambda pair: pair[1]):
        if start <= day <= end:
            quarter = ((day.year-start.year)*12 + day.month-start.month)//3
            buckets.setdefault(quarter, link)  # Avoid replacing the quarter's call with a later one-off call.
    historical = [buckets[key] for key in sorted(buckets)]
    after = [link for link, day in sorted(dated, key=lambda pair: pair[1]) if end < day <= end+timedelta(days=100)]
    latest = [link for link, _ in sorted(dated, key=lambda pair: pair[1], reverse=True)][:1]
    priority = historical[-1:] + after[:1] + historical[:1] + list(reversed(historical[1:-1])) + latest
    # Unknown dates can still be inspected when an archive does not expose its period.
    selected, seen = [], set()
    for link in priority + transcripts:
        if link.url not in seen:
            selected.append(link)
            seen.add(link.url)
        if len(selected) >= limit:
            break
    return selected
