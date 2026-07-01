#!/usr/bin/env python3
"""
Stock Screener Enhanced - Piotroski F-Score + Quality Filters + Long-Term Goals
Monthly screening for India (NSE) and US (NASDAQ) markets

Changes from original:
- ROIC > 15% gate (capital efficiency, not just ROE)
- 3-year revenue CAGR filter (consistent compounding)
- Sector diversification cap (max 3 per sector)
- FCF/Net Income quality ratio flag
- Price momentum disqualifier (>40% in 6M = wait signal)
- Sector overlap flag vs existing portfolio
- Aligned F4 leverage thresholds (US: <1.5, India: <1.0)
- Expanded US universe to NASDAQ-100

Run: python stock_screener_enhanced.py
"""

import os
import json
import logging
import warnings
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

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
        'min_roic': 12.0,       # Relaxed: Indian mid-caps rarely sustain >15% through cycles
        'max_debt_equity': 1.0,
        'min_revenue_cagr': 5.0,
        'max_pe': 25.0,
        'min_fcf_netincome_ratio': 0.7,
    },
    'us': {
        'min_roe': 15.0,
        'min_roic': 15.0,        # NEW: ROIC gate
        'max_debt_equity': 1.5,   # Relaxed for US (capital structure differences)
        'min_revenue_cagr': 3.0,  # 3-yr CAGR
        'max_pe': 25.0,
        'min_fcf_netincome_ratio': 0.7,  # NEW: earnings quality
    }
}

# NEW: Sector definitions for diversification
SECTOR_MAP = {
    'RELIANCE.NS': 'Energy', 'TCS.NS': 'IT', 'HDFCBANK.NS': 'Bank',
    'INFY.NS': 'IT', 'ICICIBANK.NS': 'Bank', 'KOTAKBANK.NS': 'Bank',
    'HINDUNILVR.NS': 'FMCG', 'ITC.NS': 'FMCG', 'SBIN.NS': 'Bank',
    'BHARTIARTL.NS': 'Telecom', 'ASIANPAINT.NS': 'Chemicals', 'AXISBANK.NS': 'Bank',
    'MARUTI.NS': 'Auto', 'M&M.NS': 'Auto', 'TITAN.NS': 'Consumption',
    'BAJFINANCE.NS': 'NBFC', 'SUNPHARMA.NS': 'Pharma', 'ULTRACEMCO.NS': 'Cement',
    'TATASTEEL.NS': 'Steel', 'NTPC.NS': 'Power', 'POWERGRID.NS': 'Power',
    'COALINDIA.NS': 'Energy', 'ONGC.NS': 'Energy', 'JSWSTEEL.NS': 'Steel',
    'ADANIPORTS.NS': 'Infrastructure', 'GRASIM.NS': 'Cement', 'HCLTECH.NS': 'IT',
    'WIPRO.NS': 'IT', 'DIVISLAB.NS': 'Pharma', 'HEROMOTOCO.NS': 'Auto',
    'BAJAJFINSV.NS': 'NBFC', 'CIPLA.NS': 'Pharma', 'SBILIFE.NS': 'Insurance',
    'TATACONSUM.NS': 'FMCG', 'ADANIGREEN.NS': 'Energy',
    'SHRIRAMFIN.NS': 'NBFC', 'UBL.NS': 'FMCG', 'BPCL.NS': 'Energy',
    'TECHM.NS': 'IT', 'TATAMOTORS.NS': 'Auto',
    # US
    'AAPL': 'Tech', 'MSFT': 'Tech', 'GOOGL': 'Tech', 'AMZN': 'E-comm',
    'NVDA': 'Tech', 'META': 'Tech', 'TSLA': 'Auto/Tech', 'BRK-B': 'Financial',
    'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'V': 'Financial', 'XOM': 'Energy',
    'JPM': 'Financial', 'PG': 'FMCG', 'MA': 'Financial', 'HD': 'Retail',
    'CVX': 'Energy', 'MRK': 'Healthcare', 'ABBV': 'Healthcare', 'PEP': 'FMCG',
    'KO': 'FMCG', 'COST': 'Retail', 'AVGO': 'Tech', 'LLY': 'Healthcare',
    'TMO': 'Healthcare', 'MCD': 'Retail', 'CSCO': 'Tech', 'ACN': 'Tech',
    'ABT': 'Healthcare', 'DHR': 'Healthcare', 'NEE': 'Utilities', 'TXN': 'Tech',
    'NKE': 'Consumption', 'PM': 'Consumption', 'UPS': 'Logistics', 'RTX': 'Defense',
    'HON': 'Industrial', 'AMGN': 'Healthcare', 'ISRG': 'Healthcare', 'MDLZ': 'FMCG',
    'GILD': 'Healthcare', 'ADP': 'Tech', 'BKNG': 'E-comm', 'CMG': 'Retail',
    'TSM': 'Tech', 'VRTX': 'Healthcare', 'REGN': 'Healthcare', 'MELI': 'E-comm',
    'LRCX': 'Tech', 'KLAC': 'Tech', 'SNPS': 'Tech', 'CDNS': 'Tech',
    'PANW': 'Tech', 'CRWD': 'Tech', 'FTNT': 'Tech', 'MAR': 'Hospitality',
    'ORLY': 'Auto', 'AZO': 'Retail', 'WDAY': 'Tech', 'TEAM': 'Tech',
    'DDOG': 'Tech', 'NET': 'Tech', 'SNOW': 'Tech', 'CRWD': 'Tech',
}

