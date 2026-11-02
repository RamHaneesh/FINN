"""Fixed Push membership and an initial, unpinned Pull warm-up list."""
import json
from finn.config import ROOT

COMPANIES = json.loads((ROOT/'config/pull_universe.json').read_text())['companies']
PUSH_COMPANIES = json.loads((ROOT/'config/portfolio.json').read_text())['companies']
SOURCE_SYMBOLS = {item['ticker']:item.get('source_ticker',item['ticker']) for item in COMPANIES}


def source_symbol(ticker):
    return SOURCE_SYMBOLS.get(ticker,ticker)
