"""
Flask web application for Credit Analysis using FMP data.

Features:
- Search by company name or ticker symbol
- Display comprehensive credit metrics
- Show AI-generated credit memo
- Download PDF reports

Run with:
    python app.py

Navigate to http://127.0.0.1:5000
"""

import os
import math
from flask import Flask, render_template_string, request, send_file, jsonify, redirect
from werkzeug.utils import secure_filename

from credit_agent_fmp import (
    resolve_symbol,
    fetch_credit_metrics_for_symbol,
    human_readable,
    generate_credit_memo_with_llm,
    generate_pdf_report,
    CreditMetrics
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def format_ratio(value, format_type='ratio'):
    """Format ratio values for display."""
    if value in [math.inf, -math.inf]:
        return "n/a"
    if format_type == 'percent':
        return f"{value:.2%}"
    elif format_type == 'ratio':
        return f"{value:.2f}x"
    else:
        return f"{value:.2f}"


def format_memo_html(memo_text):
    """
    Format the LLM-generated memo text into proper HTML with sections.
    """
    if not memo_text:
        return ""

    import re

    # First, split by lines to detect section headers
    lines = memo_text.split('\n')
    formatted_html = []
    current_para = []

    for line in lines:
        line = line.strip()

        # Check if it's a section header (e.g., "1. Business overview")
        section_match = re.match(r'^(\d+)\.\s+(.+)$', line)

        if section_match:
            # Save any accumulated paragraph
            if current_para:
                para_text = ' '.join(current_para)
                formatted_html.append(f'<p>{para_text}</p>')
                current_para = []

            # Add section header
            formatted_html.append(f'<h3 class="memo-heading">{section_match.group(1)}. {section_match.group(2)}</h3>')
        elif not line:
            # Empty line - end current paragraph
            if current_para:
                para_text = ' '.join(current_para)
                formatted_html.append(f'<p>{para_text}</p>')
                current_para = []
        else:
            # Regular line - add to current paragraph
            current_para.append(line)

    # Don't forget the last paragraph
    if current_para:
        para_text = ' '.join(current_para)
        formatted_html.append(f'<p>{para_text}</p>')

    return '\n'.join(formatted_html)


@app.route("/")
def index():
    """Homepage with search form."""
    template = """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Credit Analysis Platform</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 2rem;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
            }

            .header {
                text-align: center;
                color: white;
                margin-bottom: 3rem;
            }

            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                font-weight: 700;
            }

            .header p {
                font-size: 1.1rem;
                opacity: 0.95;
            }

            .search-card {
                background: white;
                border-radius: 16px;
                padding: 2.5rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                margin-bottom: 2rem;
            }

            .search-form {
                display: flex;
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .search-input {
                flex: 1;
                padding: 1rem 1.5rem;
                border: 2px solid #e2e8f0;
                border-radius: 12px;
                font-size: 1.1rem;
                transition: all 0.3s;
            }

            .search-input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            .search-btn {
                padding: 1rem 2.5rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 1.1rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }

            .search-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            }

            .search-hint {
                color: #64748b;
                font-size: 0.95rem;
                text-align: center;
            }

            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1.5rem;
                margin-top: 2rem;
            }

            .feature-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 1.5rem;
                border-radius: 12px;
                text-align: center;
            }

            .feature-icon {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
            }

            .feature-title {
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 0.5rem;
            }

            .feature-desc {
                color: #64748b;
                font-size: 0.9rem;
            }

            .loading {
                text-align: center;
                padding: 2rem;
                display: none;
            }

            .spinner {
                border: 4px solid #f3f4f6;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
                margin: 0 auto 1rem;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2rem;
                }

                .search-form {
                    flex-direction: column;
                }

                .search-card {
                    padding: 1.5rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Credit Analysis Platform</h1>
                <p>Comprehensive creditworthiness analysis powered by FMP and AI</p>
            </div>

            <div class="search-card">
                <form method="get" action="/report" class="search-form" onsubmit="showLoading()">
                    <input
                        name="query"
                        type="text"
                        class="search-input"
                        placeholder="Enter company name or ticker (e.g., AAPL or Apple Inc)"
                        required
                        autofocus
                    />
                    <button type="submit" class="search-btn">Analyze</button>
                </form>
                <p class="search-hint">
                    Try: MSFT, Tesla, JPMorgan Chase, or any US-listed company
                </p>

                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Analyzing financial data...</p>
                </div>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">📊</div>
                    <div class="feature-title">Real-Time Data</div>
                    <div class="feature-desc">Latest financial metrics from Financial Modeling Prep</div>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🤖</div>
                    <div class="feature-title">AI-Powered Analysis</div>
                    <div class="feature-desc">Professional credit memos generated by GPT-4</div>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">📈</div>
                    <div class="feature-title">Credit Scoring</div>
                    <div class="feature-desc">Comprehensive 20-point creditworthiness assessment</div>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">📄</div>
                    <div class="feature-title">PDF Reports</div>
                    <div class="feature-desc">Download professional credit reports instantly</div>
                </div>
            </div>
        </div>

        <script>
            function showLoading() {
                document.getElementById('loading').style.display = 'block';
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(template)


@app.route("/report")
def report():
    """Display credit analysis report."""
    query = request.args.get("query", "").strip()

    if not query:
        return redirect("/")

    error = None
    metrics = None
    memo = None
    symbol = None

    # Get API key from environment
    fmp_api_key = os.getenv("FMP_API_KEY")
    if not fmp_api_key:
        error = "FMP_API_KEY environment variable is not set. Please configure your API key."
    else:
        try:
            symbol, company_name = resolve_symbol(query, fmp_api_key)
            metrics = fetch_credit_metrics_for_symbol(symbol, fmp_api_key, forced_name=company_name)

            if os.getenv("OPENAI_API_KEY"):
                try:
                    memo = generate_credit_memo_with_llm(metrics)
                except Exception as e:
                    memo = f"Note: Credit memo generation failed: {str(e)}"
            else:
                memo = "Note: Set OPENAI_API_KEY environment variable to enable AI-generated credit memos."

        except Exception as e:
            error = f"Could not fetch credit analysis for '{query}': {str(e)}"

    template = """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Credit Report - {{ metrics.company_name if metrics else query }}</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 2rem;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
            }

            .back-link {
                display: inline-block;
                color: white;
                text-decoration: none;
                margin-bottom: 1.5rem;
                font-weight: 500;
                transition: transform 0.2s;
            }

            .back-link:hover {
                transform: translateX(-5px);
            }

            .report-card {
                background: white;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                margin-bottom: 2rem;
            }

            .report-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 2.5rem;
            }

            .company-name {
                font-size: 2rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
            }

            .ticker {
                opacity: 0.9;
                font-size: 1.1rem;
            }

            .score-section {
                display: flex;
                align-items: center;
                gap: 2rem;
                margin-top: 1.5rem;
                padding-top: 1.5rem;
                border-top: 1px solid rgba(255, 255, 255, 0.2);
            }

            .score-circle {
                width: 120px;
                height: 120px;
                border-radius: 50%;
                background: white;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            }

            .score-value {
                font-size: 2.5rem;
                font-weight: 700;
                color: #667eea;
            }

            .score-max {
                font-size: 0.9rem;
                color: #64748b;
            }

            .risk-badge {
                padding: 0.75rem 1.5rem;
                border-radius: 12px;
                font-weight: 600;
                font-size: 1.1rem;
            }

            .risk-low { background: #dcfce7; color: #166534; }
            .risk-moderate { background: #fef3c7; color: #854d0e; }
            .risk-elevated { background: #fed7aa; color: #9a3412; }
            .risk-high { background: #fee2e2; color: #991b1b; }

            .report-content {
                padding: 2.5rem;
            }

            .section {
                margin-bottom: 2.5rem;
            }

            .section-title {
                font-size: 1.5rem;
                font-weight: 700;
                color: #1e293b;
                margin-bottom: 1.5rem;
                padding-bottom: 0.75rem;
                border-bottom: 2px solid #e2e8f0;
            }

            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 1.5rem;
            }

            .metric-card {
                background: #f8fafc;
                padding: 1.5rem;
                border-radius: 12px;
                border-left: 4px solid #667eea;
            }

            .metric-label {
                color: #64748b;
                font-size: 0.9rem;
                font-weight: 500;
                margin-bottom: 0.5rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .metric-value {
                font-size: 1.5rem;
                font-weight: 700;
                color: #1e293b;
            }

            .ratios-table {
                width: 100%;
                border-collapse: collapse;
            }

            .ratios-table th,
            .ratios-table td {
                padding: 1rem;
                text-align: left;
                border-bottom: 1px solid #e2e8f0;
            }

            .ratios-table th {
                background: #f8fafc;
                font-weight: 600;
                color: #475569;
            }

            .ratios-table td {
                font-size: 1.1rem;
                color: #1e293b;
            }

            .memo-section {
                background: #f8fafc;
                padding: 2rem;
                border-radius: 12px;
                line-height: 1.8;
                color: #1e293b;
                white-space: pre-wrap;
            }

            .memo-section p {
                margin-bottom: 1.25rem;
                text-align: justify;
            }

            .memo-section p:last-child {
                margin-bottom: 0;
            }

            .memo-heading {
                color: #667eea;
                font-size: 1.25rem;
                font-weight: 700;
                margin-top: 2rem;
                margin-bottom: 1rem;
                padding-top: 1rem;
                border-top: 2px solid #e2e8f0;
            }

            .memo-heading:first-child {
                margin-top: 0;
                padding-top: 0;
                border-top: none;
            }

            .memo-note {
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 1rem;
                border-radius: 6px;
                margin-top: 1rem;
                font-size: 0.95rem;
                color: #92400e;
            }

            .actions {
                display: flex;
                gap: 1rem;
                margin-top: 2rem;
            }

            .btn {
                padding: 0.875rem 1.75rem;
                border: none;
                border-radius: 12px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                text-decoration: none;
                display: inline-block;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            }

            .btn-secondary {
                background: white;
                color: #667eea;
                border: 2px solid #667eea;
            }

            .btn-secondary:hover {
                background: #f8fafc;
            }

            .error-card {
                background: #fee2e2;
                color: #991b1b;
                padding: 2rem;
                border-radius: 12px;
                border-left: 4px solid #dc2626;
            }

            .error-title {
                font-weight: 700;
                margin-bottom: 0.5rem;
            }

            @media (max-width: 768px) {
                body {
                    padding: 1rem;
                }

                .report-content {
                    padding: 1.5rem;
                }

                .company-name {
                    font-size: 1.5rem;
                }

                .score-section {
                    flex-direction: column;
                    align-items: flex-start;
                }

                .metrics-grid {
                    grid-template-columns: 1fr;
                }

                .actions {
                    flex-direction: column;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to search</a>

            {% if error %}
            <div class="report-card">
                <div class="report-content">
                    <div class="error-card">
                        <div class="error-title">Error</div>
                        <p>{{ error }}</p>
                    </div>
                </div>
            </div>
            {% elif metrics %}
            <div class="report-card">
                <div class="report-header">
                    <div class="company-name">{{ metrics.company_name }}</div>
                    <div class="ticker">{{ metrics.ticker }} {% if metrics.fiscal_year %}• FY {{ metrics.fiscal_year }}{% endif %}</div>

                    <div class="score-section">
                        <div class="score-circle">
                            <div class="score-value">{{ metrics.score }}</div>
                            <div class="score-max">/20</div>
                        </div>
                        <div class="risk-badge risk-{{ 'low' if 'Low' in metrics.rating_bucket else 'moderate' if 'Moderate' in metrics.rating_bucket else 'elevated' if 'Elevated' in metrics.rating_bucket else 'high' }}">
                            {{ metrics.rating_bucket }}
                        </div>
                    </div>
                </div>

                <div class="report-content">
                    <div class="section">
                        <h2 class="section-title">Core Financials</h2>
                        <div class="metrics-grid">
                            <div class="metric-card">
                                <div class="metric-label">Revenue</div>
                                <div class="metric-value">{{ human_readable(metrics.revenue) }}</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-label">EBITDA</div>
                                <div class="metric-value">{{ human_readable(metrics.ebitda) }}</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-label">EBIT</div>
                                <div class="metric-value">{{ human_readable(metrics.ebit) }}</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-label">Operating Cash Flow</div>
                                <div class="metric-value">{{ human_readable(metrics.operating_cash_flow) }}</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-label">Total Debt</div>
                                <div class="metric-value">{{ human_readable(metrics.total_debt) }}</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-label">Free Cash Flow</div>
                                <div class="metric-value">{{ human_readable(metrics.fcf) }}</div>
                            </div>
                        </div>
                    </div>

                    <div class="section">
                        <h2 class="section-title">Credit Ratios & Coverage</h2>
                        <table class="ratios-table">
                            <thead>
                                <tr>
                                    <th>Metric</th>
                                    <th>Value</th>
                                    <th>Interpretation</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Debt / EBITDA</td>
                                    <td>{{ format_ratio(metrics.debt_to_ebitda, 'ratio') }}</td>
                                    <td>{% if metrics.debt_to_ebitda < 2 %}Strong{% elif metrics.debt_to_ebitda < 3 %}Good{% elif metrics.debt_to_ebitda < 4 %}Moderate{% else %}Elevated{% endif %}</td>
                                </tr>
                                <tr>
                                    <td>Interest Coverage</td>
                                    <td>{{ format_ratio(metrics.interest_coverage, 'ratio') }}</td>
                                    <td>{% if metrics.interest_coverage > 8 %}Excellent{% elif metrics.interest_coverage > 5 %}Strong{% elif metrics.interest_coverage > 3 %}Adequate{% else %}Weak{% endif %}</td>
                                </tr>
                                <tr>
                                    <td>DSCR</td>
                                    <td>{{ format_ratio(metrics.dscr, 'ratio') }}</td>
                                    <td>{% if metrics.dscr > 1.8 %}Strong{% elif metrics.dscr > 1.4 %}Good{% elif metrics.dscr > 1.1 %}Adequate{% else %}Weak{% endif %}</td>
                                </tr>
                                <tr>
                                    <td>FCF / Debt</td>
                                    <td>{{ format_ratio(metrics.fcf_to_debt, 'percent') }}</td>
                                    <td>{% if metrics.fcf_to_debt > 0.25 %}Excellent{% elif metrics.fcf_to_debt > 0.15 %}Good{% elif metrics.fcf_to_debt > 0.08 %}Moderate{% else %}Low{% endif %}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div class="section">
                        <h2 class="section-title">AI-Generated Credit Analysis</h2>
                        {% if formatted_memo %}
                        <div class="memo-section">
                            {{ formatted_memo | safe }}
                        </div>
                        {% elif memo %}
                        <div class="memo-note">
                            <strong>Note:</strong> {{ memo }}
                        </div>
                        {% else %}
                        <div class="memo-note">
                            <strong>Note:</strong> Set OPENAI_API_KEY environment variable to enable AI-generated credit memos.
                        </div>
                        {% endif %}
                    </div>

                    <div class="actions">
                        <a href="/download-pdf?symbol={{ metrics.ticker }}" class="btn btn-primary">Download PDF Report</a>
                        <a href="/" class="btn btn-secondary">New Analysis</a>
                    </div>
                </div>
            </div>
            {% endif %}
        </div>
    </body>
    </html>
    """

    formatted_memo = format_memo_html(memo) if memo and not memo.startswith("Note:") else ""

    return render_template_string(
        template,
        query=query,
        error=error,
        metrics=metrics,
        memo=memo,
        formatted_memo=formatted_memo,
        human_readable=human_readable,
        format_ratio=format_ratio
    )


@app.route("/download-pdf")
def download_pdf():
    """Generate and download PDF report."""
    symbol = request.args.get("symbol", "").strip()

    if not symbol:
        return "Missing symbol parameter", 400

    fmp_api_key = os.getenv("FMP_API_KEY")
    if not fmp_api_key:
        return "FMP_API_KEY not configured", 500

    try:
        metrics = fetch_credit_metrics_for_symbol(symbol, fmp_api_key)

        memo_text = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                memo_text = generate_credit_memo_with_llm(metrics)
            except Exception:
                pass

        safe_symbol = metrics.ticker.replace("/", "_")
        filename = f"credit_report_{safe_symbol}.pdf"
        filepath = os.path.join("/tmp", filename)

        generate_pdf_report(metrics, memo_text, filepath)

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return f"Error generating PDF: {str(e)}", 500


@app.route("/api/search")
def api_search():
    """API endpoint for searching companies."""
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    fmp_api_key = os.getenv("FMP_API_KEY")
    if not fmp_api_key:
        return jsonify({"error": "FMP_API_KEY not configured"}), 500

    try:
        symbol, company_name = resolve_symbol(query, fmp_api_key)
        return jsonify({
            "symbol": symbol,
            "company_name": company_name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("=" * 70)
    print("Credit Analysis Platform")
    print("=" * 70)
    print("\nStarting Flask server...")
    print("Navigate to: http://127.0.0.1:5000")
    print("\nRequired environment variables:")
    print(f"  FMP_API_KEY: {'✓ Set' if os.getenv('FMP_API_KEY') else '✗ Not set'}")
    print(f"  OPENAI_API_KEY: {'✓ Set' if os.getenv('OPENAI_API_KEY') else '✗ Not set (optional)'}")
    print("\n" + "=" * 70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)