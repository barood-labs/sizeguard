"""Pure offline math for position size, liquidation, fees, and funding."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Plan:
    side: str
    balance: float
    risk_pct: float
    risk_usd: float
    entry: float
    stop: float
    target: float | None
    leverage: float
    venue: str
    units: float
    notional: float
    margin: float
    stop_distance: float
    stop_distance_pct: float
    liquidation: float
    mm_rate: float
    stop_safe: bool
    stop_to_liq_pct: float
    reward_risk: float | None
    fee_entry: float
    fee_exit: float
    fee_round_trip: float
    fee_round_trip_pct_of_risk: float
    funding_rate_per_period: float
    funding_interval_h: float
    hold_days: float
    funding_periods: float
    funding_cost: float
    total_hold_cost: float  # fees RT + funding
    breakeven_move_pct: float  # move needed to cover RT fees (+ funding if hold>0)
    effective_risk_with_costs: float

    def to_dict(self) -> dict:
        return asdict(self)


def liquidation_price(
    entry: float,
    leverage: float,
    side: str,
    mm_rate: float = 0.005,
) -> float:
    """Isolated-margin approx used by many perp venues.

    long:  P_liq = entry * (1 - 1/L + mm)
    short: P_liq = entry * (1 + 1/L - mm)
    """
    if leverage <= 0:
        raise ValueError("leverage must be > 0")
    if entry <= 0:
        raise ValueError("entry must be > 0")
    inv = 1.0 / leverage
    side = side.lower()
    if side == "long":
        return entry * (1.0 - inv + mm_rate)
    if side == "short":
        return entry * (1.0 + inv - mm_rate)
    raise ValueError("side must be 'long' or 'short'")


def plan(
    *,
    balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: float = 1.0,
    side: str = "long",
    venue: str = "generic",
    maker: float = 0.0002,
    taker: float = 0.0005,
    mm_rate: float = 0.005,
    funding_interval_h: float = 8.0,
    funding_rate: float = 0.0,  # per period, e.g. 0.0001 = 0.01%
    hold_days: float = 0.0,
    target: float | None = None,
    fee_mode: str = "taker",  # taker|maker|mixed (entry taker, exit maker)
) -> Plan:
    if balance <= 0:
        raise ValueError("balance must be > 0")
    if risk_pct <= 0 or risk_pct > 100:
        raise ValueError("risk_pct must be in (0, 100]")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be > 0")
    if leverage < 1:
        raise ValueError("leverage must be >= 1")

    side_l = side.lower()
    if side_l not in ("long", "short"):
        raise ValueError("side must be long or short")

    # Side consistency: long stop below entry, short stop above.
    if side_l == "long" and stop >= entry:
        raise ValueError("long stop must be below entry")
    if side_l == "short" and stop <= entry:
        raise ValueError("short stop must be above entry")

    risk_usd = balance * (risk_pct / 100.0)
    stop_distance = abs(entry - stop)
    stop_distance_pct = stop_distance / entry
    units = risk_usd / stop_distance
    notional = units * entry
    margin = notional / leverage

    liq = liquidation_price(entry, leverage, side_l, mm_rate)

    if side_l == "long":
        # Safe if stop is above liquidation (hit stop before liq).
        stop_safe = stop > liq
        stop_to_liq_pct = (stop - liq) / entry * 100.0
    else:
        stop_safe = stop < liq
        stop_to_liq_pct = (liq - stop) / entry * 100.0

    rr: float | None = None
    if target is not None:
        if side_l == "long" and target <= entry:
            raise ValueError("long target must be above entry")
        if side_l == "short" and target >= entry:
            raise ValueError("short target must be below entry")
        rr = abs(target - entry) / stop_distance

    mode = fee_mode.lower()
    if mode == "taker":
        f_in, f_out = taker, taker
    elif mode == "maker":
        f_in, f_out = maker, maker
    elif mode == "mixed":
        f_in, f_out = taker, maker
    else:
        raise ValueError("fee_mode must be taker, maker, or mixed")

    fee_entry = notional * f_in
    fee_exit = notional * f_out
    fee_rt = fee_entry + fee_exit
    fee_rt_pct_risk = (fee_rt / risk_usd * 100.0) if risk_usd else 0.0

    periods = 0.0
    if hold_days > 0 and funding_interval_h > 0:
        periods = (hold_days * 24.0) / funding_interval_h
    # Sign: positive funding = longs pay shorts. Cost to YOU depends on side.
    # We report the cash drag assuming you PAY when rate>0 and long, or rate<0 and short.
    signed_rate = funding_rate
    if side_l == "short":
        signed_rate = -funding_rate
    funding_cost = notional * signed_rate * periods

    total_hold = fee_rt + max(0.0, funding_cost)  # "cost" view: fees always, funding if you pay
    # Breakeven move % of entry to cover fees (+ paid funding)
    breakeven = (fee_rt + max(0.0, funding_cost)) / notional * 100.0 if notional else 0.0
    effective_risk = risk_usd + fee_rt + max(0.0, funding_cost)

    return Plan(
        side=side_l,
        balance=balance,
        risk_pct=risk_pct,
        risk_usd=risk_usd,
        entry=entry,
        stop=stop,
        target=target,
        leverage=leverage,
        venue=venue,
        units=units,
        notional=notional,
        margin=margin,
        stop_distance=stop_distance,
        stop_distance_pct=stop_distance_pct * 100.0,
        liquidation=liq,
        mm_rate=mm_rate,
        stop_safe=stop_safe,
        stop_to_liq_pct=stop_to_liq_pct,
        reward_risk=rr,
        fee_entry=fee_entry,
        fee_exit=fee_exit,
        fee_round_trip=fee_rt,
        fee_round_trip_pct_of_risk=fee_rt_pct_risk,
        funding_rate_per_period=funding_rate,
        funding_interval_h=funding_interval_h,
        hold_days=hold_days,
        funding_periods=periods,
        funding_cost=funding_cost,
        total_hold_cost=total_hold,
        breakeven_move_pct=breakeven,
        effective_risk_with_costs=effective_risk,
    )
