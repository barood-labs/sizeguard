"""sizeguard CLI — answer before you click buy."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .calc import plan
from .fees import fees_for, resolve_venue
from .funding import fetch_funding


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def _pct(x: float, digits: int = 4) -> str:
    return f"{x:.{digits}f}%"


def _rate_bps(x: float) -> str:
    return f"{x * 10_000:.2f} bps/period"


def format_human(p) -> str:
    lines = []
    lines.append(f"sizeguard v{__version__} · {p.venue} · {p.side.upper()} · {p.leverage:g}x")
    lines.append("─" * 56)
    lines.append(f"Account risk     {_money(p.risk_usd)}  ({p.risk_pct:g}% of {_money(p.balance)})")
    lines.append(f"Entry / stop     {p.entry:g} → {p.stop:g}  ({p.stop_distance_pct:.3f}% away)")
    if p.target is not None:
        rr = p.reward_risk if p.reward_risk is not None else 0
        lines.append(f"Target           {p.target:g}  (R:R {rr:.2f}:1)")
    lines.append("")
    lines.append(f"Position size    {p.units:.6f} units")
    lines.append(f"Notional         {_money(p.notional)}")
    lines.append(f"Margin required  {_money(p.margin)}")
    lines.append("")
    safe = "OK — stop before liquidation" if p.stop_safe else "UNSAFE — liquidation hits before your stop"
    lines.append(f"Liquidation      {p.liquidation:.6g}  (mm {p.mm_rate * 100:.2f}%)")
    lines.append(f"Stop vs liq      {safe}")
    if p.stop_safe:
        lines.append(f"                cushion {p.stop_to_liq_pct:.3f}% of entry between stop and liq")
    lines.append("")
    lines.append(f"Fees (round-trip) {_money(p.fee_round_trip)}  ({p.fee_round_trip_pct_of_risk:.1f}% of risk budget)")
    lines.append(f"  entry {_money(p.fee_entry)} · exit {_money(p.fee_exit)}")
    if p.hold_days > 0:
        pay = "you pay" if p.funding_cost > 0 else ("you receive" if p.funding_cost < 0 else "flat")
        lines.append(
            f"Funding ({p.hold_days:g}d · {p.funding_periods:.2f}×{p.funding_interval_h:g}h)  "
            f"{_money(p.funding_cost)}  [{pay}]  rate {_rate_bps(p.funding_rate_per_period)}"
        )
    else:
        lines.append("Funding          (pass --hold-days N to estimate; optional --fetch-funding)")
    lines.append("")
    lines.append(f"Breakeven move   {p.breakeven_move_pct:.4f}% of entry to cover fees"
                 + (" + paid funding" if p.hold_days > 0 and p.funding_cost > 0 else ""))
    lines.append(f"Effective risk   {_money(p.effective_risk_with_costs)}  (stop loss + fees"
                 + (" + funding you pay" if p.funding_cost > 0 else "") + ")")
    lines.append("─" * 56)
    lines.append("Educational only. Not financial advice. Isolated-margin approx; verify on your venue.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sizeguard",
        description=(
            "Before you click buy: position size from risk%%, liquidation at leverage, "
            "round-trip fee drag, and funding cost if held N days. Offline by default; "
            "optional public funding-rate fetch (no API keys, no wallet, no orders)."
        ),
    )
    p.add_argument("--balance", type=float, required=True, help="Account equity in USD")
    p.add_argument("--risk", type=float, required=True, help="Risk percent of equity (e.g. 1 for 1%%)")
    p.add_argument("--entry", type=float, required=True, help="Entry price")
    p.add_argument("--stop", type=float, required=True, help="Stop-loss price")
    p.add_argument("--leverage", type=float, default=1.0, help="Leverage (default 1)")
    p.add_argument("--side", choices=["long", "short"], default="long")
    p.add_argument("--target", type=float, default=None, help="Optional take-profit for R:R")
    p.add_argument(
        "--venue",
        default="binance",
        help="Fee/MM preset: binance, bybit, hyperliquid (hl), okx, generic (default binance)",
    )
    p.add_argument("--maker", type=float, default=None, help="Override maker fee fraction (e.g. 0.0002)")
    p.add_argument("--taker", type=float, default=None, help="Override taker fee fraction")
    p.add_argument(
        "--fee-mode",
        choices=["taker", "maker", "mixed"],
        default="taker",
        help="taker=both taker (default), maker=both maker, mixed=taker in / maker out",
    )
    p.add_argument("--hold-days", type=float, default=0.0, help="Holding period for funding estimate")
    p.add_argument(
        "--funding-rate",
        type=float,
        default=None,
        help="Funding rate per period as fraction (e.g. 0.0001 = 0.01%%). Overrides fetch.",
    )
    p.add_argument(
        "--fetch-funding",
        action="store_true",
        help="Pull latest public funding rate for --symbol on --venue (read-only)",
    )
    p.add_argument("--symbol", default="BTCUSDT", help="Symbol for --fetch-funding (default BTCUSDT)")
    p.add_argument("--mm", type=float, default=None, help="Override maintenance-margin rate")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    p.add_argument("--version", action="version", version=f"sizeguard {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    venue = resolve_venue(args.venue)
    fee = fees_for(venue, maker=args.maker, taker=args.taker)
    mm = args.mm if args.mm is not None else fee["mm"]
    interval = fee["funding_interval_h"]
    rate = 0.0
    note = ""

    if args.funding_rate is not None:
        rate = args.funding_rate
        note = "manual --funding-rate"
    elif args.fetch_funding:
        if args.hold_days <= 0:
            print("warning: --fetch-funding without --hold-days N still fetches but funding cost is 0", file=sys.stderr)
        try:
            rate, interval, note = fetch_funding(venue, args.symbol)
            print(f"# funding {note}: {rate:.8f} per {interval:g}h", file=sys.stderr)
        except Exception as e:
            print(f"error: funding fetch failed ({e}). Pass --funding-rate or omit --fetch-funding.", file=sys.stderr)
            return 2
    elif args.hold_days > 0:
        print(
            "warning: --hold-days set but no funding rate; assuming 0. "
            "Pass --funding-rate or --fetch-funding.",
            file=sys.stderr,
        )

    try:
        result = plan(
            balance=args.balance,
            risk_pct=args.risk,
            entry=args.entry,
            stop=args.stop,
            leverage=args.leverage,
            side=args.side,
            venue=venue,
            maker=fee["maker"],
            taker=fee["taker"],
            mm_rate=mm,
            funding_interval_h=interval,
            funding_rate=rate,
            hold_days=args.hold_days,
            target=args.target,
            fee_mode=args.fee_mode,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.json:
        out = result.to_dict()
        out["funding_note"] = note
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(format_human(result))
        if not result.stop_safe:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