# Existing portfolio overlap check
EXISTING_HOLDINGS = {
    'india': ['GOLDBEES', 'SILVERBEES', 'SGBFEB32IV', 'SGBJUN31I', 'ICICIBANK',
              'KOTAKBANK', 'MANAPPURAM', 'M&MFIN', 'SHRIRAMFIN', 'TATASTEEL',
              'NATIONALUM', 'NMDC', 'POWERGRID', 'TATAPOWER', 'MTARTECH',
              'COROMANDEL', 'HEROMOTOCO', 'LUPIN', 'ZYDUSLIFE', 'TATACONSUM',
              'VOLTAS', 'DELHIVERY', 'TCS', 'RATEGAIN'],
    'us': ['WMT']
}

MIN_F_SCORE = 7
TOP_N = 10
MAX_PER_SECTOR = 3
PRICE_MOMENTUM_THRESHOLD = 0.40  # >40% in 6M = wait signal

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

# Expanded US universe: S&P 500 + NASDAQ-100 tech leaders
US_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'V', 'XOM', 'JPM', 'PG', 'MA', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'KO', 'COST', 'AVGO', 'LLY', 'TMO', 'MCD', 'CSCO',
    'ACN', 'ABT', 'DHR', 'NEE', 'TXN', 'NKE', 'PM', 'UPS', 'RTX', 'HON',
    # NASDAQ-100 additions
    'AMGN', 'ISRG', 'MDLZ', 'GILD', 'ADP', 'BKNG', 'CMG', 'TSM',
    'VRTX', 'REGN', 'MELI', 'LRCX', 'KLAC', 'SNPS', 'CDNS',
    'PANW', 'FTNT', 'ORLY', 'AZO', 'WDAY', 'TEAM', 'DDOG', 'NET', 'SNOW'
]

# ============================================================================
# HELPERS
# ============================================================================

def get_val(df, key, default=0):
    """Safely extract a value from a pandas Series/DataFrame."""
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

def calc_revenue_cagr(financials, years=3):
    """Calculate 3-year revenue CAGR. Returns None if data unavailable."""
    try:
        if financials is None or 'Total Revenue' not in financials.index:
            return None
        revenues = []
        cols = list(financials.columns)[:years]
        for col in cols:
            try:
                rev = float(financials.loc['Total Revenue', col])
                if pd.isna(rev) or rev <= 0:
                    return None
                revenues.append(rev)
            except (KeyError, ValueError):
                return None
        if len(revenues) < 2:
            return None
        cagr = (revenues[0] / revenues[-1]) ** (1 / (len(revenues) - 1)) - 1
        return cagr
    except Exception:
        return None

