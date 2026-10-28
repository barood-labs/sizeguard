"""Indicative maker/taker fee presets (standard retail tiers). Override with --maker/--taker."""

from __future__ import annotations

# Rates as fractions (0.0004 = 4 bps = 0.04%).
VENUES: dict[str, dict[str, float]] = {
    "binance": {"maker": 0.0002, "taker": 0.0004, "mm": 0.004, "funding_interval_h": 8.0},
    "bybit": {"maker": 0.0002, "taker": 0.00055, "mm": 0.005, "funding_interval_h": 8.0},
    "hyperliquid": {"maker": 0.00015, "taker": 0.00045, "mm": 0.005, "funding_interval_h": 1.0},
    "okx": {"maker": 0.0002, "taker": 0.0005, "mm": 0.005, "funding_interval_h": 8.0},
    "generic": {"maker": 0.0002, "taker": 0.0005, "mm": 0.005, "funding_interval_h": 8.0},
}

ALIASES = {
    "bn": "binance",
    "binance-futures": "binance",
    "hl": "hyperliquid",
    "hyper": "hyperliquid",
}


def resolve_venue(name: str) -> str:
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key not in VENUES:
        known = ", ".join(sorted(VENUES))
        raise SystemExit(f"Unknown venue {name!r}. Choose one of: {known}")
    return key


def fees_for(venue: str, maker: float | None = None, taker: float | None = None) -> dict[str, float]:
    v = resolve_venue(venue)
    base = dict(VENUES[v])
    if maker is not None:
        base["maker"] = maker
    if taker is not None:
        base["taker"] = taker
    return base
