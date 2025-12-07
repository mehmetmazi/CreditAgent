# Credit Analysis Platform - Frontend

A modern, responsive web application for analyzing company creditworthiness using real-time financial data and AI-powered insights.

## Features

- **Smart Search**: Search by company name or ticker symbol
- **Real-Time Data**: Fetches latest financial metrics from Financial Modeling Prep (FMP) API
- **Credit Scoring**: Comprehensive 20-point creditworthiness assessment
- **AI Analysis**: Professional credit memos generated using GPT-4
- **PDF Reports**: Download beautifully formatted credit reports
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Screenshots

### Homepage
Clean, intuitive search interface with gradient design

### Credit Report
Comprehensive display of:
- Credit score and risk rating
- Core financial metrics (Revenue, EBITDA, FCF, etc.)
- Credit ratios (Debt/EBITDA, Interest Coverage, DSCR, FCF/Debt)
- AI-generated professional credit analysis
- One-click PDF download

## Installation

1. **Ensure you have the required environment variables set:**

```bash
export FMP_API_KEY="your_fmp_api_key"
export OPENAI_API_KEY="your_openai_api_key"  # Optional, for AI memos
```

2. **Install dependencies** (if not already installed):

```bash
pip install flask requests pandas openai reportlab
```

## Running the Application

### Option 1: Using the new frontend (recommended)

```bash
python app.py
```

### Option 2: Using the basic frontend

```bash
python credit_agent_frontend.py
```

Then navigate to: http://127.0.0.1:5000

## Usage

1. **Enter a company identifier**:
   - Ticker symbol: `AAPL`, `MSFT`, `TSLA`
   - Company name: `Apple Inc`, `Microsoft`, `Tesla`

2. **View the analysis**:
   - Credit score (0-20 scale)
   - Risk rating (Low/Moderate/Elevated/High)
   - Financial metrics and ratios
   - AI-generated credit memo

3. **Download PDF report**:
   - Click "Download PDF Report" button
   - Professional PDF with all metrics and analysis

## API Endpoints

### Web Interface
- `GET /` - Homepage with search form
- `GET /report?query=AAPL` - Display credit report
- `GET /download-pdf?symbol=AAPL` - Download PDF report

### JSON API
- `GET /api/search?q=Apple` - Search for company, returns symbol and name
- `GET /health` - Health check endpoint

## Technical Stack

- **Backend**: Flask (Python)
- **Data Source**: Financial Modeling Prep API
- **AI Analysis**: OpenAI GPT-4
- **PDF Generation**: ReportLab
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## Credit Scoring Methodology

The platform uses a 20-point scoring system based on four key metrics:

1. **Debt / EBITDA** (5 points max)
   - ≤2x: 5 points (Strong)
   - 2-3x: 4 points
   - 3-4x: 3 points
   - 4-5x: 2 points
   - >5x: 1 point

2. **Interest Coverage** (5 points max)
   - >8x: 5 points
   - 5-8x: 4 points
   - 3-5x: 3 points
   - 1.5-3x: 2 points
   - <1.5x: 1 point

3. **DSCR** (5 points max)
   - >1.8: 5 points
   - 1.4-1.8: 4 points
   - 1.1-1.4: 3 points
   - 1.0-1.1: 2 points
   - <1.0: 1 point

4. **FCF / Debt** (5 points max)
   - >25%: 5 points
   - 15-25%: 4 points
   - 8-15%: 3 points
   - 3-8%: 2 points
   - <3%: 1 point

### Risk Ratings
- **17-20 points**: Low credit risk
- **13-16 points**: Moderate credit risk
- **9-12 points**: Elevated credit risk
- **0-8 points**: High credit risk

## Troubleshooting

### "FMP_API_KEY not set in environment"
Set your FMP API key:
```bash
export FMP_API_KEY="your_key_here"
```

### "No OPENAI_API_KEY found"
AI memos are optional. To enable them:
```bash
export OPENAI_API_KEY="your_key_here"
```

### "Could not fetch credit metrics"
- Verify the ticker symbol is valid
- Check that the company is US-listed
- Ensure your FMP API key has sufficient quota

### Port already in use
Change the port in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

## Development

### Project Structure
```
CreditAgent/
├── app.py                      # New Flask frontend (recommended)
├── credit_agent_frontend.py    # Basic Flask frontend
├── credit_agent_fmp.py         # Core credit analysis logic
├── credit_agent.py             # Legacy version
└── FRONTEND_README.md          # This file
```

### Customization

**Change color scheme**: Edit the CSS gradient in `app.py`:
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

**Modify scoring thresholds**: Edit the `compute_score()` function in `credit_agent_fmp.py`

**Add new metrics**: Extend the `CreditMetrics` dataclass and update the display templates

## Performance Notes

- Initial load: ~2-3 seconds (includes FMP API calls)
- With AI memo: +5-10 seconds (OpenAI API call)
- PDF generation: <1 second

## Security Considerations

- Never commit API keys to version control
- Use environment variables for all secrets
- Consider adding rate limiting for production use
- Add authentication for internal deployment

## License

See LICENSE file in the root directory

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the FMP API documentation
3. Check your API key quotas
4. Open an issue in the repository

## Future Enhancements

Potential improvements:
- Historical trend analysis
- Peer comparison
- Custom scoring models
- Export to Excel
- Email report delivery
- Multi-company batch analysis
- Real-time notifications
