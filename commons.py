"""Небольшой вежливый клиент MediaWiki API Викисклада (Wikimedia Commons).

- один запрос за раз, пауза между запросами (config: api.delay_s);
- User-Agent с описанием проекта (без личных данных);
- при 429/503 ждёт столько, сколько просит сервер (Retry-After), и повторяет;
- параметр maxlag, чтобы не нагружать сервер в часы пик.
"""
import time
import requests

API = "https://commons.wikimedia.org/w/api.php"


class Commons:
    def __init__(self, user_agent: str, delay_s: float = 2.0, max_retries: int = 6):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent
        self.s.headers["Accept-Encoding"] = "gzip"
        self.delay = delay_s
        self.max_retries = max_retries
        self._last = 0.0
        self.requests_made = 0

    def _wait(self):
        dt = time.monotonic() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.monotonic()

    def get(self, **params) -> dict:
        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        for attempt in range(self.max_retries):
            self._wait()
            try:
                r = self.s.get(API, params=params, timeout=60)
            except requests.RequestException as e:
                wait = 5 * (attempt + 1)
                print(f"  сеть: {e!r}, повтор через {wait} с")
                time.sleep(wait)
                continue
            self.requests_made += 1
            if r.status_code in (429, 503) or (r.status_code == 200 and '"maxlag"' in r.text[:200]):
                wait = int(r.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
                wait = min(max(wait, 5), 120)
                print(f"  сервер просит подождать ({r.status_code}), жду {wait} с")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        raise RuntimeError(f"API не ответил после {self.max_retries} попыток: {params}")

    def query_all(self, **params):
        """Итерация по всем страницам ответа (continue)."""
        cont = {}
        while True:
            data = self.get(action="query", **params, **cont)
            yield data
            if "continue" not in data:
                return
            cont = data["continue"]