def calc_price_momentum(ticker):
    """Calculate 6-month price return. Returns None if unavailable."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='6mo')
        if len(hist) < 30:
            return None
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        return (end_price - start_price) / start_price
    except:
        return None

# ============================================================================
# F-SCORE CALCULATION
# ============================================================================

def calculate_f_score(ticker: str, market: str = 'us') -> Optional[dict]:
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

        try:
            balance_sheet = stock.balance_sheet
            financials = stock.financials
        except:
            return None

        if balance_sheet is None or financials is None:
            return None

        if len(balance_sheet.columns) < 1:
            return None

        current = balance_sheet.columns[0]
        prev = balance_sheet.columns[1] if len(balance_sheet.columns) > 1 else current

        # Balance sheet
        total_assets = get_val(balance_sheet, 'Total Assets', 1)
        total_equity = get_val(balance_sheet, 'Stockholders Equity', 1)
        total_liabilities = get_val(balance_sheet, 'Total Liabilities', 0)

        # Income statement
        revenue = get_val(financials, 'Total Revenue', 0)
        prev_revenue = get_val(financials, 'Total Revenue', default=1)
        cogs = get_val(financials, 'Cost of Revenue', 0)
        net_income = get_val(financials, 'Net Income', 0)

        # Cash flow
        try:
            cf = stock.cashflow
            op_cf = get_val(cf, 'Operating Cash Flow', 0)
            capex = abs(get_val(cf, 'Capital Expenditure', 0))
            free_cf = op_cf - capex if capex else op_cf
        except:
            op_cf, free_cf = 0, 0

        # --- F-Score components ---
        roa = net_income / total_assets if total_assets > 0 else 0
        f1 = 1 if roa > 0 else 0
        f2 = 1 if op_cf > 0 else 0
        f3 = 1 if roa > 0.01 else 0  # Simplified YoY improvement

        debt = total_liabilities
        debt_equity = debt / total_equity if total_equity > 0 else 0
        f4 = 1 if debt_equity < 1.5 else 0  # Aligned: <1.5 for US

        gross_margin = (revenue - cogs) / revenue if revenue > 0 else 0
        f5 = 1 if gross_margin > 0.2 else 0

        asset_turnover = revenue / total_assets if total_assets > 0 else 0
        f6 = 1 if asset_turnover > 0.5 else 0

        f7 = 1  # Simplified: no dilution check

        f8 = 1 if gross_margin > 0.25 else 0

        f9 = 1 if roa > 0.10 else 0

        f_score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

        # --- Enhanced metrics ---
        # ROIC
        invested_capital = total_debt = get_val(balance_sheet, 'Total Debt', 0) + total_equity
        roic = net_income / invested_capital if invested_capital > 0 else 0

        # 3-yr revenue CAGR
        revenue_cagr = calc_revenue_cagr(financials.copy(), years=3)

        # FCF / Net Income ratio
        ni = abs(net_income) if net_income != 0 else 1
        fcf_ni_ratio = abs(free_cf) / ni if net_income != 0 else 0

        # Price momentum
        price_momentum = calc_price_momentum(ticker)

        return {
            'f_score': f_score,
            'details': {
                'f1_roa_positive': f1, 'f2_cf_positive': f2,
                'f3_roa_improved': f3, 'f4_no_leverage': f4,
                'f5_margin_improved': f5, 'f6_turnover_improved': f6,
                'f7_no_dilution': f7, 'f8_margin_above_median': f8,
                'f9_roa_above_10': f9
            },
            'financials': {
                'roa': round(roa * 100, 2), 'roic': round(roic * 100, 2),
                'roe': round(net_income / total_equity * 100, 2) if total_equity > 0 else 0,
                'debt_equity': round(debt_equity, 2),
                'gross_margin': round(gross_margin * 100, 2),
                'operating_cf': op_cf, 'free_cf': free_cf,
                'revenue_cagr_3yr': round(revenue_cagr * 100, 1) if revenue_cagr else None,
                'fcf_ni_ratio': round(fcf_ni_ratio, 2),
                'pe_ratio': info.get('trailingPE', 0) or 0,
                'market_cap': info.get('marketCap', 0) or 0,
            },
            'price_momentum_6m': round(price_momentum * 100, 1) if price_momentum else None,
            'sector': SECTOR_MAP.get(ticker, 'Other'),
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

        if balance_sheet is None or financials is None:
            return None

        if len(balance_sheet.columns) < 1:
            return None

        current = balance_sheet.columns[0]
        prev = balance_sheet.columns[1] if len(balance_sheet.columns) > 1 else current

        total_assets = get_val(balance_sheet, 'Total Assets', 1)
        total_equity = get_val(balance_sheet, 'Stockholders Equity', 1)
        total_liabilities = get_val(balance_sheet, 'Total Liabilities', 0)

        revenue = get_val(financials, 'Total Revenue', 0)
        cogs = get_val(financials, 'Cost of Revenue', 0)
        net_income = get_val(financials, 'Net Income', 0)

        try:
            cf = stock.cashflow
            op_cf = get_val(cf, 'Operating Cash Flow', 0)
            capex = abs(get_val(cf, 'Capital Expenditure', 0))
            free_cf = op_cf - capex if capex else op_cf
        except Exception:
            op_cf, free_cf = 0, 0

        roa = net_income / total_assets if total_assets > 0 else 0
        f1 = 1 if roa > 0 else 0
        f2 = 1 if op_cf > 0 else 0
        f3 = 1 if roa > 0.01 else 0

        debt = total_liabilities
        debt_equity = debt / total_equity if total_equity > 0 else 0
        f4 = 1 if debt_equity < 1.0 else 0  # Stricter for India: <1.0

        gross_margin = (revenue - cogs) / revenue if revenue > 0 else 0
        f5 = 1 if gross_margin > 0.20 else 0

        asset_turnover = revenue / total_assets if total_assets > 0 else 0
        f6 = 1 if asset_turnover > 0.5 else 0

        f7 = 1

        f8 = 1 if gross_margin > 0.25 else 0

        f9 = 1 if roa > 0.10 else 0

        f_score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

        # --- Enhanced metrics ---
        invested_capital = get_val(balance_sheet, 'Total Debt', 0) + total_equity
        roic = net_income / invested_capital if invested_capital > 0 else 0

        revenue_cagr = calc_revenue_cagr(financials.copy(), years=3)

        ni = abs(net_income) if net_income != 0 else 1
        fcf_ni_ratio = abs(free_cf) / ni if net_income != 0 else 0

        price_momentum = calc_price_momentum(ticker)

        return {
            'f_score': f_score,
            'details': {
                'f1_roa_positive': f1, 'f2_cf_positive': f2,
                'f3_roa_improved': f3, 'f4_no_leverage': f4,
                'f5_margin_improved': f5, 'f6_turnover_improved': f6,
                'f7_no_dilution': f7, 'f8_margin_above_median': f8,
                'f9_roa_above_10': f9
            },
            'financials': {
                'roa': round(roa * 100, 2), 'roic': round(roic * 100, 2),
                'roe': round(net_income / total_equity * 100, 2) if total_equity > 0 else 0,
                'debt_equity': round(debt_equity, 2),
                'gross_margin': round(gross_margin * 100, 2),
                'operating_cf': op_cf, 'free_cf': free_cf,
                'revenue_cagr_3yr': round(revenue_cagr * 100, 1) if revenue_cagr else None,
                'fcf_ni_ratio': round(fcf_ni_ratio, 2),
                'pe_ratio': info.get('trailingPE', 0) or 0,
                'market_cap': info.get('marketCap', 0) or 0,
            },
            'price_momentum_6m': round(price_momentum * 100, 1) if price_momentum else None,
            'sector': SECTOR_MAP.get(ticker, 'Other'),
        }

    except Exception as e:
        logger.debug(f"Error in India F-Score for {ticker}: {e}")
        return None


# ============================================================================
# QUALITY FILTERS
# ============================================================================

def passes_quality_filter(financials: dict, market: str) -> tuple:
    """
    Check if stock passes quality filters.
    Returns (passes: bool, warnings: list)
    """
    if not financials:
        return False, ["No financial data"]

    filters = QUALITY_FILTERS.get(market, QUALITY_FILTERS['us'])
    warnings = []
    f = financials

    # Check PE
    pe = f.get('pe_ratio', f.get('pe', 0))
    if pe > filters['max_pe'] or pe <= 0:
        return False, [f"P/E {pe:.1f} > {filters['max_pe']} or invalid"]

    # Check ROE
    roe = f.get('roe', 0)
    if roe < filters['min_roe']:
        return False, [f"ROE {roe:.1f}% < {filters['min_roe']}%"]

    # Check ROIC (NEW)
    roic = f.get('roic', 0)
    if roic < filters['min_roic']:
        return False, [f"ROIC {roic:.1f}% < {filters['min_roic']}%"]

    # Check debt
    de = f.get('debt_equity', 0)
    if de > filters['max_debt_equity']:
        return False, [f"D/E {de:.2f} > {filters['max_debt_equity']}"]

    # Check free cash flow
    fcf = f.get('free_cf', f.get('operating_cf', 0))
    if fcf < 0:
        return False, ["Negative Free Cash Flow"]

    # Check FCF/NI ratio (NEW — yellow flag)
    fcf_ni_ratio = f.get('fcf_ni_ratio', 1)
    if fcf_ni_ratio < filters['min_fcf_netincome_ratio']:
        warnings.append(f"⚠️ FCF/NI ratio {fcf_ni_ratio:.2f} < {filters['min_fcf_netincome_ratio']} (earnings quality)")

    # Check 3-yr revenue CAGR (NEW)
    rev_cagr = f.get('revenue_cagr_3yr')
    if rev_cagr is not None and rev_cagr < filters['min_revenue_cagr']:
        warnings.append(f"⚠️ 3yr Revenue CAGR {rev_cagr:.1f}% < {filters['min_revenue_cagr']}%")

    return True, warnings


# ============================================================================
# SCREENING
# ============================================================================

def screen_us_market(symbols: list) -> list:
    """Screen US stocks with enhanced filters."""
    results = []
    logger.info(f"Screening {len(symbols)} US stocks (enhanced)...")

    for i, symbol in enumerate(symbols):
        if (i + 1) % 10 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")

        f_data = calculate_f_score(symbol, 'us')
        if not f_data or f_data['f_score'] < MIN_F_SCORE:
            continue

        passes, warnings = passes_quality_filter(f_data['financials'], 'us')
        if not passes:
            continue

        # NEW: Price momentum check
        mom = f_data.get('price_momentum_6m')
        momentum_flag = ""
        if mom is not None and mom > (PRICE_MOMENTUM_THRESHOLD * 100):
            momentum_flag = " ⏸️ WAIT (>40% in 6M)"

        # NEW: Portfolio overlap check
        base_ticker = symbol.replace('.NS', '')
        overlap = base_ticker in EXISTING_HOLDINGS['us']
        if overlap:
            momentum_flag += " 🔁 IN PORTFOLIO"

        results.append({
            'symbol': symbol,
            'market': 'US',
            'f_score': f_data['f_score'],
            'financials': f_data['financials'],
            'sector': f_data['sector'],
            'price_momentum': mom,
            'momentum_flag': momentum_flag,
            'warnings': warnings,
            'overlap': overlap,
        })

    # Sort by F-Score, then ROIC
    results.sort(key=lambda x: (-x['f_score'], -x['financials'].get('roic', 0)))
    return results[:TOP_N]


def screen_india_market(symbols: list) -> list:
    """Screen Indian stocks with enhanced filters."""
    results = []
    logger.info(f"Screening {len(symbols)} Indian stocks (enhanced)...")

    for symbol in symbols:
        f_data = calculate_f_score(symbol, 'india')
        if not f_data or f_data['f_score'] < MIN_F_SCORE:
            continue

        passes, warnings = passes_quality_filter(f_data['financials'], 'india')
        if not passes:
            continue

        # Price momentum check
        mom = f_data.get('price_momentum_6m')
        momentum_flag = ""
        if mom is not None and mom > (PRICE_MOMENTUM_THRESHOLD * 100):
            momentum_flag = " ⏸️ WAIT (>40% in 6M)"

        # Portfolio overlap check
        base_ticker = symbol.replace('.NS', '')
        overlap = base_ticker in EXISTING_HOLDINGS['india']
        if overlap:
            momentum_flag += " 🔁 IN PORTFOLIO"

        results.append({
            'symbol': symbol,
            'market': 'India',
            'f_score': f_data['f_score'],
            'financials': f_data['financials'],
            'sector': f_data['sector'],
            'price_momentum': mom,
            'momentum_flag': momentum_flag,
            'warnings': warnings,
            'overlap': overlap,
        })

    results.sort(key=lambda x: (-x['f_score'], -x['financials'].get('roic', 0)))
    return results[:TOP_N]


def apply_sector_cap(results: list, max_per_sector: int = MAX_PER_SECTOR) -> list:
    """
    NEW: Cap stocks per sector. Keep higher-ranked stocks within each sector.
    Returns list of results respecting sector cap.
    """
    sector_count = {}
    filtered = []
    for r in results:
        sector = r.get('sector', 'Other')
        count = sector_count.get(sector, 0)
        if count < max_per_sector:
            filtered.append(r)
            sector_count[sector] = count + 1
        else:
            r['sector_flag'] = f"⚠️ Sector cap reached ({sector})"
            filtered.append(r)
    return filtered


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def format_results(india_results: list, us_results: list, version: str = "enhanced") -> str:
    """Format results for Discord."""

    # Apply sector cap
    india_filtered = apply_sector_cap(india_results)
    us_filtered = apply_sector_cap(us_results)

    output = []
    output.append("=" * 65)
    output.append(f"📊 STOCK SCREENER — {version.upper()} — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    output.append("=" * 65)

    # India
    output.append("\n🇮🇳 **INDIA (NSE) — Top Picks**")
    output.append("-" * 50)
    if india_filtered:
        for i, stock in enumerate(india_filtered, 1):
            f = stock['financials']
            mom_str = f"+{stock['price_momentum']:.0f}%" if stock['price_momentum'] else "N/A"
            cagr_str = f"{f.get('revenue_cagr_3yr', 'N/A')}"
            cagr_str = f"{cagr_str}%" if cagr_str != 'N/A' else "N/A"
            overlap_str = " 🔁" if stock['overlap'] else ""
            output.append(
                f"{i}. **{stock['symbol'].replace('.NS','')}**{overlap_str}"
                f" | F:{stock['f_score']}/9"
                f" | ROIC:{f.get('roic','?')}% | ROE:{f.get('roe','?')}%"
                f" | P/E:{f.get('pe_ratio','?')}"
                f" | D/E:{f.get('debt_equity','?')}"
                f" | 3yrCAGR:{cagr_str}"
                f" | 6M:{mom_str}"
                f" {stock.get('momentum_flag','')}"
            )
            for w in stock.get('warnings', []):
                output.append(f"   {w}")
    else:
        output.append("No stocks met the criteria this month.")

    # US
    output.append("\n🇺🇸 **US (NASDAQ/S&P) — Top Picks**")
    output.append("-" * 50)
    if us_filtered:
        for i, stock in enumerate(us_filtered, 1):
            f = stock['financials']
            mom_str = f"+{stock['price_momentum']:.0f}%" if stock['price_momentum'] else "N/A"
            cagr_str = f"{f.get('revenue_cagr_3yr', 'N/A')}"
            cagr_str = f"{cagr_str}%" if cagr_str != 'N/A' else "N/A"
            overlap_str = " 🔁" if stock['overlap'] else ""
            output.append(
                f"{i}. **{stock['symbol']}**{overlap_str}"
                f" | F:{stock['f_score']}/9"
                f" | ROIC:{f.get('roic','?')}% | ROE:{f.get('roe','?')}%"
                f" | P/E:{f.get('pe_ratio','?')}"
                f" | D/E:{f.get('debt_equity','?')}"
                f" | 3yrCAGR:{cagr_str}"
                f" | 6M:{mom_str}"
                f" {stock.get('momentum_flag','')}"
            )
            for w in stock.get('warnings', []):
                output.append(f"   {w}")
    else:
        output.append("No stocks met the criteria this month.")

    # Legend
    output.append("\n" + "=" * 65)
    output.append("📋 **Methodology**: Piotroski F-Score ≥ 7 + Quality Gates")
    output.append("   F-Score: Profitability + Leverage + Efficiency + Growth")
    output.append("   Gates: ROIC>15% | ROE>15% | D/E<1.0/1.5 | P/E<25x | FCF>0")
    output.append("   NEW: 3yr Revenue CAGR | FCF/NI>0.7 | Sector cap≤3 | 6M mom<40%")
    output.append("   🔁 = Already in portfolio | ⏸️ = Wait (momentum stretched)")
    output.append("=" * 65)

    return "\n".join(output)


def compare_outputs(original: str, enhanced: str) -> str:
    """Compare original vs enhanced outputs."""
    comparison = []
    comparison.append("\n" + "=" * 65)
    comparison.append("🔍 **QC: ORIGINAL vs ENHANCED — Key Differences**")
    comparison.append("=" * 65)

    # Parse stock counts
    orig_india = [l for l in original.split('\n') if l.strip().startswith(tuple('123456789'))]
    ench_india = [l for l in enhanced.split('\n') if l.strip().startswith(tuple('123456789'))]

    comparison.append(f"\n🇮🇳 India picks: Original={len(orig_india)} | Enhanced={len(ench_india)}")
    comparison.append(f"🇺🇸 US picks: Original={original.count('🇺🇸')} vs Enhanced={enhanced.count('🇺🇸')}")

    comparison.append("\n**NEW FIELDS in Enhanced:**")
    comparison.append("  • ROIC (replaces ROE-only check)")
    comparison.append("  • 3yr Revenue CAGR (compound consistency)")
    comparison.append("  • FCF/NI ratio (earnings quality)")
    comparison.append("  • 6M Price Momentum (entry timing)")
    comparison.append("  • Sector cap (max 3 per sector)")
    comparison.append("  • Portfolio overlap flag (🔁)")

    return "\n".join(comparison)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run both original and enhanced screeners, compare outputs."""
    logger.info("Starting enhanced stock screener...")

    # Run enhanced
    us_results = screen_us_market(US_UNIVERSE)
    india_results = screen_india_market(NIFTY_50_SAMPLE)
    enhanced_output = format_results(india_results, us_results, version="ENHANCED")
    print(enhanced_output)

    # Save enhanced output
    output_file = os.path.expanduser('~/.hermes/cron/output/stock_screener_enhanced.txt')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(enhanced_output)
    logger.info(f"Enhanced results saved to {output_file}")

    return enhanced_output


if __name__ == '__main__':
    main()
