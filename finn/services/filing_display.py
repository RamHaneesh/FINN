"""Conservative display fields from explicit filing metadata; no inferred people."""
import re


def management_fields(subject, description):
    text = re.sub(r"\s+", " ", f"{subject}. {description}")
    name = r"(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,4}?)"
    role = r"((?:Chief\s+(?:Executive|Financial|Operating)\s+Officer)|(?:Managing\s+Director)|(?:Company\s+Secretary)|(?:(?:Independent|Non-Executive|Executive)\s+Director)|CEO|CFO|COO)"
    # Require the action, person and role in one contiguous disclosure.
    patterns = [
        rf"(?P<action>appointment|resignation)\s+of\s+{name}\s*(?:,\s*|as(?: the)?\s+|from(?: the)?\s+){role}",
        rf"{name}\s*(?:,|as)?\s*{role}\s*(?:,)?\s*(?:has\s+)?(?P<action>resigned|joined|appointed)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            values = [value for value in match.groups() if value != match.group('action')]
            if re.search(r"re-?appoint|propos|recommend|subject to|shall|will", text, re.I):
                return None
            return {"person": values[0].strip(), "role": values[1].strip(),
                    "action": "Resigned" if match.group('action').lower().startswith('resign') else "Joined"}
    return None
