import json
import os
import queue
import threading
import time

from flask import Flask, Response, jsonify, render_template, request

import db
import scraper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
DISABLE_MONITOR = os.environ.get("DISABLE_MONITOR", "0") == "1"

app = Flask(__name__)
quotes = scraper.QuoteService(headless=HEADLESS)

_subscribers = set()
_subscribers_lock = threading.Lock()


def broadcast(event):
    payload = f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
    with _subscribers_lock:
        for subscriber in list(_subscribers):
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                pass


class Monitor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self._status_lock = threading.Lock()
        self._status = {
            "running": False,
            "poll_interval": POLL_INTERVAL,
            "last_cycle": None,
            "last_success": None,
            "last_error": None,
            "cycles": 0,
        }

    def status(self):
        with self._status_lock:
            return dict(self._status)

    def _set_status(self, **values):
        with self._status_lock:
            self._status.update(values)

    def check_alerts(self, asset, price, previous):
        if previous is None:
            return

        previous_value = previous["price"]
        currency = asset["currency"] or "R$"
        above = asset["alert_above"]
        below = asset["alert_below"]

        if above is not None and price >= above > previous_value:
            message = (
                f"{asset['symbol']} subiu para {currency} {price:.2f} "
                f"(acima de {currency} {above:.2f})"
            )
            alert = db.add_alert(asset["id"], asset["symbol"], "above", message, price)
            broadcast({"type": "alert", **alert})

        if below is not None and price <= below < previous_value:
            message = (
                f"{asset['symbol']} caiu para {currency} {price:.2f} "
                f"(abaixo de {currency} {below:.2f})"
            )
            alert = db.add_alert(asset["id"], asset["symbol"], "below", message, price)
            broadcast({"type": "alert", **alert})

    def run_cycle(self):
        assets = db.list_assets()
        self._set_status(last_cycle=db.now_iso())

        for asset in assets:
            if self.stop_event.is_set():
                return
            try:
                quote = quotes.quote(asset)
                price = quote["price"]
                previous = db.latest_price(asset["id"])
                captured_at = db.now_iso()
                db.add_price(asset["id"], price, captured_at)

                change = None
                change_pct = None
                if previous and previous["price"]:
                    change = round(price - previous["price"], 4)
                    change_pct = round((change / previous["price"]) * 100, 4)

                broadcast(
                    {
                        "type": "price",
                        "asset_id": asset["id"],
                        "symbol": asset["symbol"],
                        "name": asset["name"],
                        "currency": asset["currency"],
                        "price": price,
                        "previous_price": previous["price"] if previous else None,
                        "change": change,
                        "change_pct": change_pct,
                        "captured_at": captured_at,
                    }
                )
                self.check_alerts(asset, price, previous)
                self._set_status(last_success=captured_at, last_error=None)
            except Exception as exc:
                message = f"Falha ao capturar {asset['symbol']}: {exc}"
                self._set_status(last_error=message)
                broadcast(
                    {
                        "type": "error",
                        "asset_id": asset["id"],
                        "symbol": asset["symbol"],
                        "message": message,
                        "at": db.now_iso(),
                    }
                )

        with self._status_lock:
            self._status["cycles"] += 1

    def run(self):
        self._set_status(running=True)

        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.run_cycle()
            except Exception as exc:
                self._set_status(last_error=f"Erro no ciclo: {exc}")
                broadcast(
                    {"type": "error", "message": f"Erro no ciclo: {exc}", "at": db.now_iso()}
                )

            elapsed = time.monotonic() - started
            wait_for = max(5, POLL_INTERVAL - elapsed)
            self.wake_event.wait(timeout=wait_for)
            self.wake_event.clear()

        quotes.stop()
        self._set_status(running=False)


monitor = Monitor()


def parse_optional_float(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "."))


