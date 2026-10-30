"""Render STATUS.md and dashboard.html from one run summary.

The dashboard is a single self-contained HTML file (no external calls),
so it opens cleanly on a phone. It is regenerated on every bot run.
"""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _fmt_ts(ts):
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=ET).strftime("%m/%d %I:%M %p ET")


def _money(x):
    return f"${x:,.2f}"


def build_status_md(summary):
    cfg = summary["config"]
    daily = summary["daily"]
    L = []
    a = L.append
    a("# Altcoin Breakout Bot — Status")
    a("")
    a(f"Updated: {summary['updated_et']} · Mode: **PAPER ONLY** · "
      f"Exchange: Binance US (public data, no account needed)")
    if not summary["ok"]:
        a(f"> Last run error: {summary.get('error', 'unknown')}")
    a("")
    a("## Today")
    a(f"- Paper P&L (realized): {_money(daily['realized'])}")
    a(f"- New trades today: {daily['trades']} / {cfg['max_new_trades_per_day']} "
      f"· Daily loss cap: {_money(-cfg['daily_loss_cap_usd'])} "
      f"(new buys stop if realized hits it)")
    a(f"- Open positions: {len(summary['positions'])} / {cfg['max_open_positions']}")
    a(f"- Market guard: BTC 24h {summary['btc_change_24h']:+.2f}% "
      f"({'PAUSED new buys' if summary['btc_guard_on'] else 'ok'})")
    a("")
    a("## Open paper positions")
    if not summary["positions"]:
        a("- _none_")
    for p in summary["positions"]:
        unrl = (p["last_price"] / p["entry"] - 1) * 100 if p["entry"] else 0
        a(f"- **{p['symbol']}** — {_money(p['stake'])} @ {p['entry']:.6g}, "
          f"now {p['last_price']:.6g} ({unrl:+.2f}%), "
          f"TP {p['tp']:.6g} / SL {p['sl']:.6g}, opened {_fmt_ts(p['opened_ts'])}")
    a("")
    a("## Signals this run")
    if not summary["signals"]:
        a("- _none_")
    for s in summary["signals"]:
        a(f"- **{s['symbol']}** — close {s['close']:.6g} broke "
          f"resistance {s['resistance']:.6g} (+{s['breakout_pct']:.2f}%), "
          f"volume {s['volume_multiple']:.1f}x average"
          + (" — OPENED" if s.get("opened") else " — skipped: " + s.get("skip_reason", "")))
    a("")
    a("## Recent history")
    if not summary["history"]:
        a("- _no closed trades yet_")
    for h in reversed(summary["history"][-10:]):
        a(f"- {_fmt_ts(h['closed_ts'])}: {h['symbol']} — {h['reason']} "
          f"@ {h['exit']:.6g} → {_money(h['pnl'])}")
    a("")
    a("## Rules (starting defaults)")
    a(f"- Stake {_money(cfg['stake_usd'])} per trade · "
      f"TP +{cfg['take_profit_pct']:.0f}% · SL -{cfg['stop_loss_pct']:.0f}% · "
      f"max hold {cfg['max_hold_hours']}h")
    a(f"- Signal: 1h close above prior {cfg['lookback_candles']}h high, "
      f"volume >= {cfg['min_volume_multiple']}x average")
    a("- No live trading in this code. Paper only.")
    return "\n".join(L) + "\n"


