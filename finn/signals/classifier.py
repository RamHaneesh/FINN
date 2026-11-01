"""All 17 brief categories, deterministic triage with explicit review status."""
import re

CATEGORIES = ["results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading", "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex", "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified"]
HIGH = {"results", "management_change", "M&A", "litigation", "fund_raise"}


def classify(subject, description=""):
    text = re.sub(r"\s+", " ", f"{subject} {description}".lower())
    # Specific material disclosures precede routine wrapper words.
    rules = [
        ("litigation", r"litigat|lawsuit|penalt|regulatory order|insolvenc|fraud|arbitrat|show cause|tax demand|sebi order|court order|restructuring"),
        ("M&A", r"acquisi|\bmerger\b|demerger|joint venture|sale of.*stake|divest|amalgamat"),
        ("management_change", r"change in (management|director|key managerial)|resign|appoint.*(director|chief|cfo|ceo|managing)|retire.*(director|chief)|cessation|key managerial personnel"),
        ("fund_raise", r"rights issue|\bqip\b|qualified institution|preferential|buy.?back|commercial paper|debenture|fund rais|issuance of.*(equity|debt)|allotment.*(rights|preferential)"),
        ("pledging", r"pledge|pledging|encumbrance"),
        ("insider_trading", r"insider trading|\bpit\b|promoter.*(buy|sell|disposal|acquisition)|disclosure.*(7\(2\)|29\(2\))"),
        ("credit_rating", r"credit rating|rating.*(affirm|upgrade|downgrade)|ratings? assignment"),
        ("earnings_call", r"earnings call|conference call|concall|transcript|audio recording|video recording|investor call"),
        ("investor_meetings", r"investor meet|analyst meet|investor conference|schedule.*(investor|analyst)|one.on.one"),
        ("results", r"financial result|quarterly result|annual result|financial statement|results.*(quarter|year)"),
        ("bonus_split", r"bonus issue|bonus share|stock split|sub.division|split.*share"),
        ("dividend", r"dividend"),
        ("capex", r"capacity expansion|capital expenditure|\bcapex\b|new (plant|facility|factory)|commissioning|capacity addition"),
        ("postal_ballot", r"postal ballot|e.voting.*postal"),
        ("agm_egm", r"annual general meeting|extraordinary general meeting|\bagm\b|\begm\b"),
        ("press_release", r"press release|order win|new product|partnership|clarification|rumou?r"),
    ]
    category = next((name for name, pattern in rules if re.search(pattern, text)), "unclassified")
    routine = bool(re.search(r"newspaper|publication|trading window|esop|employee stock|compliance certificate|reconciliation.*capital|board meeting intimation|meeting intimation|notice.*board meeting", text))
    if category == "results" and re.search(r"meeting.*scheduled|scheduled.*meeting|to consider and approve|to consider.*financial results", text):
        routine = True  # A future approval notice is not a released results filing.
    # ESOP/allotment paperwork and result-publication notices are not financial results.
    if routine and category not in {"litigation", "M&A", "management_change", "fund_raise"}:
        priority = "routine"
    else:
        priority = "high" if category in HIGH or (category == "credit_rating" and "downgrade" in text) else "normal"
    if category == "unclassified":
        priority = "routine"
    return {"category": category, "priority": priority, "review_required": priority == "high", "reason": "Potentially material disclosure; open the filing to assess its scale." if priority == "high" else "Saved for context; no high-priority trigger identified in the filing metadata."}
