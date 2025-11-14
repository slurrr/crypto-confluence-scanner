# crypto-confluence-scanner
📈 Confluence Score Crypto Scanner

A modular Python-based crypto market scanner that analyzes trend quality, volume behavior, volatility compression, relative strength, and positioning to compute a Confluence Score and identify high-probability swing trading setups.

The system is designed to be:

Exchange-agnostic (Binance, Coinbase, Apex Omni, CCXT, REST)

Configurable (thresholds, weights, scoring formulas in config.yaml)

Extensible (supports crypto now, equities/futures later)

Modular (clean separation of data layer, features, scoring, patterns, ranking, alerts, reports)

Research-driven (architecture based on Deep Research analysis of Williams, Minervini, Raschke, O’Neil, etc.)

🚀 Project Status

Architecture complete.
Implementation in progress.

This repository currently includes the full folder structure and placeholders for all modules.
Features, scoring logic, data gateway, and ranking components will be implemented iteratively.

🧱 Directory Structure (High-Level)
src/
  data/
  features/
  scoring/
  patterns/
  ranking/
  alerts/
  reports/
  backtest/

config.yaml
scripts/
tests/


Each module is responsible for a specific layer of the pipeline (data ingest → features → scoring → pattern detection → ranking → alerts + reporting).

📦 Installation
git clone https://github.com/<yourname>/<reponame>.git
cd <reponame>

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

▶️ Running the Scanner (Once Implemented)
python -m src.main --config config.yaml


Or via the included script:

bash scripts/run_scan.sh

⚙️ Configuration

All tunable scoring parameters, thresholds, exchange settings, and universe definitions live in:

config.yaml


This makes the scoring model fully tweakable without changing code.

🧪 Tests

Tests will live under:

tests/


and can be run with:

pytest


(once added)

📜 License

MIT (or your preferred license)
