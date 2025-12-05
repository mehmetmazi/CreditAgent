import sys
import math
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import requests
import yfinance as yf
import pandas as pd
from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# ---------- Data structures ----------

@dataclass
class CreditMetrics:
    ticker: str
    company_name: str
    fiscal_year: str

    revenue: float
    ebitda: float
    ebit: float
    interest_expense: float
    operating_cash_flow: float
    capex: float
    change_in_wc: float
    total_debt: float

    fcf: float
    fcf_to_debt: float
    debt_to_ebitda: float
    interest_coverage: float
    dscr: float

    score: int
    rating_bucket: str


# ---------- Helpers ----------

def safe_get(df: pd.DataFrame, label_candidates, default=0.0):
    """
    Try several possible row labels in a yfinance dataframe and
    return the most recent value.
    """
    if df is None or df.empty:
        return default
    for label in label_candidates:
        if label in df.index:
            value = df.loc[label]
            if isinstance(value, pd.Series):
                return float(value.iloc[0])
            return float(value)
    return default


def human_readable(num: float) -> str:
    if num == math.inf:
        return "∞"
    if num == -math.inf:
        return "-∞"
    try:
        abs_val = abs(num)
        sign = "-" if num < 0 else ""
        if abs_val >= 1e9:
            return f"{sign}{abs_val/1e9:.2f}B"
        elif abs_val >= 1e6:
            return f"{sign}{abs_val/1e6:.2f}M"
        elif abs_val >= 1e3:
            return f"{sign}{abs_val/1e3:.2f}K"
        else:
            return f"{num:.2f}"
    except Exception:
        return str(num)


# ---------- Ticker resolution from company name ----------

def resolve_ticker_from_query(query: str) -> Tuple[str, str]:
    """
    Resolve a company name or ticker into a symbol + display name.

    - If the query already looks like a ticker (e.g. 'AAPL'), skip web search.
    - If Yahoo search rate-limits us (429) or fails, fall back to treating the input as a ticker.
    """
    raw = query.strip()

    # If it already looks like a ticker (simple heuristic), just use it
    if raw.isupper() and " " not in raw and 1 <= len(raw) <= 6:
        return raw, raw

    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": raw, "quotesCount": 1, "newsCount": 0}
    headers = {
        "User-Agent": "Mozilla/5.0 credit-agent-bot"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Warning: Yahoo Finance search HTTP error. "
              "Falling back to treating your input as a ticker.")
        return raw.upper(), raw
    except requests.exceptions.RequestException as e:
        print(f"Warning: problem calling Yahoo Finance search: {e}. "
              f"Falling back to treating '{raw}' as a ticker.")
        return raw.upper(), raw

    data = resp.json()
    quotes = data.get("quotes", [])
    if not quotes:
        print(f"Warning: no quotes found for '{raw}'. "
              "Trying to use it directly as a ticker.")
        return raw.upper(), raw

    best = quotes[0]
    symbol = best.get("symbol") or raw.upper()
    name = best.get("shortname") or best.get("longname") or symbol
    return symbol, name


# ---------- Scoring logic ----------

def compute_score(metrics: CreditMetrics) -> CreditMetrics:
    """
    Score each metric 1–5 and total (0–20).
    """
    score = 0

    # Debt / EBITDA
    d_e = metrics.debt_to_ebitda
    if d_e <= 0:  # no debt or negative EBITDA
        debt_ebitda_score = 5
    elif d_e < 2:
        debt_ebitda_score = 5
    elif d_e < 3:
        debt_ebitda_score = 4
    elif d_e < 4:
        debt_ebitda_score = 3
    elif d_e < 5:
        debt_ebitda_score = 2
    else:
        debt_ebitda_score = 1
    score += debt_ebitda_score

    # Interest coverage
    ic = metrics.interest_coverage
    if ic > 8:
        ic_score = 5
    elif ic > 5:
        ic_score = 4
    elif ic > 3:
        ic_score = 3
    elif ic > 1.5:
        ic_score = 2
    else:
        ic_score = 1
    score += ic_score

    # DSCR
    dscr = metrics.dscr
    if dscr > 1.8:
        dscr_score = 5
    elif dscr > 1.4:
        dscr_score = 4
    elif dscr > 1.1:
        dscr_score = 3
    elif dscr > 1.0:
        dscr_score = 2
    else:
        dscr_score = 1
    score += dscr_score

    # FCF / Debt
    fcf_d = metrics.fcf_to_debt
    if fcf_d > 0.25:
        fcf_score = 5
    elif fcf_d > 0.15:
        fcf_score = 4
    elif fcf_d > 0.08:
        fcf_score = 3
    elif fcf_d > 0.03:
        fcf_score = 2
    else:
        fcf_score = 1
    score += fcf_score

    # Bucket
    if score >= 17:
        bucket = "Low credit risk"
    elif score >= 13:
        bucket = "Moderate credit risk"
    elif score >= 9:
        bucket = "Elevated credit risk"
    else:
        bucket = "High credit risk"

    metrics.score = score
    metrics.rating_bucket = bucket
    return metrics