def build_dashboard_html(summary):
    cfg = summary["config"]
    daily = summary["daily"]
    esc = html.escape

    def pos_rows():
        if not summary["positions"]:
            return '<tr><td colspan="6" class="muted">No open positions yet — the bot is scanning.</td></tr>'
        rows = []
        for p in summary["positions"]:
            unrl = (p["last_price"] / p["entry"] - 1) * 100 if p["entry"] else 0
            cls = "up" if unrl >= 0 else "down"
            rows.append(
                f"<tr><td><b>{esc(p['symbol'])}</b></td>"
                f"<td>{_money(p['stake'])} @ {p['entry']:.6g}</td>"
                f"<td>{p['last_price']:.6g}</td>"
                f"<td class='{cls}'>{unrl:+.2f}%</td>"
                f"<td>{p['tp']:.6g} / {p['sl']:.6g}</td>"
                f"<td>{_fmt_ts(p['opened_ts'])}</td></tr>")
        return "".join(rows)

    def signal_rows():
        if not summary["signals"]:
            return '<tr><td colspan="5" class="muted">No breakout signals this run.</td></tr>'
        rows = []
        for s in summary["signals"]:
            status = "OPENED" if s.get("opened") else esc(s.get("skip_reason", "skipped"))
            rows.append(
                f"<tr><td><b>{esc(s['symbol'])}</b></td>"
                f"<td>{s['close']:.6g}</td>"
                f"<td>{s['resistance']:.6g} (+{s['breakout_pct']:.2f}%)</td>"
                f"<td>{s['volume_multiple']:.1f}x</td>"
                f"<td>{status}</td></tr>")
        return "".join(rows)

    def hist_rows():
        if not summary["history"]:
            return '<tr><td colspan="5" class="muted">No closed trades yet.</td></tr>'
        rows = []
        for h in reversed(summary["history"][-15:]):
            cls = "up" if h["pnl"] >= 0 else "down"
            rows.append(
                f"<tr><td>{_fmt_ts(h['closed_ts'])}</td>"
                f"<td><b>{esc(h['symbol'])}</b></td>"
                f"<td>{esc(h['reason'])}</td>"
                f"<td>{h['exit']:.6g}</td>"
                f"<td class='{cls}'>{_money(h['pnl'])}</td></tr>")
        return "".join(rows)

    def scan_rows():
        if not summary["scan"]:
            return '<tr><td colspan="4" class="muted">Scanner had no data this run.</td></tr>'
        rows = []
        for s in summary["scan"][:20]:
            cls = "up" if s["change_24h"] >= 0 else "down"
            rows.append(
                f"<tr><td><b>{esc(s['symbol'])}</b></td>"
                f"<td>{s['price']:.6g}</td>"
                f"<td class='{cls}'>{s['change_24h']:+.2f}%</td>"
                f"<td>${s['quote_volume']:,.0f}</td></tr>")
        return "".join(rows)

    guard = "PAUSED — BTC down hard" if summary["btc_guard_on"] else "OK"
    pnl_cls = "up" if daily["realized"] >= 0 else "down"
    err = (f"<div class='warn'>Last run error: {esc(str(summary.get('error')))}</div>"
           if not summary["ok"] else "")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Altcoin Breakout Bot — Paper Dashboard</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#0f1115;color:#e8eaf0;margin:0;padding:16px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:24px 0 8px}}
.muted{{color:#9aa3b2}} .up{{color:#4ade80}} .down{{color:#f87171}}
.card{{background:#1a1e27;border:1px solid #2a2f3b;border-radius:12px;padding:14px;margin:10px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.big{{font-size:22px;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:7px 6px;border-bottom:1px solid #2a2f3b}}
.warn{{background:#3a2313;border:1px solid #b45309;border-radius:10px;padding:10px;margin:10px 0}}
</style></head><body>
<h1>Altcoin Breakout Bot</h1>
<p class="muted">PAPER ONLY · Binance US public data · Updated {esc(summary['updated_et'])} · No live orders, no API keys</p>
{err}
<div class="grid">
<div class="card"><div class="muted">Today realized P&amp;L</div><div class="big {pnl_cls}">{_money(daily['realized'])}</div></div>
<div class="card"><div class="muted">New trades today</div><div class="big">{daily['trades']} / {cfg['max_new_trades_per_day']}</div></div>
<div class="card"><div class="muted">Open positions</div><div class="big">{len(summary['positions'])} / {cfg['max_open_positions']}</div></div>
<div class="card"><div class="muted">BTC guard (24h)</div><div class="big">{summary['btc_change_24h']:+.2f}% · {guard}</div></div>
</div>
<div class="card"><b>Rules:</b> ${_money(cfg['stake_usd'])} per trade · TP +{cfg['take_profit_pct']:.0f}% · SL -{cfg['stop_loss_pct']:.0f}% · max hold {cfg['max_hold_hours']}h · daily loss cap {_money(-cfg['daily_loss_cap_usd'])} · 1h close above prior {cfg['lookback_candles']}h high on ≥{cfg['min_volume_multiple']}x volume · 6h cooldown after a stop-loss.</div>
<h2>Open positions</h2>
<table><tr><th>Coin</th><th>Entry</th><th>Now</th><th>Move</th><th>TP / SL</th><th>Opened</th></tr>{pos_rows()}</table>
<h2>Breakout signals this run</h2>
<table><tr><th>Coin</th><th>Close</th><th>Resistance</th><th>Volume</th><th>Result</th></tr>{signal_rows()}</table>
<h2>Top scanned coins (by 24h volume)</h2>
<table><tr><th>Coin</th><th>Price</th><th>24h</th><th>24h volume</th></tr>{scan_rows()}</table>
<h2>Trade history</h2>
<table><tr><th>Closed</th><th>Coin</th><th>Reason</th><th>Exit</th><th>P&amp;L</th></tr>{hist_rows()}</table>
<p class="muted">Paper trading is a test, not a promise of profit. Altcoins can fall fast and stay down. Do not trade rent money.</p>
</body></html>
"""
