"""Conservative deterministic comparisons. A source quote is not a guarantee of semantic extraction accuracy."""
from datetime import date

from finn.domain import Comparison, FinancialFact, Narrative

INR_CRORE = {"INR_crore": 1, "INR_lakh": .01, "INR_million": .1, "INR_billion": 100}


def compatible(narrative: Narrative, fact: FinancialFact) -> bool:
    fields = ["metric", "period_start", "period_end", "basis", "scope", "currency_basis"]
    if any(getattr(narrative, field) != getattr(fact, field) for field in fields):
        return False
    if narrative.basis == "unknown" or narrative.scope == "unknown" or narrative.currency_basis == "unknown":
        return False
    if narrative.metric in {"revenue_growth_yoy", "revenue_growth_qoq", "ebitda_margin"} and (narrative.unit != "percent" or fact.unit != "percent"):
        return False
    available = fact.reported_on or fact.observed_on
    if not available or not narrative.stated_on or available <= narrative.stated_on:
        return False
    if fact.reported_on is None and (not fact.period_end or narrative.stated_on > fact.period_end):
        return False  # An observation timestamp is not a historical publication date.
    return narrative.unit != "unknown" and (narrative.unit == fact.unit or (narrative.unit in INR_CRORE and fact.unit in INR_CRORE))


def compare(narrative: Narrative, facts: list[FinancialFact], as_of: date) -> Comparison:
    def outcome(status, explanation, **kwargs):
        return Comparison(narrative=narrative, status=status, explanation=explanation, **kwargs)

    if narrative.narrative_type in {"aspiration", "unclear"}:
        return outcome("Cannot compare", "Context only: this statement is aspirational or unclear.")
    if not narrative.period_start or not narrative.period_end or not narrative.stated_on:
        return outcome("Cannot compare", "The statement lacks an exact target period or statement date.")
    if narrative.stated_on > as_of:
        return outcome("Cannot compare", "The statement was made after the selected assessment date.")
    if narrative.period_end > as_of:
        return outcome("Pending", "The target period has not ended.")
    candidates = [fact for fact in facts if compatible(narrative, fact) and (fact.reported_on or fact.observed_on) <= as_of]
    if not candidates:
        return outcome("Cannot compare", "No later actual matches the metric, period, reporting basis, currency basis and scope.")
    # Conflicting restatements are not silently resolved by choosing whichever supports the narrative.
    converted = [fact.value * INR_CRORE[fact.unit] / INR_CRORE[narrative.unit] if fact.unit in INR_CRORE and narrative.unit in INR_CRORE else fact.value for fact in candidates]
    if max(converted) - min(converted) > 1e-6:
        return outcome("Cannot compare", "Matching sources contain conflicting actuals; inspect the disclosures.")
    actual, value = candidates[0], converted[0]
    lower, upper = narrative.lower, narrative.upper
    if narrative.narrative_type == "directional":
        return outcome("Cannot compare", "Directional comparison requires a validated baseline, which is not implemented yet.", actual=actual)
    if lower is None and upper is None:
        return outcome("Cannot compare", "No numerical target was disclosed.", actual=actual)
    if lower is not None and value < lower - 1e-6:
        delta, relationship = value - lower, "below"
        status = "Missed"
    elif upper is not None and value > upper + 1e-6:
        delta, relationship = value - upper, "above"
        status = "Met"  # Revenue growth/margin above guidance is shown as exceeded, not a negative miss.
    else:
        delta, relationship, status = 0., "within", "Met"
    suffix = "percentage points" if narrative.unit == "percent" else narrative.unit
    explanation = f"Actual {value:g} {narrative.unit} is {relationship} the disclosed target"
    explanation += f" by {abs(delta):g} {suffix}." if delta else "."
    return outcome(status, explanation, actual=actual, relationship=relationship, difference=round(delta, 6))
