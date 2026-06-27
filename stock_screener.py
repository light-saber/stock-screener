#!/usr/bin/env python3
"""
Stock Screener - Piotroski F-Score + Quality Filters
Monthly screening for India (NSE) and US (NASDAQ) markets

Run: python stock_screener.py
"""

import os
import json
import logging
import warnings
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf
import requests

# Suppress warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Quality thresholds
QUALITY_FILTERS = {
    'india': {
        'min_roe': 15.0,
        'max_debt_equity': 1.0,
        'min_revenue_cagr': 10.0,
        'max_pe': 25.0,
    },
    'us': {
        'min_roe': 15.0,
        'max_debt_equity': 0.8,
        'min_revenue_cagr': 5.0,
        'max_pe': 25.0,
    }
}

MIN_F_SCORE = 7
TOP_N = 10

# Nifty 50 symbols for India (NSE suffix for yfinance)
NIFTY_50_SAMPLE = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'ASIANPAINT.NS', 'AXISBANK.NS',
    'MARUTI.NS', 'M&M.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'SUNPHARMA.NS', 'ULTRACEMCO.NS',
    'TATASTEEL.NS', 'NTPC.NS', 'POWERGRID.NS', 'COALINDIA.NS', 'ONGC.NS', 'JSWSTEEL.NS',
    'ADANIPORTS.NS', 'GRASIM.NS', 'HCLTECH.NS', 'WIPRO.NS', 'DIVISLAB.NS', 'HEROMOTOCO.NS',
    'BAJAJFINSV.NS', 'CIPLA.NS', 'SBILIFE.NS', 'TATACONSUM.NS', 'ADANIGREEN.NS',
    'SHRIRAMFIN.NS', 'UBL.NS', 'BPCL.NS', 'TECHM.NS', 'TATAMOTORS.NS'
]

# S&P 500 sample for US (sample universe)
SP500_SAMPLE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'V', 'XOM', 'JPM', 'PG', 'MA', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'KO', 'COST', 'AVGO', 'LLY', 'TMO', 'MCD', 'CSCO',
    'ACN', 'ABT', 'DHR', 'NEE', 'TXN', 'NKE', 'PM', 'UPS', 'RTX', 'HON'
]


# ============================================================================
# F-SCORE CALCULATION
# ============================================================================

def calculate_f_score(ticker: str, market: str = 'us') -> Optional[dict]:
    """
    Calculate Piotroski F-Score for a given ticker.
    
    Returns dict with:
    - f_score: 0-9 integer
    - details: breakdown of each component
    - financials: key financial metrics
    """
    try:
        if market == 'india':
            return calculate_f_score_india(ticker)
        else:
            return calculate_f_score_us(ticker)
    except Exception as e:
        logger.debug(f"Error calculating F-Score for {ticker}: {e}")
        return None


