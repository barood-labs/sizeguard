"""Optional read-only public funding-rate fetch. Offline fallback always works."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

UA = "sizeguard/0.1 (+https://github.com/barood-labs/sizeguard; read-only)"


def _get_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_symbol(symbol: str, venue: str) -> str:
    s = symbol.strip().upper().replace("-", "").replace("/", "").replace("_", "")
    if venue == "okx":
        # BTCUSDT -> BTC-USDT
        for q in ("USDT", "USDC", "USD"):
            if s.endswith(q) and len(s) > len(q):
                return f"{s[: -len(q)]}-{q}"
        return s
    if venue == "hyperliquid":
        # HL uses coin name without quote, e.g. BTC
        for q in ("USDT", "USDC", "USD"):
            if s.endswith(q) and len(s) > len(q):
                return s[: -len(q)]
        return s
    return s


def fetch_funding(venue: str, symbol: str) -> tuple[float, float, str]:
    """Return (rate_per_period, interval_hours, note). Raises on hard failure."""
    v = venue.lower()
    sym = normalize_symbol(symbol, v)

    if v == "binance":
        data = _get_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}")
        rate = float(data["lastFundingRate"])
        return rate, 8.0, f"binance premiumIndex {sym}"

    if v == "bybit":
        data = _get_json(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={sym}")
        rows = data.get("result", {}).get("list") or []
        if not rows:
            raise RuntimeError(f"bybit: no ticker for {sym}")
        rate = float(rows[0].get("fundingRate") or 0.0)
        # Interval from instruments-info when available; default 8h.
        interval = 8.0
        try:
            info = _get_json(
                f"https://api.bybit.com/v5/market/instruments-info?category=linear&symbol={sym}"
            )
            lst = info.get("result", {}).get("list") or []
            if lst and lst[0].get("fundingInterval"):
                # fundingInterval is minutes on Bybit
                interval = float(lst[0]["fundingInterval"]) / 60.0
        except Exception:
            pass
        return rate, interval, f"bybit linear {sym}"

    if v == "okx":
        inst = normalize_symbol(symbol, "okx")
        if not inst.endswith("-SWAP"):
            # perpetual swap id
            if "-" in inst:
                inst = f"{inst}-SWAP"
            else:
                inst = f"{inst}-USDT-SWAP" if "USDT" not in inst else f"{inst}-SWAP"
        # Prefer public funding-rate endpoint
        data = _get_json(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}")
        rows = data.get("data") or []
        if not rows:
            raise RuntimeError(f"okx: no funding for {inst}")
        rate = float(rows[0].get("fundingRate") or 0.0)
        return rate, 8.0, f"okx {inst}"

    if v == "hyperliquid":
        coin = normalize_symbol(symbol, "hyperliquid")
        body = json.dumps({"type": "metaAndAssetCtxs"}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.hyperliquid.xyz/info",
            data=body,
            headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        meta, ctxs = payload[0], payload[1]
        universe = meta.get("universe") or []
        idx = next((i for i, u in enumerate(universe) if u.get("name") == coin), None)
        if idx is None:
            raise RuntimeError(f"hyperliquid: coin {coin} not found")
        ctx = ctxs[idx]
        rate = float(ctx.get("funding") or 0.0)
        return rate, 1.0, f"hyperliquid {coin}"

    raise RuntimeError(f"no public funding fetch for venue {venue!r}")
