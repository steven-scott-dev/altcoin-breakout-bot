"""Breakout paper-trading core — pure logic, no live orders anywhere.

Rules (locked starting defaults, tunable in config.json):
- Universe: Binance US USDT pairs, altcoins only (BTC excluded as a trade,
  used only as a market guard), 24h quote volume >= $250k, top 40 by volume.
  Binance US is much thinner than global Binance — on 2026-10-27 the top
  USDT altcoin (ETH) did only ~$1.2M in 24h, so a $2M floor left zero coins.
  Stablecoins and leveraged UP/DOWN tokens are excluded, as are coins
  down more than 50% in 24h (likely dead/stale listings).
- Signal (1h candles, closed candles only): the last closed 1h candle
  closes above the highest high of the previous 20 closed 1h candles,
  on >= 1.5x the average volume of those 20 candles.
- Market guard: no new buys if BTC is down more than 5% in 24h.
- Paper stake $10, TP +10%, SL -5% (2:1 reward/risk), max hold 72h.
- Caps: max 5 open positions, max 5 new trades/day, daily realized
  loss cap -$2.50 (new buys stop for the day once hit).
- Cooldown: 6h after a stop-loss on the same coin before re-entering.
- Fees (paper, for realism): 0.02% taker on entry and on exit.
- PAPER ONLY. There is no order-placement code in this repo, by design.
  Going live would be a separate, explicitly approved step with API keys
  the owner adds himself — never sent to Muse.
"""
import json
import urllib.request

STABLE_BASES = {
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "USD1", "BUSD",
    "UST", "USTC",  # Terra stablecoins, no longer stable — excluded anyway
}
EXCLUDED_BASES = {"BTC"}  # BTC is the guard, not a tradeable altcoin here.


def fetch_json(base_url, path, timeout=15):
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"User-Agent": "altcoin-breakout-paper-bot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_tradeable_altcoin(symbol):
    """USDT pair, not a stablecoin, not BTC, not a leveraged token."""
    if not symbol.endswith("USDT"):
        return False
    base = symbol[:-4]
    if base in STABLE_BASES or base in EXCLUDED_BASES:
        return False
    if base.endswith("UP") or base.endswith("DOWN"):
        return False
    # Leveraged tokens are usually 3-4 letter base + UP/DOWN; the check
    # above covers the common case. BULL/BEAR tokens are also skipped.
    if base.endswith("BULL") or base.endswith("BEAR"):
        return False
    return True


def select_universe(tickers, config):
    """tickers: Binance US /ticker/24hr list. Returns top symbols by volume."""
    min_vol = config["min_24h_quote_volume_usd"]
    rows = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not is_tradeable_altcoin(sym):
            continue
        try:
            vol = float(t.get("quoteVolume", 0))
            price = float(t.get("lastPrice", 0))
            change = float(t.get("priceChangePercent", 0))
        except (TypeError, ValueError):
            continue
        if vol < min_vol or price <= 0:
            continue
        if change <= -50:
            continue
        rows.append({"symbol": sym, "price": price,
                     "change_24h": change, "quote_volume": vol})
    rows.sort(key=lambda r: r["quote_volume"], reverse=True)
    return rows[: config["universe_limit"]]


def parse_klines(raw):
    """Binance kline rows -> dicts with float OHLCV."""
    out = []
    for r in raw:
        try:
            out.append({
                "open_time": int(r[0]),
                "open": float(r[1]), "high": float(r[2]),
                "low": float(r[3]), "close": float(r[4]),
                "volume": float(r[5]), "close_time": int(r[6]),
            })
        except (IndexError, TypeError, ValueError):
            continue
    return out


def closed_candles(candles):
    """Drop the last (still-forming) candle; a breakout needs a closed candle."""
    if len(candles) < 2:
        return candles
    return candles[:-1]


def detect_breakout(candles, lookback=20, min_volume_multiple=1.5,
                    max_volume_multiple=20, min_avg_quote_volume=1000):
    """Return signal details if the last closed candle breaks out, else None.

    candles must already be closed candles, oldest -> newest.
    Resistance = max high of the `lookback` candles before the last one.
    Pump guards (added after the first live scan, 2026-10-27):
    - prior hourly quote volume must average >= $1,000, so a coin that
      was dead for 20 hours cannot qualify on one tiny-volume spike;
    - volume multiple must be <= 20x, so a 1,000x spike is treated as
      a pump, not a healthy breakout.
    """
    if len(candles) < lookback + 1:
        return None
    breakout = candles[-1]
    prior = candles[-(lookback + 1):-1]
    resistance = max(c["high"] for c in prior)
    avg_vol = sum(c["volume"] for c in prior) / len(prior)
    if avg_vol <= 0:
        return None
    avg_quote = sum(c["close"] * c["volume"] for c in prior) / len(prior)
    if avg_quote < min_avg_quote_volume:
        return None
    vol_mult = breakout["volume"] / avg_vol
    if breakout["close"] <= resistance:
        return None
    if vol_mult < min_volume_multiple or vol_mult > max_volume_multiple:
        return None
    return {
        "close": breakout["close"],
        "resistance": resistance,
        "breakout_pct": (breakout["close"] / resistance - 1) * 100,
        "volume_multiple": vol_mult,
        "avg_volume": avg_vol,
        "breakout_volume": breakout["volume"],
        "avg_quote_volume": avg_quote,
    }


def calc_pnl(entry, exit_price, stake, fee_pct):
    """Net paper P&L in USD, fees on both sides."""
    if entry <= 0 or stake <= 0:
        return 0.0
    qty = stake / entry
    proceeds = qty * exit_price
    fees = stake * fee_pct / 100.0 + proceeds * fee_pct / 100.0
    return proceeds - stake - fees


def check_exit(position, price, now_ts, config):
    """Return (reason, exit_price) if this position should close, else (None, None)."""
    if price >= position["tp"]:
        return "take-profit", position["tp"]
    if price <= position["sl"]:
        return "stop-loss", position["sl"]
    age_h = (now_ts - position["opened_ts"]) / 3600.0
    if age_h >= config["max_hold_hours"]:
        return "time-exit-72h", price
    return None, None
