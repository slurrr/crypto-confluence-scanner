# Crypto Confluence Score Scanner – Project Spec (Canonical)

> **Repo:** `crypto-confluence-scanner`  
> **This file:** `PROJECT_SPEC.md` (source of truth for architecture + naming)

This spec is meant to keep *you* and any future AI helpers aligned on:

- What exists **right now** in the repo (file names, config keys, entrypoints).
- What the system is **intended** to do (based on the Architecture Plan + Confluence Score model).
- How to extend it without inventing new structures or names.

If anything in this spec conflicts with the actual code/config in the repo, **the repo wins** and this file should be updated.

---

## 1. Current Project Layout

Project root (from your machine):

```text
project_root/
├── .git/
├── .venv/
├── .vscode/
├── reports/
├── scripts/
├── src/
├── tests/
├── .gitignore
├── alerts_state.json
├── config.yaml
├── gitcheat.md
├── PROJECT_SPEC.md
├── README.md
└── requirements.txt
```

Notes:

- `reports/` – output directory for generated markdown reports.
- `scripts/` – for helper/runner scripts (currently light/empty, but reserved).
- `tests/` – test suite root (some files may exist, but tests are still being built out).
- `alerts_state.json` – persistent alert state (dedupe, last-sent info, etc.).
- `config.yaml` – main runtime config (see §2).

---

## 2. Current `src/` Layout (Actual Files)

From `src_tree_vscode.txt`:

```text
src/
│   debug_alerts.py
│   debug_daily_report.py
│   debug_features.py
│   debug_ranking.py
│   debug_scores.py
│   main.py
│   scratch.py
│   __init__.py
│
├── alerts
│   │   engine.py
│   │   notifiers.py
│   │   state.py
│   │   types.py
│   │   __pycache__/...
│
├── backtest
│   │   backtest_engine.py
│
├── data
│   │   exchange_api.py
│   │   models.py
│   │   repository.py
│   │   __init__.py
│   │   __pycache__/...   # includes market_health.cpython-310.pyc ⇒ market_health.py exists
│
├── features
│   │   positioning.py
│   │   relative_strength.py
│   │   trend.py
│   │   volatility.py
│   │   volume.py
│   │   __pycache__/...
│
├── patterns
│   │   breakout.py
│   │   pullback.py
│   │   rsi_divergence.py
│   │   volatility_squeeze.py
│   │   __pycache__/...
│
├── ranking
│   │   filters.py
│   │   ranking.py
│   │   __pycache__/...
│
├── reports
│   │   daily_report.py
│   │   __pycache__/...
│
├── scoring
│   │   confluence.py
│   │   positioning_score.py
│   │   regimes.py
│   │   rs_score.py
│   │   trend_score.py
│   │   volatility_score.py
│   │   volume_score.py
│   │   __pycache__/...
│
└── __pycache__/...
```

### 2.1 Production vs Debug Files

Treat these as **production / architectural** modules:

- `src/main.py`
- `src/data/*`
- `src/features/*`
- `src/scoring/*`
- `src/patterns/*`
- `src/ranking/*`
- `src/reports/*`
- `src/alerts/*`
- `src/backtest/*`

Treat these as **debug/scratch helpers** (not to be used as architectural references in new work):

- `src/debug_alerts.py`
- `src/debug_daily_report.py`
- `src/debug_features.py`
- `src/debug_ranking.py`
- `src/debug_scores.py`
- `src/scratch.py`

When asking for help in future chats, always refer to the production modules above, not the debug ones.

---

## 3. Current Configuration (`config.yaml` – Actual Keys)

From `config.yaml.txt`:

