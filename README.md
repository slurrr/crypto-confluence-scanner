# crypto-confluence-scanner
📈 Confluence Score Crypto Scanner

A modular Python-based crypto market scanner that computes a Confluence Score using trend, volume, volatility, relative strength, and positioning metrics.
Designed for swing trading setups and multi-timeframe analysis.

🚀 Project Status

Architecture complete — implementation in progress.

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


Each module corresponds to one stage of the pipeline:

data ingest → features → scoring → pattern detection → ranking → alerts → reporting

📦 Installation

Clone the repository:

git clone https://github.com/<yourname>/<reponame>.git
cd <reponame>


Create a virtual environment:

python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate


Install dependencies:

pip install -r requirements.txt

▶️ Running the Scanner (Once Implemented)
python -m src.main --config config.yaml


Or via the included script:

bash scripts/run_scan.sh

⚙️ Configuration

All scoring thresholds, exchange settings, and universe definitions live in:

config.yaml


This makes the entire scoring model fully tweakable without changing code.

🧪 Tests

Tests will live under:

tests/


Run them with:

pytest

📜 License

MIT (or your preferred license)
