# Altcoin Breakout Bot — Paper Only

Breakout / momentum paper bot for Binance US altcoins, built the same way
as the Polymarket underdog bot: a scheduled pass, paper positions with
TP/SL, and a dashboard you can check on your phone.

**Paper only. No live trading code exists in this repo. No API keys.**

## How it works

- **Data:** Binance US public API only (`api.binance.us`). No account, no key.
  Verified live: `GET /api/v3/ticker/price?symbol=BTCUSDT` returns a price.
- **Universe:** USDT altcoin pairs, 24h quote volume ≥ $250k, top 40 by volume.
  Binance US is thin vs. global Binance — on 2026-10-27 the top USDT altcoin
  (ETH) did only ~$1.2M in 24h, so a $2M floor left zero coins. BTC is
  excluded as a trade (it is only the market guard). Stablecoins, leveraged
  UP/DOWN tokens, and coins down >50% in 24h are excluded. A further
  24h crash guard skips new buys on coins down >20% in 24h.
- **Signal:** Last *closed* 1h candle closes above the highest high of the
  prior 20 closed 1h candles, on ≥ 1.5x their average volume.
  Pump guards: prior hourly quote volume must average ≥ $1,000, and
  volume multiple must be ≤ 20x — a 1,000x spike on a dead coin is a
  pump, not a breakout (first live scan, 2026-10-27, caught exactly that
  on ANTUSDT before the guard was added).
- **Market guard:** No new buys if BTC is down more than 5% in 24h.
- **Paper trade:** $10 stake, TP +10%, SL −5%, max hold 72h (time exit).
  Paper fees: 0.02% taker on entry and exit.
- **Caps (same spirit as the sports bot):** Max 5 open positions, max 5 new
  trades/day, daily realized loss cap −$2.50 (new buys stop for the day),
  6h cooldown after a stop-loss on the same coin. Caps are re-checked
  after *every* open, so a busy pass cannot overshoot.

## Run it

```bash
python tests/test_breakout.py   # logic tests, no network
python -m trader.run_once       # one 15-min pass
```

Each pass rewrites `STATUS.md`, `status.json`, `state.json`, and
`dashboard.html`. Open `dashboard.html` on your phone for the scanner,
open positions, daily P&L, and trade history.

## GitHub Actions (same pattern as underdog-trader)

Push this folder to a repo and `.github/workflows/trade.yml` runs it
every 15 minutes and commits the updated status/dashboard back.
Breakout needs 1h confirmation, so 15 minutes is the scan cadence —
not a 5-minute scalp.

## Going live — NOT approved, NOT built

Live trading would be a separate step, only if you explicitly approve it
later, and you would add any Binance US API key yourself in the repo.
Never send an API key or secret to Muse. Paper first: watch at least
2–4 weeks of paper P&L, win rate, and false breakouts before deciding
anything about live money. Paper results are not a promise of profit.
Altcoins can fall fast and stay down — do not trade rent money.
