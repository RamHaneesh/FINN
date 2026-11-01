"""Fill absent company context without rerunning saved management research."""
import logging

from finn.sources.financials import FinancialSource
from finn.sources.profile import CACHE, ProfileSource
from finn.services.trajectory import cached_trajectory


def missing_sections(store, ticker):
    profile = store.get(CACHE, ticker)
    financials = store.get('financials-v1', ticker)
    return {'business': not profile or profile.get('status') != 'ready',
            'financials': not financials or not financials.get('history'),
            'trajectory': not financials or not financials.get('annual'),
            # A completed report with zero findings is valid, not a missing section.
            'research': not bool(store.get('research-v1', ticker)) and not bool(store.get('research-availability-v1',ticker))}


def fill_context(pipeline, ticker):
    missing = missing_sections(pipeline.store, ticker)
    if missing['business']:
        try:
            ProfileSource(pipeline.store, pipeline.http).fetch(ticker, refresh=True)
        except Exception as exc:
            logging.getLogger(__name__).warning('Profile fill for %s: %s', ticker, type(exc).__name__)
    financials = pipeline.store.get('financials-v1', ticker)
    if not financials or not financials.get('history') or not financials.get('annual'):
        try:
            financials = FinancialSource(pipeline.store, pipeline.http).fetch(ticker, refresh=True)
        except Exception as exc:
            logging.getLogger(__name__).warning('Financial fill for %s: %s', ticker, type(exc).__name__)
    if financials:
        cached_trajectory(pipeline.store, ticker, financials)
