# arb-engine

A cross-venue sports arbitrage scanner. It pulls sportsbook prices (via The Odds API) and
exchange order books (Kalshi, Polymarket), matches the same game across venues, and finds
arbs that hold up after fees, at the size actually available.

What it does that a typical odds screen doesn't:

- **Fees included.** Kalshi's taker fee (`ceil(0.07 × C × P × (1−P))`) is applied to every
  Kalshi leg. Many "arbs" on odds screens disappear once you do this.
- **Depth-aware sizing.** It walks each exchange's order book, can split one side across
  several venues, and picks the stake that maximizes guaranteed profit within your bankroll.
- **Two ways to back a team on Kalshi.** YES on that team's market, or NO on the
  opponent's. It takes whichever is cheaper.
- **Settlement-rule checks.** Tennis arbs are flagged (or skipped) when venues settle
  retirements differently. Soccer moneylines require all three outcomes (home, draw, away).
- **A history of everything seen.** Every opportunity is logged to SQLite with how long
  it lasted, so `arb report` tells you what this is actually worth per day.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp config.example.toml config.toml   # then edit allowed venues for your state
export ODDS_API_KEY=...              # https://the-odds-api.com
# optional Telegram alerts:
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
```

## Usage

```bash
arb scan                     # scan every 30s, print/alert new arbs, log to arb.db
arb scan --once              # one pass
arb scan --record quotes.jsonl   # also save raw quotes for later backtesting
arb report --hours 24        # how many arbs, how big, how long they lasted

# Manual check of something you saw on an odds screen (fees from config.toml):
arb calc +134@draftkings -132@kalshi --config config.toml
arb calc +100 +104@novig --stake 500
```

## Status

| Piece | State |
|---|---|
| Odds math, fee models, arb engine, depth walking, stake sizing | Done, unit-tested |
| Cross-venue event matching (aliases, mascots, home/away flips) | Done, unit-tested |
| The Odds API / Kalshi / Polymarket parsers | Tested against payloads shaped like the documented responses. **Not yet run against the live APIs.** |
| SQLite log + report, Telegram alerts, replay | Done |

Before trusting live output, check:

1. **Kalshi series tickers** in `config.toml` (`GET /series`). Kalshi renames these.
2. **Fee settings** for each venue you enable.
3. **Tennis retirement rules** for each venue (`[rules.tennis_retirement]`).
4. **Polymarket US vs international.** The adapter targets the international Gamma and
   CLOB APIs. US residents use Polymarket US, which has a separate API.
5. **Kalshi spreads and totals** aren't parsed yet, only game winners.

## Roadmap

1. **Scanner (this).** Run it for a week and use `arb report` to see whether net-of-fee
   volume justifies the rest.
2. **Alerts with exact stakes** to Telegram for legs you place by hand.
3. **Automated execution on exchanges** (Kalshi and Polymarket have trading APIs), with
   risk limits and a kill switch. Sportsbook legs stay manual, since books ban bots.
4. **Maker engine.** Rest limit orders on exchanges priced so a fill is already an arb
   against a sportsbook price, then hedge immediately. This avoids taker fees.

## Tests

```bash
pytest -q
```
