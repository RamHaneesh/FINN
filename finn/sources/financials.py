"""Fast standardized tables. Provenance remains distinct from primary transcript evidence."""
import calendar
from datetime import date, datetime, timedelta
import re

from bs4 import BeautifulSoup

from finn.domain import Citation, FinancialFact, fingerprint, normalize_ticker, utc_now
from finn.sources.http import PublicHTTP, SourceError
from finn.storage import Store

METRICS = [("revenue", "Revenue"), ("ebitda", "EBITDA"), ("pbt", "PBT"), ("pat", "PAT")]


def numeric(value):
    cleaned = value.replace(",", "").replace("%", "").replace("−", "-").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def growth(current, previous):
    if current is None or previous is None or previous <= 0:
        return None
    return round((current / previous - 1) * 100, 2)


class FinancialSource:
    def __init__(self, store: Store, http: PublicHTTP):
        self.store, self.http = store, http

    def fetch(self, ticker, refresh=False):
        ticker = normalize_ticker(ticker)
        cached = None if refresh else self.store.get("financials-v1", ticker, max_age=24 * 3600)
        if cached is not None:
            return cached
        for suffix in ["consolidated/", ""]:
            url = f"https://www.screener.in/company/{ticker}/{suffix}"
            try:
                html = self.http.fetch(url, max_bytes=3_000_000)
                data = self.parse(ticker, url, html)
            except SourceError:
                if suffix:
                    continue
                raise
            self.store.put("financials-v1", ticker, data)
            return data
        raise SourceError("No standardized company financials available")

    @staticmethod
    def parse(ticker, url, html):
        soup = BeautifulSoup(html, "html.parser")
        quarterly = FinancialSource.table(soup, "quarters")
        annual = FinancialSource.table(soup, "profit-loss", annual=True)
        if not quarterly:
            raise SourceError("Quarterly table unavailable for this symbol")
        company = soup.select_one("h1")
        section = soup.find(id="quarters")
        basis = "consolidated" if "consolidated" in section.get_text(" ", strip=True).lower() else "standalone"
        result = {"ticker": ticker, "name": company.get_text(" ", strip=True) if company else ticker, "basis": basis, "source_url": url + "#quarters", "source_type": "standardized_table", "fetched_at": utc_now(), "history": quarterly, "annual": annual,
                  "note": "Source: Screener standardized company financials. EBITDA* is a derived proxy: PBT + interest + depreciation − other income, cross-checked against operating profit. It is not separately disclosed EBITDA and is excluded from guidance comparisons. Unavailable values remain blank."}
        result.update(FinancialSource.headlines(result))
        return result

    @staticmethod
    def table(soup, section_id, annual=False):
        section = soup.find(id=section_id)
        table = section.find("table") if section else None
        if table is None:
            return []
        headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        columns = []
        for index, label in enumerate(headers):
            try:
                parsed = datetime.strptime(label, "%b %Y").date()
            except ValueError:
                continue
            end = parsed.replace(day=calendar.monthrange(parsed.year, parsed.month)[1])
            if annual:
                start = date(end.year - 1, end.month, end.day) + timedelta(days=1)
            else:
                absolute = end.year * 12 + end.month - 3
                start = date(absolute // 12, absolute % 12 + 1, 1)
            columns.append((index, {"label": label, "start": str(start), "end": str(end)}))
        mapping = {"sales": "revenue", "revenue": "revenue", "operating profit": "operating_profit", "ebitda": "ebitda", "profit before tax": "pbt", "net profit": "pat", "interest": "interest", "depreciation": "depreciation", "other income": "other_income"}
        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            label = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).replace("+", "").strip().lower()
            metric = mapping.get(label)
            if metric:
                for index, period in columns:
                    period[metric] = numeric(cells[index].get_text(" ", strip=True)) if index < len(cells) else None
        for _, period in columns:
            parts = [period.get(key) for key in ["pbt", "interest", "depreciation", "other_income", "operating_profit"]]
            if period.get("ebitda") is None and all(value is not None for value in parts):
                pbt, interest, depreciation, other, operating = parts
                derived = pbt + interest + depreciation - other
                if abs(derived - operating) <= max(3, abs(operating) * .02):
                    period["ebitda"] = round(derived, 2)
                    period["ebitda_derived"] = True
        return [period for _, period in columns]

    @staticmethod
    def headlines(snapshot, event_date=None):
        history = snapshot["history"]
        eligible = [row for row in history if not event_date or row["end"] < str(event_date)[:10]]
        if not eligible:
            return {"latest_period": "Unavailable", "metrics": []}
        latest = eligible[-1]
        index = history.index(latest)
        prev = history[index - 1] if index else {}
        year = next((row for row in history if row["end"][:4] == str(int(latest["end"][:4]) - 1) and row["end"][5:7] == latest["end"][5:7]), {})
        return {"latest_period": latest["label"], "source_type": "standardized_table", "source_url": snapshot["source_url"], "metrics": [{"metric": metric, "label": label, "value": latest.get(metric), "qoq": growth(latest.get(metric), prev.get(metric)), "yoy": growth(latest.get(metric), year.get(metric)), "derived": metric == "ebitda" and latest.get("ebitda_derived", False)} for metric, label in METRICS]}

    @staticmethod
    def facts(snapshot):
        facts = []
        observed = datetime.fromisoformat(snapshot["fetched_at"]).date()
        for history in [snapshot["history"], snapshot.get("annual", [])]:
            for index, row in enumerate(history):
                prior_year = next((item for item in history if item["end"][:4] == str(int(row["end"][:4]) - 1) and item["end"][5:] == row["end"][5:]), {})
                metrics = [(key, row.get(key), "INR_crore") for key in ["revenue", "pbt", "pat"]]
                metrics += [("revenue_growth_yoy", growth(row.get("revenue"), prior_year.get("revenue")), "percent")]
                if history is snapshot["history"] and index:
                    metrics.append(("revenue_growth_qoq", growth(row.get("revenue"), history[index - 1].get("revenue")), "percent"))
                for metric, value, unit in metrics:
                    if value is None:
                        continue
                    quote = f"{row['label']} standardized financials: {metric} = {value:g} {unit}."
                    if "growth" in metric:
                        quote += f" Calculated from revenue {row.get('revenue')} and the matching prior period; reported currency."
                    facts.append(FinancialFact(metric=metric, period_start=row["start"], period_end=row["end"], basis=snapshot["basis"], scope="company", currency_basis="reported", unit=unit, value=value, observed_on=observed, citation=Citation(document_id="table:" + fingerprint([snapshot["ticker"], row]), url=snapshot["source_url"], page=None, quote=quote, source_type="standardized_table")))
        return facts