# ---------- Core metrics fetch ----------

def fetch_credit_metrics_for_ticker(ticker: str, forced_name: Optional[str] = None) -> CreditMetrics:
    """
    - Fetch financials via yfinance
    - Compute FCF + credit ratios
    - Return CreditMetrics
    """
    tk = yf.Ticker(ticker)

    info = tk.info or {}
    company_name = forced_name or info.get("longName") or info.get("shortName") or ticker

    income = tk.income_stmt
    cashflow = tk.cashflow
    balance = tk.balance_sheet

    fiscal_year = ""
    for df in [income, cashflow, balance]:
        if df is not None and not df.empty:
            col = df.columns[0]
            fiscal_year = str(getattr(col, "year", col))
            break

    revenue = safe_get(income, ["Total Revenue", "Revenue", "Net Revenue"])
    ebitda = safe_get(income, ["Ebitda", "EBITDA"])
    ebit = safe_get(income, ["Ebit", "EBIT", "Operating Income", "Operating Income or Loss"])
    interest_expense = safe_get(income, ["Interest Expense", "Interest Expense Non Operating"])

    operating_cash_flow = safe_get(cashflow, ["Total Cash From Operating Activities", "Operating Cash Flow"])
    capex = -safe_get(cashflow, ["Capital Expenditures", "Purchase Of Property Plant And Equipment"])
    change_in_wc = safe_get(cashflow, ["Change In Working Capital", "Change In Working Capital"])

    short_term_debt = safe_get(balance, ["Short Long Term Debt", "Short Term Debt"])
    long_term_debt = safe_get(balance, ["Long Term Debt", "Long Term Debt Noncurrent"])
    total_debt = short_term_debt + long_term_debt

    # FCF ≈ OCF - capex
    if operating_cash_flow == 0 and ebit != 0:
        tax_rate = 0.25
        fcf = ebit * (1 - tax_rate) - capex - change_in_wc
    else:
        fcf = operating_cash_flow - capex

    fcf_to_debt = (fcf / total_debt) if total_debt > 0 else math.inf
    debt_to_ebitda = (total_debt / ebitda) if ebitda != 0 else math.inf
    interest_coverage = (ebit / abs(interest_expense)) if interest_expense != 0 else math.inf

    denom = abs(interest_expense) + short_term_debt
    dscr = (operating_cash_flow / denom) if denom > 0 else math.inf

    metrics = CreditMetrics(
        ticker=ticker,
        company_name=company_name,
        fiscal_year=fiscal_year,
        revenue=revenue,
        ebitda=ebitda,
        ebit=ebit,
        interest_expense=interest_expense,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        change_in_wc=change_in_wc,
        total_debt=total_debt,
        fcf=fcf,
        fcf_to_debt=fcf_to_debt,
        debt_to_ebitda=debt_to_ebitda,
        interest_coverage=interest_coverage,
        dscr=dscr,
        score=0,
        rating_bucket="",
    )

    return compute_score(metrics)


# ---------- Console reporting (optional) ----------

