# Credit Agent (LLM)

Small utility that fetches public financials (via Yahoo / `yfinance`), computes simple credit metrics and ratios, optionally asks OpenAI to render a short credit memo, and writes a PDF credit report.

Features
- Fetch latest financials for a ticker or company name
- Compute FCF, FCF / Debt, Debt / EBITDA, Interest coverage, DSCR, internal score
- Console snapshot and PDF report (`credit_report_<TICKER>.pdf`)
- Optional LLM memo included when `OPENAI_API_KEY` is set

Requirements
- Python 3.8+
- macOS / Unix-like shell
- Packages: `requests`, `yfinance`, `pandas`, `openai`, `reportlab`

Quick install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests yfinance pandas openai reportlab
```

Environment
- Optional: set OpenAI API key to enable LLM memo generation:

```bash
export OPENAI_API_KEY="sk-..."
```

Usage

Resolve a ticker/company and generate a PDF report:

```bash
python .venv/credit_agent_llm.py AAPL
```

Or pass a company name:

```bash
python .venv/credit_agent_llm.py "Apple Inc"
```

Behavior
- Prints a numeric credit snapshot to console.
- If `OPENAI_API_KEY` is present, generates an LLM credit memo and prints it.
- Writes a PDF named `credit_report_<TICKER>.pdf` to the current directory.

Notes & caveats
- Data source: Yahoo Finance via `yfinance` — validate before using for decisions.
- Calculations are simplified screening metrics; cross-check full statements before making decisions.
- OpenAI usage may incur cost and is subject to API limits and quota.

Troubleshooting
- If Yahoo search fails, the tool falls back to treating the input as a ticker.
- Ensure network access for `yfinance` and `requests`.
- If PDF generation fails, verify `reportlab` is installed.

Files
- Main script: `.venv/credit_agent_llm.py`
- Output example: `credit_report_AAPL.pdf`

License
- No license file included. Add one if you plan to publish.

---

Created automatically by assistant.

