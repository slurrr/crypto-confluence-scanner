# 📌 Sprint Checklist — `crypto-confluence-scanner`

This checklist is structured to drop directly into your repo (e.g., `PROJECT_SPRINT_CHECKLIST.md`) and aligns exactly with your current architecture.

---

## 1️⃣ Foundation Stabilization

### **1.1 Standardize Feature Module APIs (`src/features/`)**
- [ x ] `features/trend.py` exposes `compute_trend_features(bars: list[Bar]) -> dict`
- [ x ] `features/volume.py` exposes `compute_volume_features(bars: list[Bar]) -> dict`
- [ x ] `features/volatility.py` exposes `compute_volatility_features(bars: list[Bar]) -> dict`
- [ x ] `features/relative_strength.py` exposes `compute_rs_features(bars: list[Bar], universe_returns) -> dict`
- [ x ] `features/positioning.py` exposes `compute_positioning_features(bars, derivatives) -> dict`
- [ x ] All feature dicts use consistent key naming (snake_case, stable schema)

### **1.2 `ScoreBundle` Data Model**
- [ x ] Add/update `ScoreBundle` in `data/models.py`:
  - `symbol: str`
  - `timeframe: str`
  - `features: dict`
  - `scores: dict`
  - `confluence_score: float`
  - `patterns: list[str]`  

### **1.3 Market Regime Integration**
- [ x ] Confirm `data/market_health.py` returns standardized structure
- [ x ] Confirm `scoring/regimes.py` maps market health → regime
- [ x ] Ensure `scoring/confluence.py` uses regime-specific weights

---

## 2️⃣ Feature & Scoring Completion

### **2.1 Feature Computation**
- [ x ] Implement **trend** feature logic
- [ x ] Implement **volume** feature logic (RVOL, OBV slope, spikes)
- [ x ] Implement **volatility** indicators (BBW%, ATR%, percentiles)
- [ x ] Implement **relative strength** metrics (1M/3M returns, universe ranks)
- [ x ] Implement **positioning** metrics (funding z-score, OI changes)

### **2.2 Component Scores (`src/scoring/`)**
- [ x ] `trend_score.py` → 0–100 Trend Score
- [ x ] `volume_score.py` → 0–100 Volume Score
- [ x ] `volatility_score.py` → 0–100 Volatility Score
- [ x ] `rs_score.py` → 0–100 RS Score
- [ x ] `positioning_score.py` → 0–100 Positioning Score
- [ x ] Validate score normalizations (min/max caps, percentiles, etc.)

### **2.3 Confluence Score**
- [ x ] Pull component scores
- [ x ] Apply regime-weighting
- [ x ] Implement missing-value fallbacks
- [ x ] Final `confluence_score: float` output

---

## 3️⃣ Pipeline Integration

### **3.1 Pattern Normalization (`src/patterns/`)**
- [ ] All pattern detectors return a unified structure:
  - e.g. `list[str]` or `list[PatternResult]`
- [ ] Update:
  - [ ] `breakout.py`
  - [ ] `volatility_squeeze.py`
  - [ ] `pullback.py`
  - [ ] `rsi_divergence.py`

### **3.2 Main Pipeline Wiring (`src/main.py`)**
- [ x ] Fetch OHLCV + derivatives for each symbol/timeframe
- [ x ] Compute all features
- [ x ] Compute all component scores
- [ x ] Compute confluence score
- [  ] Run pattern detection
- [ x ] Assemble `ScoreBundle`
- [  ] Collect results for ranking/reporting/alerts

### **3.3 Ranking & Filtering (`src/ranking/`)**
- [ ] Ensure `filters.py` applies liquidity & feasibility filters
- [ ] Ensure `ranking.py` sorts by:
  - [ ] confluence score  
  - [ ] RS score  
  - [ ] pattern presence  
- [ x ] Support top-N selection via config

### **3.4 Daily Report (`src/reports/daily_report.py`)**
- [ ] Render market regime summary
- [ ] Render top-N by confluence
- [ ] Render top-N by RS
- [ ] List breakouts, squeezes, divergences
- [ ] Save to `reports/` directory

### **3.5 Alerts Engine (`src/alerts/`)**
- [ ] Integrate ScoreBundle into alert evaluation
- [ ] Apply threshold logic from `config.yaml`
- [ ] Implement state dedupe via `alerts_state.json`
- [ ] Ensure alert types work:
  - [ ] high_confluence  
  - [ ] volume_spike  
  - [ ] squeeze_candidate  
  - [ ] regime_change  
  - [ ] rsi_divergence  
- [ ] Wire Telegram/Discord notifiers

---

## 4️⃣ Optional Round 2 Enhancements

### **4.1 Backtesting (`src/backtest/backtest_engine.py`)**
- [ ] Historical replay of bars
- [ ] Recompute scores & patterns
- [ ] Generate forward-return stats
- [ ] Produce signal-quality tables

### **4.2 Symbol Discovery Automation**
- [ ] Support exchange-wide symbol queries
- [ ] Add DexScreener / ApeX loader
- [ ] Add filtering rules (liq, volume, listing age)

### **4.3 Storage Layer**
- [ ] Add PostgreSQL repository adapter
- [ ] Write OHLCV, scores, and signals to DB
- [ ] Add read-back for dashboards/backtests

---

## 5️⃣ Testing Coverage (`/tests`)

### **5.1 Data Layer**
- [ ] `models.py` dataclass tests
- [ ] `exchange_api` fetch + structure tests
- [ ] `market_health` regime tests

### **5.2 Features & Scoring**
- [ ] Synthetic bars → known feature outputs
- [ ] Deterministic score outputs

### **5.3 Patterns**
- [ ] Synthetic breakout
- [ ] Synthetic squeeze
- [ ] Synthetic RSI divergence scenarios

### **5.4 Ranking, Reports, Alerts**
- [ ] Ranking order correctness
- [ ] Report markdown integrity
- [ ] Alert dedupe & cooldown logic

---

# ✔️ End of Sprint Checklist