def print_numeric_report(metrics: CreditMetrics):
    print("=" * 70)
    print(f" Creditworthiness Snapshot – {metrics.company_name} ({metrics.ticker})")
    if metrics.fiscal_year:
        print(f" Fiscal year: {metrics.fiscal_year}")
    print("=" * 70)
    print("\n-- Core Financials --")
    print(f"Revenue:                {human_readable(metrics.revenue)}")
    print(f"EBITDA:                 {human_readable(metrics.ebitda)}")
    print(f"EBIT:                   {human_readable(metrics.ebit)}")
    print(f"Operating Cash Flow:    {human_readable(metrics.operating_cash_flow)}")
    print(f"Capex:                  {human_readable(metrics.capex)}")
    print(f"Change in Working Cap.: {human_readable(metrics.change_in_wc)}")
    print(f"Total Debt:             {human_readable(metrics.total_debt)}")
    print(f"Interest Expense:       {human_readable(metrics.interest_expense)}")

    print("\n-- Cash Flow & Coverage --")
    if metrics.fcf_to_debt not in [math.inf, -math.inf]:
        fcf_debt_line = f"{metrics.fcf_to_debt:.2%}"
    else:
        fcf_debt_line = "n/a"
    if metrics.debt_to_ebitda not in [math.inf, -math.inf]:
        d_e_line = f"{metrics.debt_to_ebitda:.2f}"
    else:
        d_e_line = "n/a"
    if metrics.interest_coverage not in [math.inf, -math.inf]:
        ic_line = f"{metrics.interest_coverage:.2f}"
    else:
        ic_line = "n/a"
    if metrics.dscr not in [math.inf, -math.inf]:
        dscr_line = f"{metrics.dscr:.2f}"
    else:
        dscr_line = "n/a"

    print(f"Free Cash Flow (FCF):   {human_readable(metrics.fcf)}")
    print(f"FCF / Debt:             {fcf_debt_line}")
    print(f"Debt / EBITDA:          {d_e_line}")
    print(f"Interest Coverage:      {ic_line}")
    print(f"DSCR:                   {dscr_line}")

    print("\n-- Credit View --")
    print(f"Score (0–20):           {metrics.score}")
    print(f"Risk Bucket:            {metrics.rating_bucket}")

    print("\nInterpretation:")
    if metrics.rating_bucket == "Low credit risk":
        print("• Strong capacity to service debt; leverage and coverage metrics are comfortable.")
    elif metrics.rating_bucket == "Moderate credit risk":
        print("• Reasonable ability to service debt, but metrics could tighten in a downturn.")
    elif metrics.rating_bucket == "Elevated credit risk":
        print("• Weaker cushion; the company may struggle under stress or higher interest rates.")
    else:
        print("• High risk profile; limited headroom to absorb shocks or refinancing stress.")

    print("\nNOTE: This is a simplified model using public data via yfinance; "
          "always cross-check with full financial statements & disclosures.")
    print("=" * 70)


# ---------- OpenAI credit memo ----------

def generate_credit_memo_with_llm(metrics: CreditMetrics, model: str = "gpt-4.1-mini") -> str:
    """
    Use OpenAI Responses API to turn numeric metrics into a structured credit memo.
    Requires OPENAI_API_KEY in the environment.
    """
    client = OpenAI()  # uses OPENAI_API_KEY

    prompt = f"""
You are an experienced sell-side credit analyst.

Write a structured, professional credit memo on {metrics.company_name} (ticker: {metrics.ticker}).

Use the following quantitative metrics (latest fiscal year):

- Revenue: {human_readable(metrics.revenue)}
- EBITDA: {human_readable(metrics.ebitda)}
- EBIT: {human_readable(metrics.ebit)}
- Operating cash flow: {human_readable(metrics.operating_cash_flow)}
- Capex: {human_readable(metrics.capex)}
- Change in working capital: {human_readable(metrics.change_in_wc)}
- Total debt: {human_readable(metrics.total_debt)}
- Interest expense: {human_readable(metrics.interest_expense)}
- Free cash flow (FCF): {human_readable(metrics.fcf)}
- FCF / Debt: {"n/a" if metrics.fcf_to_debt in [math.inf, -math.inf] else f"{metrics.fcf_to_debt:.2%}"}
- Debt / EBITDA: {"n/a" if metrics.debt_to_ebitda in [math.inf, -math.inf] else f"{metrics.debt_to_ebitda:.2f}x"}
- Interest coverage (EBIT / interest): {"n/a" if metrics.interest_coverage in [math.inf, -math.inf] else f"{metrics.interest_coverage:.2f}x"}
- DSCR (OCF / (interest + short-term debt proxy)): {"n/a" if metrics.dscr in [math.inf, -math.inf] else f"{metrics.dscr:.2f}x"}
- Internal score (0–20): {metrics.score}
- Risk bucket: {metrics.rating_bucket}

Write the memo in concise UK English with these section headings:

1. Business overview
2. Recent financial performance
3. Cash flow generation and leverage
4. Debt structure and debt service capacity
5. Key risks and mitigants
6. Overall credit view and recommendation

Focus strictly on the metrics above. Where information is missing, say so explicitly rather than inventing details.
"""

    response = client.responses.create(
        model=model,
        input=prompt.strip(),
    )

    return response.output_text