```yaml
timeframes:
  - 1d

exchange:
  id: binance
  symbols:
    - BTC/USDT
    - ETH/USDT
    - ZEC/USDT
    - LTC/USDT

  derivatives:
    id: binanceusdm     # CCXT id for Binance USDT-M futures

ranking:
  max_symbols: 20   # cap how many symbols you scan per run

#filters:
#  min_trend_score: 25
#  min_rs_score: 20
#  min_volume_score: 30
#  min_volatility_score: 0
#  max_atr_pct: 25
#  max_bb_width_pct: 60

  reports:
  top_n: 20
  output_dir: reports

alerts:
  enabled: true

  # Global thresholds (mainly used for HIGH_CONFLUENCE)
  min_confluence_score: 60
  min_trend_score: 55
  min_volume_score: 50
  min_positioning_score: 50
  require_uptrend_regime: false

  # State / dedupe
  state_file: "alerts_state.json"
  min_cs_delta: 3.0
  cooldown_minutes: 60

  # Which alert types are active
  types:
    high_confluence: true
    volume_spike: true
    squeeze_candidate: true
    regime_change: true
    rsi_divergence: true

  # Per-type extra thresholds
  volume_spike_min_volume_score: 75
  squeeze_max_vol_score: 40
  squeeze_max_bbw_pct: 6
  rsi_divergence_timeframes:
    - "4h"
    - "1h"
    - "15m"
  rsi_divergence_lookback: 300
  rsi_divergence_pivot_lookback: 2
  rsi_divergence_min_strength: 1
  rsi_divergence_max_bars_from_last: 10

  # Turn detailed divergence logging on/off
  rsi_divergence_debug: true

  # Timezone for divergence debugging logs
  rsi_divergence_timezone: "America/Denver"

  telegram:
    enabled: false
    bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"

  discord:
    enabled: false
    webhook_url: "https://discord.com/api/webhooks/XXX/YYY"
```

### 3.1 Conceptual Structure

Logically, the config is interpreted as:

- `timeframes` – list of candle timeframes to scan (currently just `"1d"`).
- `exchange` – exchange + symbol universe:
  - `id` – CCXT exchange id (here `"binance"`).
  - `symbols` – explicit list of spot symbols.
  - `derivatives.id` – CCXT id for futures/perps (here `"binanceusdm"`).
- `ranking.max_symbols` – maximum number of symbols to include per scan.
- `reports.top_n` – how many ranked results to show in reports.
- `reports.output_dir` – where to save markdown reports (matches `reports/` directory).
- `alerts` – global alert configuration and thresholds:
  - `enabled` – master toggle.
  - `min_*_score` – global minimums for high-confluence alerts.
  - `types` – which alert types are active.
  - `volume_spike_*`, `squeeze_*`, `rsi_divergence_*` – per-type parameters.
  - `state_file` – path to `alerts_state.json` (relative to project root).
  - `rsi_divergence_timezone` – timezone for divergence logs.

If you later expand config with scoring regimes, patterns, storage, etc., **add new sections rather than renaming these** to avoid breaking existing code.

---

## 4. High-Level Behavior (What the Scanner Does)

**Goal:** For each run, take a set of symbols and timeframes, compute a **Confluence Score (0–100)** per symbol, detect setups (breakout, squeeze, etc.), rank them, and optionally send alerts + reports.

### 4.1 Batch Pipeline (Target / Conceptual)

This is the conceptual flow (what `src/main.py` is evolving toward):

1. **Load config** from `config.yaml`.
2. **Build exchange access** via `data/exchange_api.py`.
3. **Build repository** via `data/repository.py` (DB or direct-API abstraction).
4. **Discover universe** (currently: symbols from `exchange.symbols`).
5. For each **timeframe** in `timeframes`:
   1. Fetch OHLCV bars and derivatives metrics for all symbols.
   2. Compute **features**:
      - `features/trend.py`
      - `features/volume.py`
      - `features/volatility.py`
      - `features/relative_strength.py`
      - `features/positioning.py`
   3. Compute **component scores**:
      - `scoring/trend_score.py`
      - `scoring/volume_score.py`
      - `scoring/volatility_score.py`
      - `scoring/rs_score.py`
      - `scoring/positioning_score.py`
   4. Compute **market regime** via `data/market_health.py` + `scoring/regimes.py`.
   5. Compute **Confluence Score** using `scoring/confluence.py` (0–100).
   6. Detect **patterns** via `patterns/*`:
      - `breakout.py`
      - `volatility_squeeze.py`
      - `pullback.py`
      - `rsi_divergence.py`
   7. Pass scored+tagged symbols into `ranking/filters.py` + `ranking/ranking.py`.
6. Generate **report** via `reports/daily_report.py` (saved into `reports/`).
7. Generate **alerts** via `alerts/engine.py` + `alerts/notifiers.py` using config thresholds, updating `alerts_state.json` for dedupe.
8. Optionally, capture outputs in storage (DB, files) and/or run **backtests**.

Actual implementation may differ in small details, but **all helpers and new code should work within this pipeline**.

---

## 5. Module Responsibilities (Current + Intended)

### 5.1 `src/data/`