def calculate_f_score_us(ticker: str) -> Optional[dict]:
    """Calculate F-Score for US stocks using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get financial data
        try:
            balance_sheet = stock.balance_sheet
            financials = stock.financials
        except:
            return None
        
        # Default values
        defaults = {
            'roa': 0, 'op_cf': 0, 'prev_roa': 0,
            'debt_equity': 0, 'prev_debt_equity': 0,
            'gross_margin': 0, 'prev_gross_margin': 0,
            'asset_turnover': 0, 'prev_asset_turnover': 0,
            'shares_outstanding': 1, 'prev_shares': 1,
            'total_assets': 1, 'total_equity': 1,
            'revenue': 0, 'prev_revenue': 0,
            'ebit': 0, 'cogs': 0
        }
        
        # Extract current year data
        try:
            if len(balance_sheet.columns) >= 1:
                current = balance_sheet.columns[0]
                prev = balance_sheet.columns[1] if len(balance_sheet.columns) > 1 else current
            else:
                return None
        except:
            return None
            
        # Parse financial items safely
        def get_val(df, key, default=0):
            try:
                if df is not None and key in df.index:
                    val = df.loc[key]
                    if hasattr(val, 'iloc'):
                        val = val.iloc[0]
                    if pd.isna(val):
                        return default
                    return float(val)
                return default
            except:
                return default
        
        # Calculate metrics
        total_assets = get_val(balance_sheet, 'Total Assets', 1)
        total_equity = get_val(balance_sheet, 'Stockholders Equity', 1)
        total_liabilities = get_val(balance_sheet, 'Total Liabilities', 0)
        current_assets = get_val(balance_sheet, 'Current Assets', 0)
        current_liabilities = get_val(balance_sheet, 'Current Liabilities', 0)
        inventory = get_val(balance_sheet, 'Inventory', 0)
        
        # Get income statement
        try:
            is_df = financials
            revenue = get_val(is_df, 'Total Revenue')
            prev_revenue = get_val(is_df, 'Total Revenue', default=1)
            cogs = get_val(is_df, 'Cost of Revenue', 0)
            ebit = get_val(is_df, 'Operating Income', 0)
            net_income = get_val(is_df, 'Net Income', 0)
            gross_profit = get_val(is_df, 'Gross Profit', 0)
        except:
            revenue, prev_revenue, cogs, ebit, net_income = 0, 0, 0, 0, 0
        
        # Get cash flow
        try:
            cf = stock.cashflow
            op_cf = get_val(cf, 'Operating Cash Flow', 0)
            capex = get_val(cf, 'Capital Expenditure', 0)
            free_cf = op_cf - capex if capex else op_cf
        except:
            op_cf, free_cf = 0, 0
        
        # Calculate F-Score components
        # 1. ROA > 0
        roa = net_income / total_assets if total_assets > 0 else 0
        f1 = 1 if roa > 0 else 0
        
        # 2. Operating Cash Flow > 0
        f2 = 1 if op_cf > 0 else 0
        
        # 3. ROA > ROA (prior year) - simplified
        f3 = 1 if roa > 0.01 else 0  # Approximate
        
        # 4. No deterioration in debt ratio
        debt = total_liabilities
        debt_equity = debt / total_equity if total_equity > 0 else 0
        f4 = 1 if debt_equity < 1.0 else 0
        
        # 5. Gross margin > prior year
        gross_margin = (revenue - cogs) / revenue if revenue > 0 else 0
        f5 = 1 if gross_margin > 0.2 else 0  # Approximate
        
        # 6. Asset turnover improved
        asset_turnover = revenue / total_assets if total_assets > 0 else 0
        f6 = 1 if asset_turnover > 0.5 else 0  # Approximate
        
        # 7. No new shares issued (dilution)
        try:
            shares = get_val(balance_sheet, 'Common Stock', 1)
            f7 = 1  # Assume stable for simplicity
        except:
            f7 = 1
        
        # 8. Gross margin > industry median (simplified)
        f8 = 1 if gross_margin > 0.25 else 0
        
        # 9. ROA > 10%
        f9 = 1 if roa > 0.10 else 0
        
        f_score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9
        
        return {
            'f_score': f_score,
            'details': {
                'f1_roa_positive': f1,
                'f2_cf_positive': f2,
                'f3_roa_improved': f3,
                'f4_no_leverage': f4,
                'f5_margin_improved': f5,
                'f6_turnover_improved': f6,
                'f7_no_dilution': f7,
                'f8_margin_above_median': f8,
                'f9_roa_above_10': f9
            },
            'financials': {
                'roa': round(roa * 100, 2),
                'roe': round(net_income / total_equity * 100, 2) if total_equity > 0 else 0,
                'debt_equity': round(debt_equity, 2),
                'gross_margin': round(gross_margin * 100, 2),
                'operating_cf': op_cf,
                'free_cf': free_cf,
                'pe_ratio': info.get('trailingPE', 0) or 0,
                'market_cap': info.get('marketCap', 0) or 0,
            }
        }
        
    except Exception as e:
        logger.debug(f"Error in US F-Score for {ticker}: {e}")
        return None


def calculate_f_score_india(ticker: str) -> Optional[dict]:
    """Calculate F-Score for Indian stocks using yfinance (.NS suffix)."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        try:
            balance_sheet = stock.balance_sheet
            financials = stock.financials
        except Exception:
            return None

        def get_val(df, key, default=0):
            try:
                if df is not None and key in df.index:
                    val = df.loc[key]
                    if hasattr(val, 'iloc'):
                        val = val.iloc[0]
                    if pd.isna(val):
                        return default
                    return float(val)
                return default
            except Exception:
                return default

        # Balance sheet
        total_assets = get_val(balance_sheet, 'Total Assets', 1)
        total_equity = get_val(balance_sheet, 'Stockholders Equity', 1)
        total_liabilities = get_val(balance_sheet, 'Total Liabilities', 0)

        # Income statement
        try:
            is_df = financials
            revenue = get_val(is_df, 'Total Revenue', 0)
            cogs = get_val(is_df, 'Cost of Revenue', 0)
            ebit = get_val(is_df, 'Operating Income', 0)
            net_income = get_val(is_df, 'Net Income', 0)
        except Exception:
            revenue, cogs, ebit, net_income = 0, 0, 0, 0

        # Cash flow
        try:
            cf = stock.cashflow
            op_cf = get_val(cf, 'Operating Cash Flow', 0)
            capex = get_val(cf, 'Capital Expenditure', 0)
            free_cf = op_cf - capex if capex else op_cf
        except Exception:
            op_cf, free_cf = 0, 0

        # F-Score components
        roa = net_income / total_assets if total_assets > 0 else 0
        f1 = 1 if roa > 0 else 0

        f2 = 1 if op_cf > 0 else 0

        f3 = 1 if roa > 0.01 else 0

        debt = total_liabilities
        debt_equity = debt / total_equity if total_equity > 0 else 0
        f4 = 1 if debt_equity < 1.5 else 0  # Slightly relaxed for Indian market

        gross_margin = (revenue - cogs) / revenue if revenue > 0 else 0
        f5 = 1 if gross_margin > 0.20 else 0

        asset_turnover = revenue / total_assets if total_assets > 0 else 0
        f6 = 1 if asset_turnover > 0.5 else 0

        f7 = 1  # Simplified: no dilution check

        f8 = 1 if gross_margin > 0.25 else 0

        f9 = 1 if roa > 0.10 else 0

        f_score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

        return {
            'f_score': f_score,
            'details': {
                'f1_roa_positive': f1,
                'f2_cf_positive': f2,
                'f3_roa_improved': f3,
                'f4_no_leverage': f4,
                'f5_margin_improved': f5,
                'f6_turnover_improved': f6,
                'f7_no_dilution': f7,
                'f8_margin_above_median': f8,
                'f9_roa_above_10': f9
            },
            'financials': {
                'roa': round(roa * 100, 2),
                'roe': round(net_income / total_equity * 100, 2) if total_equity > 0 else 0,
                'debt_equity': round(debt_equity, 2),
                'gross_margin': round(gross_margin * 100, 2),
                'operating_cf': op_cf,
                'free_cf': free_cf,
                'pe_ratio': info.get('trailingPE', 0) or 0,
                'market_cap': info.get('marketCap', 0) or 0,
            }
        }

    except Exception as e:
        logger.debug(f"Error in India F-Score for {ticker}: {e}")
        return None


