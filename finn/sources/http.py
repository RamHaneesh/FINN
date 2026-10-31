import ipaddress
from urllib.parse import urlsplit

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class SourceError(RuntimeError):
    pass


def public_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SourceError("Source must be a public HTTPS URL without embedded credentials")
    host = parsed.hostname.lower()
    if host == "localhost" or "." not in host or host.endswith((".local", ".internal")):
        raise SourceError("Local sources are not supported")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise SourceError("Private network sources are not supported")
    return url


class PublicHTTP:
    def __init__(self, timeout=30):
        self.timeout = timeout

    @retry(retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)), stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=3), reraise=True)
    def fetch(self, url: str, max_bytes: int = 30_000_000) -> bytes:
        public_url(url)
        with httpx.Client(timeout=self.timeout, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0 (compatible; FINN/0.1)"}) as client:
            for _ in range(6):
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        from urllib.parse import urljoin
                        url = public_url(urljoin(url, response.headers["location"]))
                        continue
                    if response.status_code != 200:
                        raise SourceError(f"Source returned HTTP {response.status_code}")
                    parts, total = [], 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise SourceError("Document exceeds configured download limit")
                        parts.append(chunk)
                    return b"".join(parts)
        raise SourceError("Too many source redirects")
