"""Direct public company-profile text. No transcripts, PDFs or generative model."""
import re
from bs4 import BeautifulSoup
from finn.domain import normalize_ticker, utc_now
from finn.sources.http import SourceError

CACHE = 'business-profile-v2'

def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'\[\d+\]', '', text)).strip()

def sentences(text, limit=2):
    parts = re.split(r'(?<!Ltd\.)(?<!Inc\.)(?<!Mr\.)(?<=[.!?])\s+(?=[A-Z])', clean(text))
    return ' '.join(parts[:limit])

class ProfileSource:
    def __init__(self, store, http):
        self.store, self.http = store, http

    @staticmethod
    def parse(ticker, url, html):
        soup = BeautifulSoup(html, 'html.parser')
        profile = soup.select_one('.company-profile')
        about = profile.select_one('.about') if profile else None
        if not about:
            raise SourceError('No public company description in profile')
        for element in profile.select('sup, script, style, .show-more-button, button'):
            element.decompose()
        about_text = clean(about.get_text(' ', strip=True))
        if not about_text:
            raise SourceError('Empty company profile')
        description = sentences(about_text)
        commentary = profile.select_one('.commentary')
        segments, products, mix = [], [], []
        for passage in re.split(r'(?<=[.!?])\s+(?=[A-Z])', about_text):
            if re.search(r'\bbrands?\b', passage, re.I) and passage not in description:
                products.append(passage)
        if commentary:
            for paragraph in commentary.select('p'):
                text = clean(paragraph.get_text(' ', strip=True))
                segment_context = bool(re.search(r'business segments?|revenue (?:mix|break.?up|segments?)|segment.?wise|geograph', text, re.I))
                previous_mix_count = len(mix)
                for strong in paragraph.select('strong'):
                    label = clean(strong.get_text(' ', strip=True)).strip(': ')
                    dated_share = bool(re.search(r'\d+(?:\.\d+)?\s*%.*(?:FY\s*\d{2,4}|20\d{2})', label, re.I))
                    if segment_context and dated_share and not re.search(r'market share|margin|growth|ROCE|ROE', label, re.I):
                        label = re.sub(r'^[a-zA-Z]\)\s*', '', label)
                        if label not in mix:
                            mix.append(label)
                    elif segment_context and re.match(r'^[a-zA-Z]\)\s*', label) and not dated_share:
                        segments.append(re.sub(r'^[a-zA-Z]\)\s*', '', label))
                if re.match(r'(?:brands?|products?|product portfolio|retail formats?|business verticals?)\b', text, re.I):
                    products.append(sentences(text, 2))
                if (segment_context and len(mix) == previous_mix_count and re.search(r'\d+(?:\.\d+)?\s*%.*(?:FY\s*\d{2,4}|20\d{2})', text, re.I)
                        and not re.search(r'market share|margin|growth|ROCE|ROE', text, re.I)):
                    mix.append(sentences(text, 2))
            if len(re.split(r'(?<=[.!?])\s+(?=[A-Z])', description)) < 2:
                for paragraph in commentary.select('p'):
                    text = clean(paragraph.get_text(' ', strip=True))
                    if re.match(r'part of .*group\b', text, re.I):
                        heading = paragraph.find('strong')
                        if heading:
                            description += ' ' + clean(heading.get_text(' ', strip=True)).rstrip('.') + '.'
                        break
        company = soup.select_one('h1')
        return {'status': 'ready', 'source_type': 'company_profile', 'source_name': 'Screener company profile',
                'ticker': ticker, 'name': company.get_text(' ', strip=True) if company else ticker,
                'description': description, 'segments': segments[:6], 'revenue_mix': mix[:8], 'products': products[:3],
                'source_url': url.split('#')[0], 'generated_at': utc_now(),
                'note': 'Copied from the public company profile. Segment percentages retain the profile’s reporting periods; they are not current estimates.',
                'profile_text': about_text}

    def fetch(self, ticker, refresh=False):
        ticker = normalize_ticker(ticker)
        existing = self.store.get(CACHE, ticker)
        if existing and existing.get('status') == 'ready' and not refresh:
            return existing
        for suffix in ['consolidated/', '']:
            url = f'https://www.screener.in/company/{ticker}/{suffix}'
            try:
                html = self.http.fetch(url, max_bytes=3_000_000)
                result = self.parse(ticker, url, html)
            except Exception:
                continue
            self.store.put(CACHE, ticker, result)
            if not self.store.get('financials-v1', ticker):
                from finn.sources.financials import FinancialSource
                try:
                    self.store.put('financials-v1', ticker, FinancialSource.parse(ticker, url, html))
                except SourceError:
                    pass
            return result
        if existing and existing.get('status') == 'ready':
            return existing
        result = {'status': 'profile_link', 'source_type': 'company_profile', 'source_name': 'Screener company profile',
                  'ticker': ticker, 'description': None, 'segments': [], 'revenue_mix': [], 'products': [],
                  'source_url': f'https://www.screener.in/company/{ticker}/', 'generated_at': utc_now()}
        self.store.put(CACHE, ticker, result)
        return result
