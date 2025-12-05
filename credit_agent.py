import sys
import math
from dataclasses import dataclass
from typing import Optional, Dict

import yfinance as yf
import pandas as pd


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


def safe_get(df: pd.DataFrame, label_candidates, default=0.0):
    """
    Try several possible row labels in a yfinance dataframe.
    """
    if df is None or df.empty:
        return default
    for label in label_candidates:
        if label in df.index:
            value = df.loc[label]
            # Take latest column (most recent year / period)
            if isinstance(value, pd.Series):
                return float(value.iloc[0])
            return float(value)
    return default


def compute_score(metrics: CreditMetrics) -> CreditMetrics:
    """
    Score each metric 0–5 and total.
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


def fetch_credit_metrics(ticker: str) -> CreditMetrics:
    """
    Core 'agent' function:
    - Fetch data
    - Compute FCF and ratios
    - Return CreditMetrics dataclass
    """
    tk = yf.Ticker(ticker)

    # Basic info
    info = tk.info or {}
    company_name = info.get("longName") or info.get("shortName") or ticker

    # Financial statements
    income = tk.income_stmt
    cashflow = tk.cashflow
    balance = tk.balance_sheet

    # Latest fiscal year label (column name) for reporting
    fiscal_year = ""
    for df in [income, cashflow, balance]:
        if df is not None and not df.empty:
            fiscal_year = str(df.columns[0].year) if hasattr(df.columns[0], "year") else str(df.columns[0])
            break

    # Extract key items
    revenue = safe_get(income, ["Total Revenue", "Revenue", "Net Revenue"])
    ebitda = safe_get(income, ["Ebitda", "EBITDA"])
    ebit = safe_get(income, ["Ebit", "EBIT", "Operating Income", "Operating Income or Loss"])
    interest_expense = safe_get(income, ["Interest Expense", "Interest Expense Non Operating"])

    operating_cash_flow = safe_get(cashflow, ["Total Cash From Operating Activities", "Operating Cash Flow"])
    capex = -safe_get(cashflow, ["Capital Expenditures", "Purchase Of Property Plant And Equipment"])  # usually negative
    change_in_wc = safe_get(cashflow, ["Change In Working Capital", "Change In Working Capital"])  # often already sign-correct

    # Debt: try to approximate from balance sheet
    short_term_debt = safe_get(balance, ["Short Long Term Debt", "Short Term Debt"])
    long_term_debt = safe_get(balance, ["Long Term Debt", "Long Term Debt Noncurrent"])
    total_debt = short_term_debt + long_term_debt

    # FCF (unlevered style)
    # FCF = OCF - Capex (capex here already positive)
    if operating_cash_flow == 0 and ebit != 0:
        # fallback: FCF approximation from EBIT
        tax_rate = 0.25
        fcf = ebit * (1 - tax_rate) + (operating_cash_flow) - capex - change_in_wc
    else:
        fcf = operating_cash_flow - capex

    # Ratios
    if total_debt > 0:
        fcf_to_debt = fcf / total_debt
    else:
        fcf_to_debt = math.inf

    if ebitda != 0:
        debt_to_ebitda = total_debt / ebitda
    else:
        debt_to_ebitda = math.inf

    if interest_expense != 0:
        interest_coverage = ebit / abs(interest_expense)
    else:
        interest_coverage = math.inf

    # DSCR ≈ OCF / (interest + current maturities of debt)
    # We'll approximate current maturities as short_term_debt here
    denominator = abs(interest_expense) + short_term_debt
    if denominator > 0:
        dscr = operating_cash_flow / denominator
    else:
        dscr = math.inf

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


def print_report(metrics: CreditMetrics):
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
    print(f"Free Cash Flow (FCF):   {human_readable(metrics.fcf)}")
    print(f"FCF / Debt:             {metrics.fcf_to_debt:.2%}" if metrics.fcf_to_debt not in [math.inf, -math.inf] else "FCF / Debt:             n/a")
    print(f"Debt / EBITDA:          {metrics.debt_to_ebitda:.2f}" if metrics.debt_to_ebitda not in [math.inf, -math.inf] else "Debt / EBITDA:          n/a")
    print(f"Interest Coverage:      {metrics.interest_coverage:.2f}" if metrics.interest_coverage not in [math.inf, -math.inf] else "Interest Coverage:      n/a")
    print(f"DSCR:                   {metrics.dscr:.2f}" if metrics.dscr not in [math.inf, -math.inf] else "DSCR:                   n/a")

    print("\n-- Credit View --")
    print(f"Score (0–20):           {metrics.score}")
    print(f"Risk Bucket:            {metrics.rating_bucket}")

    # Simple textual interpretation
    print("\nInterpretation:")
    if metrics.rating_bucket == "Low credit risk":
        print("• Strong capacity to service debt. Leverage and coverage ratios look healthy.")
    elif metrics.rating_bucket == "Moderate credit risk":
        print("• Reasonable capacity to service debt, but leverage or coverage could tighten in a downturn.")
    elif metrics.rating_bucket == "Elevated credit risk":
        print("• Weakish metrics – the company may struggle under stress or higher rates.")
    else:
        print("• High risk profile – limited cushion to absorb shocks or higher funding costs.")

    print("\nNOTE: This is a simplified model using public data via yfinance; "
          "always cross-check with full financial statements & disclosures.")
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python credit_agent.py <TICKER>")
        print("Example: python credit_agent.py AAPL")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    try:
        metrics = fetch_credit_metrics(ticker)
        print_report(metrics)
    except Exception as e:
        print(f"Error computing credit metrics for {ticker}: {e}")


if __name__ == "__main__":
    main()