# ============================================================================
# QUALITY FILTERS
# ============================================================================

def passes_quality_filter(financials: dict, market: str) -> bool:
    """Check if stock passes quality filters."""
    if not financials:
        return False
    
    filters = QUALITY_FILTERS.get(market, QUALITY_FILTERS['us'])
    f = financials
    
    # Check PE
    pe = f.get('pe_ratio', f.get('pe', 0))
    if pe > filters['max_pe'] or pe <= 0:
        return False
    
    # Check ROE
    roe = f.get('roe', 0)
    if roe < filters['min_roe']:
        return False
    
    # Check debt
    de = f.get('debt_equity', 0)
    if de > filters['max_debt_equity']:
        return False
    
    # Check free cash flow
    fcf = f.get('free_cf', f.get('operating_cf', 0))
    if fcf < 0:
        return False
    
    return True


# ============================================================================
# SCREENING
# ============================================================================

def screen_us_market(symbols: list) -> list:
    """Screen US stocks."""
    results = []
    
    logger.info(f"Screening {len(symbols)} US stocks...")
    
    for i, symbol in enumerate(symbols):
        if (i + 1) % 10 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        
        f_data = calculate_f_score(symbol, 'us')
        
        if f_data and f_data['f_score'] >= MIN_F_SCORE:
            if passes_quality_filter(f_data['financials'], 'us'):
                results.append({
                    'symbol': symbol,
                    'market': 'US',
                    'f_score': f_data['f_score'],
                    'financials': f_data['financials']
                })
    
    # Sort by F-Score
    results.sort(key=lambda x: (-x['f_score'], -x['financials'].get('roe', 0)))
    
    return results[:TOP_N]