# ---------- PDF generation ----------

def _draw_wrapped_text(c: canvas.Canvas, text: str,
                       x: float, y: float,
                       max_width: float,
                       line_height: float,
                       font_name: str = "Helvetica",
                       font_size: int = 10,
                       bottom_margin: float = 40) -> float:
    """
    Draw word-wrapped text onto the canvas.
    Returns the new y-coordinate after drawing.
    Automatically creates new pages if we hit the bottom.
    """
    c.setFont(font_name, font_size)
    words = text.split()
    line = ""
    width, height = A4

    for word in words:
        test_line = word if line == "" else line + " " + word
        if c.stringWidth(test_line, font_name, font_size) <= max_width:
            line = test_line
        else:
            if y < bottom_margin:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - bottom_margin
            c.drawString(x, y, line)
            y -= line_height
            line = word

    if line:
        if y < bottom_margin:
            c.showPage()
            c.setFont(font_name, font_size)
            y = height - bottom_margin
        c.drawString(x, y, line)
        y -= line_height

    return y


def generate_pdf_report(metrics: CreditMetrics, memo_text: Optional[str], filename: str) -> None:
    """
    Create a nicely formatted PDF with:
    - Numeric credit snapshot
    - LLM memo (if provided)
    """
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, f"Credit Report – {metrics.company_name} ({metrics.ticker})")
    y -= 24
    if metrics.fiscal_year:
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Fiscal year: {metrics.fiscal_year}")
        y -= 18

    # Section: Core Financials
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "1. Core Financials")
    y -= 18
    c.setFont("Helvetica", 10)

    lines = [
        f"Revenue:                {human_readable(metrics.revenue)}",
        f"EBITDA:                 {human_readable(metrics.ebitda)}",
        f"EBIT:                   {human_readable(metrics.ebit)}",
        f"Operating Cash Flow:    {human_readable(metrics.operating_cash_flow)}",
        f"Capex:                  {human_readable(metrics.capex)}",
        f"Change in Working Cap.: {human_readable(metrics.change_in_wc)}",
        f"Total Debt:             {human_readable(metrics.total_debt)}",
        f"Interest Expense:       {human_readable(metrics.interest_expense)}",
    ]
    for line in lines:
        if y < margin:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 10)
        c.drawString(margin, y, line)
        y -= 14

    # Section: Coverage & Ratios
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "2. Cash Flow & Coverage")
    y -= 18
    c.setFont("Helvetica", 10)

    if metrics.fcf_to_debt not in [math.inf, -math.inf]:
        fcf_debt_line = f"{metrics.fcf_to_debt:.2%}"
    else:
        fcf_debt_line = "n/a"
    if metrics.debt_to_ebitda not in [math.inf, -math.inf]:
        d_e_line = f"{metrics.debt_to_ebitda:.2f}x"
    else:
        d_e_line = "n/a"
    if metrics.interest_coverage not in [math.inf, -math.inf]:
        ic_line = f"{metrics.interest_coverage:.2f}x"
    else:
        ic_line = "n/a"
    if metrics.dscr not in [math.inf, -math.inf]:
        dscr_line = f"{metrics.dscr:.2f}x"
    else:
        dscr_line = "n/a"

    ratio_lines = [
        f"Free Cash Flow (FCF):   {human_readable(metrics.fcf)}",
        f"FCF / Debt:             {fcf_debt_line}",
        f"Debt / EBITDA:          {d_e_line}",
        f"Interest Coverage:      {ic_line}",
        f"DSCR:                   {dscr_line}",
    ]
    for line in ratio_lines:
        if y < margin:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 10)
        c.drawString(margin, y, line)
        y -= 14

    # Section: Score & Interpretation
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "3. Internal Credit View")
    y -= 18
    c.setFont("Helvetica", 10)

    if y < margin:
        c.showPage()
        y = height - margin
        c.setFont("Helvetica", 10)

    c.drawString(margin, y, f"Score (0–20): {metrics.score}")
    y -= 14
    c.drawString(margin, y, f"Risk bucket:  {metrics.rating_bucket}")
    y -= 18

    interpretation = ""
    if metrics.rating_bucket == "Low credit risk":
        interpretation = "Strong capacity to service debt; leverage and coverage metrics are comfortable."
    elif metrics.rating_bucket == "Moderate credit risk":
        interpretation = "Reasonable ability to service debt, but metrics could tighten in a downturn."
    elif metrics.rating_bucket == "Elevated credit risk":
        interpretation = "Weaker cushion; the company may struggle under stress or higher interest rates."
    else:
        interpretation = "High risk profile; limited headroom to absorb shocks or refinancing stress."

    y = _draw_wrapped_text(
        c,
        "Interpretation: " + interpretation,
        x=margin,
        y=y,
        max_width=width - 2 * margin,
        line_height=14,
        font_name="Helvetica",
        font_size=10,
        bottom_margin=margin,
    )

    # Section: LLM memo, if provided
    if memo_text:
        y -= 10
        if y < margin:
            c.showPage()
            y = height - margin
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "4. Analyst-style Credit Memo (LLM-generated)")
        y -= 18
        y = _draw_wrapped_text(
            c,
            memo_text,
            x=margin,
            y=y,
            max_width=width - 2 * margin,
            line_height=14,
            font_name="Helvetica",
            font_size=10,
            bottom_margin=margin,
        )

    # Footer note
    if y < margin:
        c.showPage()
        y = height - margin
    y -= 10
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        margin,
        y,
        "Note: This report is generated automatically using public financial data. "
        "It should be supplemented with full financial statements and disclosures."
    )

    c.save()


