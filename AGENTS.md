# Agents Context

## Project Overview
Monthly stock screener using Piotroski F-Score. India (NSE) + US (NASDAQ).

## Key Files
- `stock_screener.py` — single entry point, everything runs from here
- `requirements.txt` — pinned deps (nsepy, yfinance, pandas)

## How It Works
1. Fetch NSE India stocks via nsepy (backup: yfinance ADR data)
2. Fetch NASDAQ stocks via yfinance
3. Calculate Piotroski F-Score (9 criteria, 0–9 scale)
4. Apply quality filters: ROE > 15%, D/E < 1.0, P/E < 25x, FCF positive
5. Output ranked results to stdout

## Cron Context
- Runs monthly via cron: `0 9 1 * *`
- Hermes cron job ID: `1af40ba68431`
- Delivers output to origin (current chat)
- If nsepy fails silently, falls back to yfinance — check logs if India data looks wrong

## Data Limitations
- India F-Score uses simplified metrics (free data access is limited)
- For full accuracy: integrate Kite API (Zerodha)
- FCF approximated as Operating Cash Flow − CapEx

## Enhancement Backlog
1. Kite API integration for Indian market data
2. 5-year revenue CAGR filter
3. Sector diversification
4. Dividend yield filter

## Conventions
- Outputs in Markdown with emoji flags (🇮🇳 / 🇺🇸)
- All numbers in standard format (not INR lakh/crore)
- No API keys needed (nsepy, yfinance are free)