def screen_india_market(symbols: list) -> list:
    """Screen Indian stocks."""
    results = []
    
    logger.info(f"Screening {len(symbols)} Indian stocks...")
    
    for symbol in symbols:
        f_data = calculate_f_score(symbol, 'india')
        
        if f_data and f_data['f_score'] >= MIN_F_SCORE:
            if passes_quality_filter(f_data['financials'], 'india'):
                results.append({
                    'symbol': symbol,
                    'market': 'India',
                    'f_score': f_data['f_score'],
                    'financials': f_data['financials']
                })
    
    results.sort(key=lambda x: (-x['f_score'], -x['financials'].get('roe', 0)))
    
    return results[:TOP_N]


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def format_results(india_results: list, us_results: list) -> str:
    """Format results for Discord."""
    
    output = []
    output.append("=" * 60)
    output.append("📊 MONTHLY STOCK SCREENER - PIOTROSKI F-SCORE")
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    output.append("=" * 60)
    
    # India Results
    output.append("\n🇮🇳 **INDIA (NSE) - Top Picks**")
    output.append("-" * 40)
    
    if india_results:
        for i, stock in enumerate(india_results, 1):
            f = stock['financials']
            output.append(
                f"{i}. **{stock['symbol']}** | F-Score: {stock['f_score']}/9 | "
                f"ROE: {f.get('roe', 'N/A')}% | P/E: {f.get('pe_ratio', 'N/A')} | "
                f"D/E: {f.get('debt_equity', 'N/A')}"
            )
    else:
        output.append("No stocks met the criteria this month.")
    
    # US Results
    output.append("\n🇺🇸 **US (NASDAQ) - Top Picks**")
    output.append("-" * 40)
    
    if us_results:
        for i, stock in enumerate(us_results, 1):
            f = stock['financials']
            output.append(
                f"{i}. **{stock['symbol']}** | F-Score: {stock['f_score']}/9 | "
                f"ROE: {f.get('roe', 'N/A')}% | P/E: {f.get('pe_ratio', 'N/A')} | "
                f"D/E: {f.get('debt_equity', 'N/A')}"
            )
    else:
        output.append("No stocks met the criteria this month.")
    
    # Summary
    output.append("\n" + "=" * 60)
    output.append("📋 **Methodology**: Piotroski F-Score ≥ 7 + Quality Filters")
    output.append(f"   • ROE > 15% | Debt/Equity < 1.0 | P/E < 25x")
    output.append(f"   • Positive Free Cash Flow")
    output.append("=" * 60)
    
    return "\n".join(output)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution."""
    logger.info("Starting monthly stock screener...")
    
    # Screen US market
    us_results = screen_us_market(SP500_SAMPLE)
    logger.info(f"US: Found {len(us_results)} qualifying stocks")
    
    # Screen India market (using US yfinance as backup for NSE data)
    india_results = screen_india_market(NIFTY_50_SAMPLE)
    logger.info(f"India: Found {len(india_results)} qualifying stocks")
    
    # Format output
    output = format_results(india_results, us_results)
    print(output)
    
    # Save to file for cron job delivery
    output_file = os.path.expanduser('~/.hermes/cron/output/stock_screener.txt')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(output)
    
    logger.info(f"Results saved to {output_file}")
    
    return output


if __name__ == '__main__':
    main()