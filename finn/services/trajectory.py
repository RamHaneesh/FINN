"""Deterministic annual trends; no model-generated numbers or chart coordinates."""
from datetime import date, datetime
from math import isfinite
from zoneinfo import ZoneInfo

from finn.domain import fingerprint, utc_now


def calculate(snapshot):
    rows = []
    for row in sorted(snapshot.get('annual', []), key=lambda item: item['end']):
        start, end = date.fromisoformat(row['start']), date.fromisoformat(row['end'])
        if not 300 <= (end-start).days <= 380 or end > datetime.now(ZoneInfo('Asia/Kolkata')).date():
            continue
        revenue, ebitda = row.get('revenue'), row.get('ebitda')
        rows.append({**row, 'ebitda_margin': round(ebitda/revenue*100, 2) if revenue and revenue > 0 and ebitda is not None else None})
    annual_rows = rows
    rows = rows[-5:]
    table = []
    for row in rows:
        prior = next((old for old in annual_rows if old['end'] == str(int(row['end'][:4])-1)+row['end'][4:]), {})
        previous, current = prior.get('revenue'), row.get('revenue')
        table.append({'year': 'FY'+row['end'][:4], 'period': row['label'], 'end': row['end'],
                      'revenue': current, 'revenue_yoy': round((current/previous-1)*100, 2) if previous is not None and previous > 0 and current is not None else None,
                      'ebitda_margin': row['ebitda_margin'], 'ebitda_derived': row.get('ebitda_derived', False), 'pat': row.get('pat')})
    summary = {}
    if len(annual_rows) >= 2:
        first, last = annual_rows[max(0, len(annual_rows)-6)], annual_rows[-1]
        years = (date.fromisoformat(last['end'])-date.fromisoformat(first['end'])).days/365.2425
        for metric in ['revenue', 'pat']:
            start, end = first.get(metric), last.get(metric)
            summary[metric] = {'cagr': round(((end/start)**(1/years)-1)*100, 2) if years > 0 and start is not None and end is not None and start > 0 and end > 0 else None,
                               'years': round(years, 1), 'start': first['label'], 'end': last['label']}
    series = []
    for metric, label, unit in [('revenue', 'Revenue', '₹ crore'), ('pat', 'PAT', '₹ crore'), ('ebitda_margin', 'EBITDA margin', '%')]:
        values = [row.get(metric) for row in rows]
        valid = [value for value in values if value is not None and isfinite(value)]
        low, high = min(valid, default=0), max(valid, default=0)
        # Include zero for amount charts; preserve negative profit values.
        if unit != '%':
            low, high = min(0, low), max(0, high)
        spread = high-low or max(abs(high)*.1, 1)
        points = [{'label': row['label'], 'value': value,
                   'x': round(12 + index*264/max(1, len(rows)-1), 2),
                   'y': round(82 - (value-low)/spread*66, 2) if value is not None else None}
                  for index, (row, value) in enumerate(zip(rows, values))]
        change = cagr = None
        if len(rows) >= 2 and values[0] is not None and values[-1] is not None:
            change = round(values[-1]-values[0], 2)
            years = (date.fromisoformat(rows[-1]['end'])-date.fromisoformat(rows[0]['end'])).days/365.2425
            if unit != '%' and values[0] > 0 and values[-1] > 0:
                cagr = round(((values[-1]/values[0])**(1/years)-1)*100, 2)
        series.append({'metric': metric, 'label': label, 'unit': unit, 'points': points, 'cagr': cagr,
                       'change': change, 'derived': metric == 'ebitda_margin' and any(row.get('ebitda_derived') for row in rows)})
    return {'periods': [row['label'] for row in rows], 'series': series, 'rows': table, 'summary': summary, 'basis': snapshot['basis'],
            'source_url': snapshot['source_url'].split('#')[0]+'#profit-loss', 'source_type': 'standardized_table', 'source_ticker': snapshot.get('source_ticker', snapshot.get('ticker')),
            'generated_at': utc_now(), 'note': 'Completed annual periods only; TTM excluded. YoY compares the same fiscal year-end one year earlier. Five-year CAGR uses an additional preceding annual observation where available; shorter available history is labeled. Missing or non-positive endpoints have no CAGR. EBITDA margin* uses the same derived proxy as the snapshot.' + (' Watchlist label '+snapshot['ticker']+'; source symbol '+snapshot['source_ticker']+'. Historical periods may span corporate reorganisations.' if snapshot.get('source_ticker') and snapshot.get('ticker')!=snapshot['source_ticker'] else '')}


def cached_trajectory(store, ticker, snapshot):
    if not snapshot:
        return None
    key = fingerprint({'version': 3, 'annual': snapshot.get('annual', []), 'basis': snapshot['basis']})
    saved = store.get('trajectory-v1', ticker)
    if saved and saved['input_key'] == key:
        return saved
    result = dict(calculate(snapshot), input_key=key)
    store.put('trajectory-v1', ticker, result)
    return result
