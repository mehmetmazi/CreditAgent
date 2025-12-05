import sys
import math
import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List

import requests
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

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
    except (TypeError, ValueError):
        return str(num)


def _get_json(url: str, params: Dict[str, Any]) -> Any:
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------- FMP fetch functions ----------

def fetch_fmp_income_statement(symbol: str, api_key: str) -> Dict[str, Any]:
    """
    Returns the latest annual income statement dict from FMP.
    Endpoint: /api/v3/income-statement/{symbol}?limit=1
    """
    url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}"
    params = {"limit": 1, "apikey": api_key}
    data = _get_json(url, params)
    if not data:
        raise ValueError(f"No income statement data for {symbol}")
    return data[0]


def fetch_fmp_balance_sheet(symbol: str, api_key: str) -> Dict[str, Any]:
    """
    Returns the latest annual balance sheet dict from FMP.
    Endpoint: /api/v3/balance-sheet-statement/{symbol}?limit=1
    """
    url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}"
    params = {"limit": 1, "apikey": api_key}
    data = _get_json(url, params)
    if not data:
        raise ValueError(f"No balance sheet data for {symbol}")
    return data[0]


def fetch_fmp_cash_flow(symbol: str, api_key: str) -> Dict[str, Any]:
    """
    Returns the latest annual cash flow statement dict from FMP.
    Endpoint: /api/v3/cash-flow-statement/{symbol}?limit=1
    """
    url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}"
    params = {"limit": 1, "apikey": api_key}
    data = _get_json(url, params)
    if not data:
        raise ValueError(f"No cash flow data for {symbol}")
    return data[0]


def fetch_fmp_profile(symbol: str, api_key: str) -> Dict[str, Any]:
    """
    Returns company profile with name, etc.
    Endpoint: /api/v3/profile/{symbol}
    """
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
    params = {"apikey": api_key}
    data = _get_json(url, params)
    if not data:
        return {}
    return data[0]


# ---------- Symbol / name resolution ----------

def resolve_symbol(query: str, api_key: str) -> Tuple[str, str]:
    """
    Use FMP's search endpoint to resolve a name/ticker into a symbol + company name.

    Endpoint: /api/v3/search
    """
    raw = query.strip()

    # If they already gave something ticker-like, we'll still run search but fallback gracefully.
    url = "https://financialmodelingprep.com/api/v3/search"
    params = {"query": raw, "limit": 1, "exchange": "NASDAQ,NYSE,AMEX", "apikey": api_key}
    try:
        data = _get_json(url, params)
    except Exception as e:
        print(f"Warning: FMP search failed: {e}. Falling back to using '{raw}' as symbol.")
        return raw.upper(), raw

    if not data:
        print(f"Warning: no FMP search result for '{raw}'. Using it directly as symbol.")
        return raw.upper(), raw

    best = data[0]
    symbol = best.get("symbol", raw.upper())
    name = best.get("name", symbol)
    return symbol, name


# ---------- Scoring logic ----------

def _get_debt_ebitda_score(d_e: float) -> int:
    if d_e <= 0:
        return 5
    elif d_e < 2:
        return 5
    elif d_e < 3:
        return 4
    elif d_e < 4:
        return 3
    elif d_e < 5:
        return 2
    else:
        return 1


def _get_interest_coverage_score(ic: float) -> int:
    if ic > 8:
        return 5
    elif ic > 5:
        return 4
    elif ic > 3:
        return 3
    elif ic > 1.5:
        return 2
    else:
        return 1


def _get_dscr_score(dscr: float) -> int:
    if dscr > 1.8:
        return 5
    elif dscr > 1.4:
        return 4
    elif dscr > 1.1:
        return 3
    elif dscr > 1.0:
        return 2
    else:
        return 1


def _get_fcf_to_debt_score(fcf_d: float) -> int:
    if fcf_d > 0.25:
        return 5
    elif fcf_d > 0.15:
        return 4
    elif fcf_d > 0.08:
        return 3
    elif fcf_d > 0.03:
        return 2
    else:
        return 1


def compute_score(metrics: CreditMetrics) -> CreditMetrics:
    """
    Score each metric 1–5 and total (0–20).
    """
    score = (
        _get_debt_ebitda_score(metrics.debt_to_ebitda)
        + _get_interest_coverage_score(metrics.interest_coverage)
        + _get_dscr_score(metrics.dscr)
        + _get_fcf_to_debt_score(metrics.fcf_to_debt)
    )

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