- `models.py`
  - Defines core dataclasses:
    - `Bar` – OHLCV bar (symbol, exchange, timestamp, O/H/L/C, volume).
    - `SymbolMeta` – symbol metadata (base, quote, is_perpetual, etc.).
    - `DerivativesMetrics` – funding + OI data.
    - `MarketHealth` – regime, breadth, BTC trend.
    - `ScoreBundle` / similar structure – container for per-symbol scores.
- `exchange_api.py`
  - CCXT-style abstraction to fetch OHLCV, funding, OI.
  - Knows about `exchange.id` and `exchange.derivatives.id` from config.
- `repository.py`
  - Repository pattern for reading/writing data (DB, files).
  - Currently used mainly as a data gateway; can later grow to Postgres.
- `market_health.py` (implied from pycache)
  - Compute BTC trend, breadth, and classify regime (bull / sideways / bear).

### 5.2 `src/features/`

Each module computes raw indicators/metrics, **not** scores:

- `trend.py` – MA alignment, ADX, trend persistence, distance from MA, etc.
- `volume.py` – RVOL, OBV trend, volume spikes, accumulation.
- `volatility.py` – BB width %, ATR %, volatility percentile, contraction.
- `relative_strength.py` – 1M/3M returns vs BTC, percentile ranks in universe.
- `positioning.py` – funding z-scores, OI changes, positioning features for perps.

The features are fed into scoring functions (see §5.3).

### 5.3 `src/scoring/`

Implements the **Confluence Score model** in code:

- `trend_score.py` – maps trend features → **Trend Score (0–100)**.
- `volume_score.py` – volume features → **Volume Score (0–100)**.
- `volatility_score.py` – volatility features → **Volatility Score (0–100)**.
- `rs_score.py` – RS features → **Relative Strength Score (0–100)**.
- `positioning_score.py` – derivatives features → **Positioning Score (0–100)**.
- `regimes.py` – market regime detection/weights helper (bull/sideways/bear).
- `confluence.py` – combines the above component scores into **Confluence Score (0–100)** using regime-specific weights and optional confidence/availability adjustments.

### 5.4 `src/patterns/`

Higher-level setup detection using scores + features:

- `breakout.py`
  - Detects breakouts above pivots/highs with volume confirmation.
- `volatility_squeeze.py`
  - Detects low-volatility squeeze setups (e.g., BB width percentile low, then expansion).
- `pullback.py`
  - Detects pullbacks within trends (“Holy Grail” type setups).
- `rsi_divergence.py`
  - Detects bullish and bearish RSI divergences.
  - Uses `alerts.rsi_divergence_*` config params and `rsi_divergence_timezone` for logs.

### 5.5 `src/ranking/`

- `filters.py`
  - Liquidity filters, feasibility filters, optional score-based cutoffs.
- `ranking.py`
  - Builds ranked lists (leaderboards), e.g.:
    - Top by Confluence Score.
    - Top by RS.
    - Top squeezes, top breakouts, etc.

### 5.6 `src/alerts/`

- `types.py`
  - Enum/definitions of alert types: `HIGH_CONFLUENCE`, `VOLUME_SPIKE`, `SQUEEZE_CANDIDATE`, `REGIME_CHANGE`, `RSI_DIVERGENCE`, etc.
- `state.py`
  - Reads/writes `alerts_state.json` using `alerts.state_file`.
  - Handles dedupe, cooldown, and min delta logic.
- `notifiers.py`
  - Channel implementations (Telegram, Discord, etc.), reading `alerts.telegram` and `alerts.discord` config sections.
- `engine.py`
  - Main alert routing / evaluation engine.
  - Consumes:
    - Scores and pattern classifications.
    - Alert thresholds from `config.yaml` (`alerts.min_*` etc.).
  - Decides which signals become alerts, updates state, and calls notifiers.

### 5.7 `src/reports/`

- `daily_report.py`
  - Builds markdown report for each run.
  - Uses:
    - Market regime (from `data/market_health.py` / `scoring/regimes.py`).
    - Ranked symbol lists from `ranking/ranking.py`.
    - Config options under `reports` (e.g. `top_n`, `output_dir`).

Reports are written into the `reports/` directory.

### 5.8 `src/backtest/`

- `backtest_engine.py`
  - Replays historical data and re-runs the scoring + pattern logic to evaluate outcomes.
  - Intended uses:
    - Measure forward returns after high-confluence events.
    - Event studies for individual pattern types.