# ---------- CLI entrypoint ----------

def main():
    if len(sys.argv) < 2:
        print("Usage: python credit_agent.py <TICKER_OR_COMPANY_NAME>")
        print("Example: python credit_agent.py AAPL")
        print("         python credit_agent.py \"Apple Inc\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).strip()

    try:
        ticker, name_from_search = resolve_ticker_from_query(query)
        metrics = fetch_credit_metrics_for_ticker(ticker, forced_name=name_from_search)
    except Exception as e:
        print(f"Error resolving or fetching data for '{query}': {e}")
        sys.exit(1)

    # Console snapshot (optional, for debugging)
    print_numeric_report(metrics)

    memo_text = None

    # Try to generate a memo if API key is present
    if os.getenv("OPENAI_API_KEY"):
        print("\nGenerating LLM-based credit memo via OpenAI...\n")
        try:
            memo_text = generate_credit_memo_with_llm(metrics)
            print(memo_text)  # also show in console
        except Exception as e:
            print(f"Error generating credit memo with OpenAI: {e}")
            memo_text = f"(Memo generation failed: {e})"
    else:
        print("\nNo OPENAI_API_KEY found in environment; skipping LLM memo in PDF.")
        memo_text = None

    # Generate PDF
    safe_ticker = metrics.ticker.replace("/", "_")
    filename = f"credit_report_{safe_ticker}.pdf"
    generate_pdf_report(metrics, memo_text, filename)
    print(f"\nPDF report saved as: {filename}")


if __name__ == "__main__":
    main()
