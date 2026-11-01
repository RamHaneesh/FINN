"""Company profile, independent of narrative research and model access."""
from finn.sources.profile import ProfileSource

def build_business(pipeline, ticker, refresh=False):
    return ProfileSource(pipeline.store, pipeline.http).fetch(ticker, refresh=refresh)