### 5.9 `src/main.py`

Entry point orchestrating everything above.

Target signature (not enforced, but a good mental model):

```python
def main(config_path: str = "config.yaml") -> None:
    ...
```

When building new functionality, **wire it through `main.py`** rather than ad-hoc debug scripts, then reflect any major changes here in the spec.

---

## 6. Confluence Score Model (Short Summary)

The full quantitative design is defined in your Deep Research doc *“Quantitative ‘Confluence Score’ Model for Crypto Scanning”*. In implementation terms:

- Each asset/timeframe gets five component scores (0–100):
  1. **Trend Quality**
  2. **Volume & Liquidity**
  3. **Volatility (Compression)**
  4. **Relative Strength**
  5. **Positioning (Sentiment)**

- These components are combined into a **Confluence Score (0–100)** with **regime-aware weights** (bull/sideways/bear) determined via market health.

High-level behavior:

- **Trend Score**: Rewards bullish MA alignment, strong ADX, and trend persistence; penalizes excessive distance from MA (overextension).
- **Volume Score**: Rewards RVOL, OBV uptrend, accumulation, and healthy liquidity; identifies volume spikes.
- **Volatility Score**: High when volatility is unusually low vs its own history (squeeze), lower when volatility is already expanded.
- **RS Score**: High when 1M/3M returns are in top percentiles vs BTC/universe (O’Neil/Minervini style leaders).
- **Positioning Score**: Contrarian – high when funding is strongly negative with high OI (crowded shorts), low when funding is very positive with high OI (crowded longs).

Implementation details live in `src/scoring/*.py` and should always stay conceptually aligned with this section and the Deep Research doc.

---

## 7. Roadmap / Status (To Keep Updated)

Use this as a living checklist. Mark items `[x]` as they become solid and tested.

### 7.1 Core Architecture

- [x] Directory layout (`data`, `features`, `scoring`, `patterns`, `ranking`, `alerts`, `reports`, `backtest`) created.
- [x] `config.yaml` with timeframes, exchange, ranking, alerts.
- [ ] Expand `config.yaml` with explicit `scoring` / `regimes` / `patterns` sections.
- [ ] Confirm `data/market_health.py` API and integration with `scoring/regimes.py`.

### 7.2 Feature & Scoring Implementation

- [ ] Ensure each `features/*.py` exposes a clear, documented API (input: list[Bar], output: dict of feature values).
- [ ] Ensure each `scoring/*_score.py` maps those feature dicts → 0–100 scores as per the quant model.
- [ ] Ensure `confluence.py` uses regime-aware weighting and handles missing components gracefully.

### 7.3 Patterns, Ranking, Reports, Alerts

- [ ] Standardize pattern outputs (`patterns/*`) into a common signal format.
- [ ] Ensure `ranking/filters.py` and `ranking/ranking.py` operate on score+pattern structures.
- [ ] Verify `reports/daily_report.py` consumes rankings and market regime correctly.
- [ ] Verify `alerts/engine.py` applies thresholds from `config.yaml` and updates `alerts_state.json` as intended.

### 7.4 Backtesting & Testing

- [ ] Flesh out `backtest/backtest_engine.py` to replay historical data and compute performance metrics.
- [ ] Add unit tests in `tests/` for:
  - `data` (models, exchange_api, repository, market_health).
  - `features` and `scoring` (deterministic inputs → expected scores).
  - `patterns` (synthetic series triggering specific setups).
  - `ranking`, `alerts`, and `reports` key paths.

---

## 8. How to Use This Spec in Future Chats

When opening a new ChatGPT conversation to work on this project:

1. Say **explicitly**:  
   - “Repo: `crypto-confluence-scanner`”  
   - “Project spec is in `PROJECT_SPEC.md`.”
2. Paste the relevant section(s) from this file (e.g., module responsibilities, config, or Confluence Score summary).
3. Ask for changes *in terms of this spec*, e.g.:
   - “Implement `scoring/trend_score.py` to match §6 Trend Score behavior.”
   - “Add a new alert type under `alerts.types` and wire it through `alerts/engine.py` per §5.6.”
   - “Update `reports/daily_report.py` to show top N by Confluence Score as described in §5.7.”
4. If you change code in a way that alters architecture or semantics, **update this file** to match.

As long as this spec stays aligned with the repo, every future chat has a solid anchor and won’t invent its own structures or names.

---

_End of `PROJECT_SPEC.md`_
