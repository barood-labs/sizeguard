# sizeguard

**Before you click buy — size, liquidation, fees, and funding in one command.**

Crypto perps wipe accounts when position size, leverage, and funding don't fit the stop.
`sizeguard` is a free, local, zero-dependency CLI that answers four questions every trader
should ask *before* the order:

1. **Position size** from account risk % and stop distance  
2. **Liquidation price** at your leverage (isolated-margin approx)  
3. **Funding cost** if you hold N days (manual rate or public API snapshot)  
4. **Round-trip fee drag** with Binance / Bybit / Hyperliquid / OKX presets  

No wallet connect. No API keys required. No order placement. Offline math always works.

```bash
python -m sizeguard \
  --balance 10000 --risk 1 \
  --entry 95000 --stop 93000 \
  --leverage 10 --side long \
  --venue binance --hold-days 3 \
  --funding-rate 0.0001
```

## Install

Python 3.10+. No third-party packages.

```bash
git clone https://github.com/barood-labs/sizeguard.git
cd sizeguard
python -m pip install -e .
# or just:
python -m sizeguard --help
```

## One-liner demo

```bash
python -m sizeguard \
  --balance 10000 --risk 1 \
  --entry 100 --stop 98 \
  --leverage 5 --side long \
  --venue binance --fee-mode taker \
  --hold-days 2 --funding-rate 0.0001 \
  --target 106
```

Example output (numbers rounded):

```
sizeguard v0.1.0 · binance · LONG · 5x
────────────────────────────────────────────────────────
Account risk     $100.00  (1% of $10,000.00)
Entry / stop     100 → 98  (2.000% away)
Target           106  (R:R 3.00:1)

Position size    50.000000 units
Notional         $5,000.00
Margin required  $1,000.00

Liquidation      80.5  (mm 0.40%)
Stop vs liq      OK — stop before liquidation

Fees (round-trip) $4.00  (4.0% of risk budget)
Funding (2d · 6×8h)  $3.00  [you pay]
Breakeven move   0.1400% of entry to cover fees + paid funding
Effective risk   $107.00
```

Exit code `3` means your stop sits beyond liquidation (you'll get liquidated first).

## Optional live funding (read-only)

Public endpoints only. Some IPs/regions are blocked by venues — if fetch fails, pass `--funding-rate` instead.

```bash
python -m sizeguard \
  --balance 10000 --risk 1 \
  --entry 95000 --stop 93000 \
  --leverage 8 --side long \
  --venue binance --symbol BTCUSDT \
  --hold-days 3 --fetch-funding
```

Supported fetch venues: `binance`, `bybit`, `okx`, `hyperliquid` (`hl`).

## Flags

| Flag | Meaning |
|------|---------|
| `--balance` | Equity in USD |
| `--risk` | Percent of equity to risk if stop hits |
| `--entry` / `--stop` / `--target` | Prices |
| `--leverage` | e.g. `10` |
| `--side` | `long` or `short` |
| `--venue` | `binance`, `bybit`, `hyperliquid`, `okx`, `generic` |
| `--fee-mode` | `taker` (default), `maker`, or `mixed` (taker in / maker out) |
| `--maker` / `--taker` | Override fee fractions |
| `--hold-days` | Holding window for funding |
| `--funding-rate` | Per-period rate as fraction (`0.0001` = 0.01%) |
| `--fetch-funding` | Pull latest public rate for `--symbol` |
| `--json` | Machine-readable output |

## What it is / isn't

**Is:** a pre-trade risk checklist you can run offline or in CI.  
**Isn't:** a trading bot, signal service, wallet, or tax reporter. Liquidation uses a standard isolated-margin approximation; always confirm on your exchange.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

MIT © barood-labs
