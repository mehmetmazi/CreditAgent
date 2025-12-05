"""
Simple Flask web UI for viewing credit reports.

Run with:
    python credit_agent_frontend.py

Navigate to http://127.0.0.1:5000 and search for a ticker.
"""

from flask import Flask, render_template_string, request, url_for

from credit_agent import fetch_credit_metrics, human_readable

app = Flask(__name__)


def metrics_to_rows(metrics):
    """Prepare display rows for the template."""
    return [
        ("Company", f"{metrics.company_name} ({metrics.ticker})"),
        ("Fiscal year", metrics.fiscal_year or "n/a"),
        ("Revenue", human_readable(metrics.revenue)),
        ("EBITDA", human_readable(metrics.ebitda)),
        ("EBIT", human_readable(metrics.ebit)),
        ("Operating Cash Flow", human_readable(metrics.operating_cash_flow)),
        ("Capex", human_readable(metrics.capex)),
        ("Change in Working Capital", human_readable(metrics.change_in_wc)),
        ("Total Debt", human_readable(metrics.total_debt)),
        ("Interest Expense", human_readable(metrics.interest_expense)),
        (
            "Free Cash Flow (FCF)",
            human_readable(metrics.fcf),
        ),
        (
            "FCF / Debt",
            f"{metrics.fcf_to_debt:.2%}" if metrics.fcf_to_debt not in [float("inf"), float("-inf")] else "n/a",
        ),
        (
            "Debt / EBITDA",
            f"{metrics.debt_to_ebitda:.2f}" if metrics.debt_to_ebitda not in [float("inf"), float("-inf")] else "n/a",
        ),
        (
            "Interest Coverage",
            f"{metrics.interest_coverage:.2f}" if metrics.interest_coverage not in [float("inf"), float("-inf")] else "n/a",
        ),
        (
            "DSCR",
            f"{metrics.dscr:.2f}" if metrics.dscr not in [float("inf"), float("-inf")] else "n/a",
        ),
        ("Score (0–20)", str(metrics.score)),
        ("Risk Bucket", metrics.rating_bucket),
    ]


@app.route("/")
def index():
    ticker = request.args.get("ticker", "").strip()
    error = None
    metrics = None

    if ticker:
        try:
            metrics = fetch_credit_metrics(ticker)
        except Exception as exc:  # pragma: no cover - presentation layer
            error = f"Could not fetch credit metrics for '{ticker}': {exc}"

    template = """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Credit Report Viewer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 2rem; background: #f7f7f7; }
            .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
            h1 { margin-top: 0; }
            form { margin-bottom: 1.5rem; display: flex; gap: 0.5rem; }
            input[type="text"] { flex: 1; padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-size: 1rem; }
            button { padding: 0.75rem 1.1rem; border: none; background: #1d7dda; color: #fff; border-radius: 6px; font-size: 1rem; cursor: pointer; }
            button:hover { background: #1667b1; }
            .error { padding: 0.75rem 1rem; border-radius: 6px; background: #ffe6e6; color: #b30000; margin-bottom: 1rem; }
            table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
            th, td { padding: 0.65rem 0.5rem; border-bottom: 1px solid #eee; text-align: left; }
            th { width: 35%; color: #444; }
            .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; background: #e6f0ff; color: #16437e; font-weight: 600; }
            .muted { color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Credit Report Viewer</h1>
            <p class="muted">Enter a ticker symbol to generate a quick creditworthiness snapshot.</p>
            <form method="get" action="{{ url_for('index') }}">
                <input name="ticker" type="text" placeholder="e.g., AAPL" value="{{ ticker }}" aria-label="Ticker" required />
                <button type="submit">View report</button>
            </form>

            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}

            {% if metrics %}
            <h2>{{ metrics.company_name }} ({{ metrics.ticker.upper() }})</h2>
            {% if metrics.fiscal_year %}
            <p class="muted">Most recent fiscal year: {{ metrics.fiscal_year }}</p>
            {% endif %}
            <p><span class="badge">{{ metrics.rating_bucket }}</span> — Score: {{ metrics.score }}/20</p>
            <table>
                <tbody>
                {% for label, value in rows %}
                    <tr>
                        <th>{{ label }}</th>
                        <td>{{ value }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% endif %}
        </div>
    </body>
    </html>
    """

    rows = metrics_to_rows(metrics) if metrics else []
    return render_template_string(template, ticker=ticker, metrics=metrics, rows=rows)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)
