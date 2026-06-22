# Stock Screener - Piotroski F-Score

A monthly stock screening tool that applies the Piotroski F-Score methodology combined with quality filters to identify quality stocks in both Indian (NSE) and US (NASDAQ) markets.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This screener identifies quality stocks using:

- **Piotroski F-Score** (≥7/9) - Joseph Piotroski's proven 9-point scoring system
- **Quality Filters** - ROE, Debt/Equity, P/E ratio, Free Cash Flow
- **Universal Framework** - Works identically for India and US markets

## Methodology

### Piotroski F-Score (9 Points)

| # | Criteria | Point |
|---|----------|-------|
| 1 | ROA > 0 | +1 |
| 2 | Operating Cash Flow > 0 | +1 |
| 3 | ROA > ROA (prior year) | +1 |
| 4 | No deterioration in Debt/Equity | +1 |
| 5 | Gross Margin > prior year | +1 |
| 6 | Asset Turnover improved | +1 |
| 7 | No new shares issued (dilution) | +1 |
| 8 | Gross Margin > industry median | +1 |
| 9 | ROA > 10% | +1 |

**Buy: F-Score ≥ 7**  
**Avoid: F-Score ≤ 2**

### Quality Filters

| Metric | India | US |
|--------|-------|-----|
| ROE | > 15% | > 15% |
| Debt/Equity | < 1.0 | < 0.8 |
| P/E Ratio | < 25x | < 25x |
| Free Cash Flow | Positive | Positive |

## Installation

```bash
# Clone or download the script
git clone https://github.com/sachinhello/stock-screener.git
cd stock-screener

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the screener
python stock_screener.py
```

### Cron Job (Monthly)

Add to your crontab:

```bash
# Run on 1st of every month at 9 AM
0 9 1 * * /usr/bin/python3 /path/to/stock_screener.py >> /var/log/stock_screener.log 2>&1
```

## Output

The screener outputs:

- Top 10 picks from India (NSE)
- Top 10 picks from US (NASDAQ)
- F-Score breakdown
- Key metrics (ROE, P/E, Debt/Equity)

Example output:

```
============================================================
📊 MONTHLY STOCK SCREENER - PIOTROSKI F-SCORE
Generated: 2026-06-22 10:00:00
============================================================

🇮🇳 **INDIA (NSE) - Top Picks**
----------------------------------------
1. **RELIANCE** | F-Score: 8/9 | ROE: 22% | P/E: 18 | D/E: 0.4
2. **TCS** | F-Score: 8/9 | ROE: 45% | P/E: 22 | D/E: 0.2
...

🇺🇸 **US (NASDAQ) - Top Picks**
----------------------------------------
1. **MSFT** | F-Score: 9/9 | ROE: 35% | P/E: 24 | D/E: 0.3
2. **AAPL** | F-Score: 8/9 | ROE: 150% | P/E: 20 | D/E: 1.7
...

============================================================
📋 **Methodology**: Piotroski F-Score ≥ 7 + Quality Filters
   • ROE > 15% | Debt/Equity < 1.0 | P/E < 25x
   • Positive Free Cash Flow
============================================================
```

## Data Sources

- **India**: NSE via nsepy (backup: yfinance for ADR data)
- **US**: Yahoo Finance (yfinance)

## Limitations

1. F-Score calculation for India uses simplified metrics due to limited free data access
2. For full accuracy with Indian stocks, integrate with Kite API (Zerodha)
3. Free cash flow is approximated from operating cash flow - capex

## Enhancements

To improve accuracy:

1. Add Kite API integration for Indian market data
2. Add 5-year revenue CAGR filter
3. Add sector diversification
4. Add dividend yield filter

## License

MIT License - Feel free to use and modify.

## References

- [Piotroski F-Score - Wikipedia](https://en.wikipedia.org/wiki/Piotroski_F-score)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [nsepy](https://github.com/vgandhi13/nsepy)

---

*Disclaimer: This is for educational purposes only. Not financial advice.*