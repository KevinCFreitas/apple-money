import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval={interval}&range={range}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

CURRENCY_LABELS = {
    "BRL": "R$",
    "USD": "US$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "ARS": "$",
    "CAD": "C$",
    "AUD": "A$",
}


def parse_price(text):
    """Converte textos como 'R$ 55,04', '1.234,56' ou '55.04' em float."""
    if text is None:
        raise ValueError("texto de preço vazio")

    clean = re.sub(r"[^\d,.\-]", "", str(text)).strip()
    if not clean or clean in {"-", ".", ","}:
        raise ValueError(f"preço inválido: {text!r}")

    has_comma = "," in clean
    has_dot = "." in clean

    if has_comma and has_dot:
        if clean.rfind(",") > clean.rfind("."):
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(",", "")
    elif has_comma:
        clean = clean.replace(",", ".")

    return float(clean)


def _yahoo_chart(symbol, interval="1m", range_="1d"):
    symbol = (symbol or "").strip()
    if not symbol:
        raise ValueError("símbolo vazio")

    url = YAHOO_CHART_URL.format(
        symbol=urllib.parse.quote(symbol, safe=""),
        interval=interval,
        range=range_,
    )
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f"Símbolo '{symbol}' não encontrado no Yahoo Finance.") from exc
        raise ValueError(f"Yahoo Finance respondeu HTTP {exc.code}.") from exc

    chart = payload.get("chart") or {}
    if chart.get("error"):
        description = chart["error"].get("description", "erro desconhecido")
        raise ValueError(f"Yahoo Finance: {description}")

    results = chart.get("result") or []
    if not results:
        raise ValueError(f"Nenhum dado retornado para '{symbol}'.")

    return results[0]


def fetch_yahoo_quote(symbol):
    result = _yahoo_chart(symbol, interval="1m", range_="1d")
    meta = result.get("meta") or {}

    price = meta.get("regularMarketPrice")
    if price is None:
        price = meta.get("fulldayPrice")

    if price is None:
        closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        valid = [value for value in closes if value is not None]
        if not valid:
            raise ValueError(f"Sem preço disponível para '{symbol}'.")
        price = valid[-1]

    currency_code = meta.get("currency") or ""
    return {
        "symbol": meta.get("symbol") or symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "price": float(price),
        "currency": CURRENCY_LABELS.get(currency_code, currency_code or "R$"),
        "currency_code": currency_code,
    }


def fetch_yahoo_history(symbol, interval="5m", range_="1d"):
    result = _yahoo_chart(symbol, interval=interval, range_=range_)
    timestamps = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

    from datetime import datetime

    points = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        captured_at = datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
        points.append({"price": float(close), "captured_at": captured_at})
    return points


class InvestingScraper:
    """Fallback opcional para páginas da Investing.com (pode ser bloqueado por 403)."""

    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self._lock = threading.Lock()

    def start(self):
        if self.driver is not None:
            return self
        from selenium import webdriver

        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1400,900")
        options.add_argument("--lang=pt-BR")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(45)
        return self

    def stop(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def fetch_price(self, url):
        from selenium.webdriver.support.ui import WebDriverWait

        with self._lock:
            if self.driver is None:
                self.start()
            try:
                self.driver.get(url)
                wait = WebDriverWait(self.driver, 20)
                element = wait.until(
                    lambda driver: driver.find_element(
                        "css selector", "[data-test='instrument-price-last']"
                    )
                    if driver.find_elements(
                        "css selector", "[data-test='instrument-price-last']"
                    )
                    else False
                )
                return parse_price(element.text)
            except Exception:
                self.stop()
                raise


class QuoteService:
    def __init__(self, headless=True):
        self.headless = headless
        self._investing = None

    def quote(self, asset):
        provider = (asset.get("provider") or "yahoo").lower()
        if provider == "investing":
            if self._investing is None:
                self._investing = InvestingScraper(headless=self.headless)
            price = self._investing.fetch_price(asset["url"])
            return {
                "symbol": asset["symbol"],
                "name": asset.get("name") or asset["symbol"],
                "price": price,
                "currency": asset.get("currency") or "R$",
            }
        return fetch_yahoo_quote(asset["symbol"])

    def history(self, asset):
        provider = (asset.get("provider") or "yahoo").lower()
        if provider == "yahoo":
            return fetch_yahoo_history(asset["symbol"])
        return []

    def stop(self):
        if self._investing is not None:
            self._investing.stop()
            self._investing = None