# ---------- Core metrics from FMP ----------

def fetch_credit_metrics_for_symbol(symbol: str, api_key: str, forced_name: Optional[str] = None) -> CreditMetrics:
    """
    Pull FMP statements and derive the credit metrics.
    """
    income = fetch_fmp_income_statement(symbol, api_key)
    balance = fetch_fmp_balance_sheet(symbol, api_key)
    cashflow = fetch_fmp_cash_flow(symbol, api_key)
    profile = fetch_fmp_profile(symbol, api_key)

    company_name = forced_name or profile.get("companyName") or profile.get("companyName") or symbol

    # Fiscal year: FMP has 'date' and 'calendarYear'
    fiscal_year = str(income.get("calendarYear") or income.get("date", "")[:4])

    # Income statement fields (keys are per FMP docs)
    revenue = float(income.get("revenue") or 0.0)
    ebitda = float(income.get("ebitda") or 0.0)
    ebit = float(income.get("ebit") or 0.0)
    interest_expense = float(income.get("interestExpense") or 0.0)

    # Cash flow
    operating_cash_flow = float(cashflow.get("netCashProvidedByOperatingActivities") or
                                cashflow.get("netCashProvidedByOperatingActivitiesReported") or 0.0)

    # FMP capex is usually in 'capitalExpenditure'
    capex = float(cashflow.get("capitalExpenditure") or 0.0)
    # Make capex positive outflow
    if capex < 0:
        capex = -capex

    # Working capital changes can be approximated from 'changeInWorkingCapital' if present
    change_in_wc = float(cashflow.get("changeInWorkingCapital") or 0.0)

    # Balance sheet: debt
    short_term_debt = float(balance.get("shortTermDebt") or balance.get("shortTermBorrowings") or 0.0)
    long_term_debt = float(balance.get("longTermDebt") or 0.0)
    total_debt = short_term_debt + long_term_debt

    # FCF ≈ OCF - capex
    if operating_cash_flow == 0 and ebit != 0:
        tax_rate = 0.25
        fcf = ebit * (1 - tax_rate) - capex - change_in_wc
    else:
        fcf = operating_cash_flow - capex

    fcf_to_debt = (fcf / total_debt) if total_debt > 0 else math.inf
    debt_to_ebitda = (total_debt / ebitda) if ebitda != 0 else math.inf
    interest_coverage = (ebit / abs(float(interest_expense))) if interest_expense != 0 else math.inf

    denom = abs(float(interest_expense)) + short_term_debt
    dscr = (operating_cash_flow / denom) if denom > 0 else math.inf

    metrics = CreditMetrics(
        ticker=symbol,
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


# ---------- Console report ----------

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
    fcf_debt_line = "n/a" if metrics.fcf_to_debt in [math.inf, -math.inf] else f"{metrics.fcf_to_debt:.2%}"
    d_e_line = "n/a" if metrics.debt_to_ebitda in [math.inf, -math.inf] else f"{metrics.debt_to_ebitda:.2f}"
    ic_line = "n/a" if metrics.interest_coverage in [math.inf, -math.inf] else f"{metrics.interest_coverage:.2f}"
    dscr_line = "n/a" if metrics.dscr in [math.inf, -math.inf] else f"{metrics.dscr:.2f}"

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

    print("\nNOTE: This is a simplified model using public data via FMP; "
          "always cross-check with full financial statements & disclosures.")
    print("=" * 70)


# ---------- OpenAI credit memo ----------

def generate_credit_memo_with_llm(metrics: CreditMetrics, model: str = "gpt-4o-mini") -> str:
    """
    Use OpenAI Chat Completions API to turn numeric metrics into a structured credit memo.
    Requires OPENAI_API_KEY in the environment.
    """
    client = OpenAI()  # uses OPENAI_API_KEY

    system_prompt = "You are an experienced sell-side credit analyst."
    user_prompt = f"""
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

    messages: List[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(role="user", content=user_prompt),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    return response.choices[0].message.content


# ---------- PDF generation helpers ----------

def _draw_wrapped_text(c: canvas.Canvas, text: str,
                       x: float, y: float,
                       max_width: float,
                       line_height: float,
                       font_name: str = "Helvetica",
                       font_size: int = 10,
                       bottom_margin: float = 40) -> float:
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


def _draw_pdf_section(c: canvas.Canvas, y: float, title: str, lines: List[str], margin: float) -> float:
    """Draw a section with a title and a list of lines."""
    if y < margin:
        c.showPage()
        y = A4[1] - margin

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, title)
    y -= 18
    c.setFont("Helvetica", 10)

    for line in lines:
        if y < margin:
            c.showPage()
            y = A4[1] - margin
            c.setFont("Helvetica", 10)
        c.drawString(margin, y, line)
        y -= 14
    return y


def generate_pdf_report(metrics: CreditMetrics, memo_text: Optional[str], filename: str) -> None:
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

    # Core Financials
    core_financials_lines = [
        f"Revenue:                {human_readable(metrics.revenue)}",
        f"EBITDA:                 {human_readable(metrics.ebitda)}",
        f"EBIT:                   {human_readable(metrics.ebit)}",
        f"Operating Cash Flow:    {human_readable(metrics.operating_cash_flow)}",
        f"Capex:                  {human_readable(metrics.capex)}",
        f"Change in Working Cap.: {human_readable(metrics.change_in_wc)}",
        f"Total Debt:             {human_readable(metrics.total_debt)}",
        f"Interest Expense:       {human_readable(metrics.interest_expense)}",
    ]
    y = _draw_pdf_section(c, y, "1. Core Financials", core_financials_lines, margin)

    # Coverage & ratios
    fcf_debt_line = "n/a" if metrics.fcf_to_debt in [math.inf, -math.inf] else f"{metrics.fcf_to_debt:.2%}"
    d_e_line = "n/a" if metrics.debt_to_ebitda in [math.inf, -math.inf] else f"{metrics.debt_to_ebitda:.2f}x"
    ic_line = "n/a" if metrics.interest_coverage in [math.inf, -math.inf] else f"{metrics.interest_coverage:.2f}x"
    dscr_line = "n/a" if metrics.dscr in [math.inf, -math.inf] else f"{metrics.dscr:.2f}x"

    ratio_lines = [
        f"Free Cash Flow (FCF):   {human_readable(metrics.fcf)}",
        f"FCF / Debt:             {fcf_debt_line}",
        f"Debt / EBITDA:          {d_e_line}",
        f"Interest Coverage:      {ic_line}",
        f"DSCR:                   {dscr_line}",
    ]
    y = _draw_pdf_section(c, y, "2. Cash Flow & Coverage", ratio_lines, margin)

    # Internal view
    score_lines = [
        f"Score (0–20): {metrics.score}",
        f"Risk bucket:  {metrics.rating_bucket}",
    ]
    y = _draw_pdf_section(c, y, "3. Internal Credit View", score_lines, margin)

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

    # Memo
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

    if y < margin:
        c.showPage()
        y = height - margin
    y -= 10
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        margin,
        y,
        "Note: This report is generated automatically using public financial data from FMP. "
        "It should be supplemented with full financial statements and disclosures."
    )

    c.save()


# ---------- CLI entrypoint ----------

def run_analysis(query: str, fmp_api_key: str):
    """Main execution flow."""
    try:
        symbol, name_from_search = resolve_symbol(query, fmp_api_key)
        metrics = fetch_credit_metrics_for_symbol(symbol, fmp_api_key, forced_name=name_from_search)
    except Exception as e:
        print(f"Error resolving or fetching data for '{query}': {e}")
        sys.exit(1)

    print_numeric_report(metrics)

    memo_text = None
    if os.getenv("OPENAI_API_KEY"):
        print("\nGenerating LLM-based credit memo via OpenAI...\n")
        try:
            memo_text = generate_credit_memo_with_llm(metrics)
            print(memo_text)
        except Exception as e:
            print(f"Error generating credit memo with OpenAI: {e}")
            memo_text = f"(Memo generation failed: {e})"
    else:
        print("\nNo OPENAI_API_KEY found in environment; skipping LLM memo in PDF.")

    safe_symbol = metrics.ticker.replace("/", "_")
    filename = f"credit_report_{safe_symbol}.pdf"
    generate_pdf_report(metrics, memo_text, filename)
    print(f"\nPDF report saved as: {filename}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python credit_agent_fmp.py <TICKER_OR_COMPANY_NAME>")
        print("Example: python credit_agent_fmp.py AAPL")
        print("         python credit_agent_fmp.py \"Apple Inc\"")
        sys.exit(1)

    fmp_api_key = os.getenv("FMP_API_KEY")
    if not fmp_api_key:
        print("Error: FMP_API_KEY is not set in the environment.")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).strip()
    run_analysis(query, fmp_api_key)


if __name__ == "__main__":
    main()
