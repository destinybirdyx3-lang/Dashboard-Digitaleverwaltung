"""Gemeinsamer HTTP-Zugriff mit Retry/Backoff (Rate-Limits der Bundes-APIs, kurzzeitige Ausfälle)."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

USER_AGENT = "mh-dashboard/0.1 (Digitalisierungs-Dashboard Stadt Muelheim an der Ruhr)"


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def make_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


@retry(
    retry=retry_if_exception(_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def request(client: httpx.Client, method: str, url: str, **kwargs: object) -> httpx.Response:
    response = client.request(method, url, **kwargs)  # type: ignore[arg-type]
    response.raise_for_status()
    return response