def validate_asset_payload(payload, partial=False):
    errors = []
    data = {}

    if not partial or "symbol" in payload:
        symbol = (payload.get("symbol") or "").strip().upper()
        if not symbol:
            errors.append("Informe o código do ativo (ex.: AAPL34.SA).")
        data["symbol"] = symbol

    if not partial or "name" in payload:
        data["name"] = (payload.get("name") or "").strip()

    if "url" in payload:
        url = (payload.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url
        data["url"] = url

    if "currency" in payload:
        data["currency"] = (payload.get("currency") or "").strip()

    if "provider" in payload:
        data["provider"] = (payload.get("provider") or "yahoo").strip().lower()

    for field, label in (("alert_above", "alerta de alta"), ("alert_below", "alerta de baixa")):
        if field in payload:
            raw = payload.get(field)
            try:
                data[field] = parse_optional_float(raw)
            except (TypeError, ValueError):
                errors.append(f"Valor inválido para {label}.")

    return data, errors


@app.get("/")
def index():
    return render_template("index.html", poll_interval=POLL_INTERVAL)


@app.get("/api/assets")
def api_assets():
    return jsonify(db.assets_summary())


@app.post("/api/assets")
def api_add_asset():
    payload = request.get_json(silent=True) or {}
    data, errors = validate_asset_payload(payload)
    if errors:
        return jsonify({"errors": errors}), 400

    if db.get_asset_by_symbol(data["symbol"]):
        return jsonify({"errors": ["Já existe um ativo com esse código."]}), 409

    provider = data.get("provider", "yahoo")
    lookup = {
        "symbol": data["symbol"],
        "provider": provider,
        "url": data.get("url", ""),
        "name": data.get("name", ""),
        "currency": data.get("currency", ""),
    }
    try:
        quote = quotes.quote(lookup)
    except Exception as exc:
        return jsonify({"errors": [str(exc)]}), 422

    symbol = (quote.get("symbol") or data["symbol"]).strip().upper()
    asset = db.add_asset(
        symbol=symbol,
        name=data.get("name") or quote.get("name") or symbol,
        url=data.get("url") or f"https://finance.yahoo.com/quote/{symbol}",
        currency=quote.get("currency") or data.get("currency") or "R$",
        provider=provider,
        alert_above=data.get("alert_above"),
        alert_below=data.get("alert_below"),
    )

    try:
        for point in quotes.history(asset)[-200:]:
            db.add_price(asset["id"], point["price"], point["captured_at"])
    except Exception:
        pass

    latest = db.latest_price(asset["id"])
    if not latest or latest["price"] != quote["price"]:
        db.add_price(asset["id"], quote["price"], db.now_iso())

    latest = db.latest_price(asset["id"])
    previous = db.previous_price(asset["id"])
    change = round(latest["price"] - previous["price"], 4) if previous else None
    change_pct = (
        round((change / previous["price"]) * 100, 4)
        if change is not None and previous["price"]
        else None
    )
    broadcast(
        {
            "type": "price",
            "asset_id": asset["id"],
            "symbol": asset["symbol"],
            "name": asset["name"],
            "currency": asset["currency"],
            "price": latest["price"],
            "previous_price": previous["price"] if previous else None,
            "change": change,
            "change_pct": change_pct,
            "captured_at": latest["captured_at"],
        }
    )

    return jsonify(db.get_asset(asset["id"])), 201


@app.patch("/api/assets/<int:asset_id>")
def api_update_asset(asset_id):
    asset = db.get_asset(asset_id)
    if not asset:
        return jsonify({"errors": ["Ativo não encontrado."]}), 404

    payload = request.get_json(silent=True) or {}
    data, errors = validate_asset_payload(payload, partial=True)
    if errors:
        return jsonify({"errors": errors}), 400

    updates = {}
    if data.get("name"):
        updates["name"] = data["name"]
    for field in ("alert_above", "alert_below"):
        if field in data:
            updates[field] = data[field]

    updated = db.update_asset(asset_id, **updates)
    return jsonify(updated)


@app.delete("/api/assets/<int:asset_id>")
def api_delete_asset(asset_id):
    if not db.get_asset(asset_id):
        return jsonify({"errors": ["Ativo não encontrado."]}), 404
    db.delete_asset(asset_id)
    return jsonify({"ok": True})


@app.get("/api/assets/<int:asset_id>/history")
def api_history(asset_id):
    if not db.get_asset(asset_id):
        return jsonify({"errors": ["Ativo não encontrado."]}), 404
    minutes = request.args.get("minutes", type=int) or None
    limit = request.args.get("limit", default=2000, type=int)
    return jsonify(db.history(asset_id, minutes=minutes, limit=limit))


@app.get("/api/alerts")
def api_alerts():
    limit = request.args.get("limit", default=100, type=int)
    return jsonify(db.recent_alerts(limit=limit))


@app.get("/api/status")
def api_status():
    return jsonify(monitor.status())


@app.post("/api/refresh")
def api_refresh():
    monitor.wake_event.set()
    return jsonify({"ok": True})


@app.get("/api/stream")
def api_stream():
    subscriber = queue.Queue(maxsize=200)
    with _subscribers_lock:
        _subscribers.add(subscriber)

    def generate():
        try:
            yield f"data: {json.dumps({'type': 'hello', 'status': monitor.status()})}\n\n"
            while True:
                try:
                    payload = subscriber.get(timeout=20)
                    yield payload
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _subscribers_lock:
                _subscribers.discard(subscriber)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def backfill_missing_history():
    for asset in db.list_assets():
        if db.latest_price(asset["id"]):
            continue
        try:
            for point in quotes.history(asset)[-200:]:
                db.add_price(asset["id"], point["price"], point["captured_at"])
            if not db.latest_price(asset["id"]):
                quote = quotes.quote(asset)
                db.add_price(asset["id"], quote["price"], db.now_iso())
        except Exception as exc:
            print(f"Aviso: não foi possível carregar histórico de {asset['symbol']}: {exc}")


def create_app():
    db.init_db()
    backfill_missing_history()
    if not DISABLE_MONITOR and not monitor.is_alive():
        monitor.start()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), threaded=True)
