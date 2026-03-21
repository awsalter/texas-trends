"""
Texas Trends Data Fetcher
Pulls data from FRED, BLS, NY Fed, and Richmond Fed.
Saves JSON files to the /data directory for the dashboard.
Run monthly via GitHub Actions.
"""

import requests
import json
import os
import io
import pandas as pd
from datetime import datetime

FRED_API_KEY = os.environ.get('FRED_API_KEY', '')
BLS_API_KEY  = os.environ.get('BLS_API_KEY', '')

START_DATE  = '2018-01-01'
START_YEAR  = 2018
BASE_DATE   = '2020-01-01'


# ── HELPERS ───────────────────────────────────────────────────────────────────

def fetch_fred(series_id, start=START_DATE):
    """Fetch a monthly series from FRED."""
    r = requests.get(
        'https://api.stlouisfed.org/fred/series/observations',
        params={
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'observation_start': start,
        },
        timeout=30,
    )
    r.raise_for_status()
    obs = [o for o in r.json()['observations'] if o['value'] != '.']
    if not obs:
        return pd.Series(dtype=float)
    dates  = pd.to_datetime([o['date'] for o in obs])
    values = [float(o['value']) for o in obs]
    return pd.Series(values, index=dates)


def fetch_bls(series_ids, start_year=START_YEAR):
    """Fetch monthly series from the BLS public API (v2)."""
    end_year = datetime.now().year
    headers  = {'Content-type': 'application/json'}
    payload  = {
        'seriesid':        series_ids,
        'startyear':       str(start_year),
        'endyear':         str(end_year),
        'annualaverage':   False,
    }
    if BLS_API_KEY:
        payload['registrationkey'] = BLS_API_KEY

    r = requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',
                      json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    result = {}
    for series in r.json().get('Results', {}).get('series', []):
        sid     = series['seriesID']
        records = []
        for item in series.get('data', []):
            period = item.get('period', '')
            value  = item.get('value', '-')
            if value == '-':
                continue
            if period.startswith('M') and period != 'M13':
                month = int(period[1:])
                yr    = int(item['year'])
                records.append((pd.Timestamp(yr, month, 1), float(value)))
            elif period.startswith('Q'):
                quarter = int(period[1:])
                month   = (quarter - 1) * 3 + 1
                yr      = int(item['year'])
                records.append((pd.Timestamp(yr, month, 1), float(value)))
        if records:
            records.sort()
            dates, values = zip(*records)
            result[sid] = pd.Series(list(values), index=list(dates))
    return result


def index_to_base(series, base=BASE_DATE):
    """Reindex a series so base_date = 100."""
    if series.empty:
        return series
    base_val = series.asof(pd.Timestamp(base))
    if pd.isna(base_val) or base_val == 0:
        non_null = series.dropna()
        if non_null.empty:
            return series
        base_val = non_null.iloc[0]
    return (series / base_val * 100).round(3)


def yoy(series, periods=12):
    """Year-over-year % change."""
    return (series.pct_change(periods) * 100).round(3)


def to_list(series):
    return [None if pd.isna(v) else round(float(v), 3) for v in series]


def dates_list(idx):
    return [d.strftime('%Y-%m') for d in idx]


def target_path(idx, base=BASE_DATE, rate=0.02):
    """2% annual growth path indexed to 100 at base_date."""
    base_ts = pd.Timestamp(base)
    return [round(100 * (1 + rate) ** ((d - base_ts).days / 365.25), 3) for d in idx]


# ── PRICE PRESSURES ───────────────────────────────────────────────────────────

def build_price_pressures():
    print("  Fetching price pressures...")

    # Fetch CPI one year before START_DATE so YoY values are valid from START_DATE onward
    cpi_start = str(int(START_DATE[:4]) - 1) + START_DATE[4:]

    # National CPI (BLS CPIAUCSL via FRED)
    us_cpi = fetch_fred('CPIAUCSL', start=cpi_start)

    # DFW CPI (FRED)
    dfw_cpi     = fetch_fred('CUURA316SA0', start=cpi_start)
    # Houston and San Antonio CPI (FRED — BLS API does not carry these series)
    houston_cpi = fetch_fred('CUURA318SA0', start=cpi_start)
    sa_cpi      = fetch_fred('CUURA423SA0', start=cpi_start)

    df = pd.DataFrame({
        'us':      us_cpi,
        'dfw':     dfw_cpi,
        'houston': houston_cpi,
        'sa':      sa_cpi,
    }).ffill().dropna(subset=['us', 'dfw'])

    # Weights: DFW ~42%, Houston ~32%, San Antonio ~15%, rest proxied by DFW average
    # Fill missing SA/Houston with DFW as fallback
    df['houston'] = df['houston'].fillna(df['dfw'])
    df['sa']      = df['sa'].fillna(df['dfw'])
    df['texas']   = df['dfw'] * 0.42 + df['houston'] * 0.35 + df['sa'] * 0.15 + df['dfw'] * 0.08

    # Index to Jan 2020
    us_idx    = index_to_base(df['us'])
    texas_idx = index_to_base(df['texas'])
    dfw_idx   = index_to_base(df['dfw'])
    tgt       = target_path(df.index)

    result = pd.DataFrame({
        'us_index':    us_idx,
        'texas_index': texas_idx,
        'dfw_index':   dfw_idx,
        'us_yoy':      yoy(df['us']),
        'texas_yoy':   yoy(df['texas']),
        'dfw_yoy':     yoy(df['dfw']),
    }).dropna(subset=['us_index'])
    result = result[result.index >= pd.Timestamp(START_DATE)]

    return {
        'dates':       dates_list(result.index),
        'us_index':    to_list(result['us_index']),
        'texas_index': to_list(result['texas_index']),
        'dfw_index':   to_list(result['dfw_index']),
        'target_path': [round(tgt[i], 3) for i in range(len(result))],
        'us_yoy':      to_list(result['us_yoy']),
        'texas_yoy':   to_list(result['texas_yoy']),
        'dfw_yoy':     to_list(result['dfw_yoy']),
    }


# ── MONEY MATTERS ─────────────────────────────────────────────────────────────

def fetch_ny_fed_lw():
    """Download Laubach-Williams r* estimates from NY Fed (quarterly).
    Reads the 'data' sheet; dates are already Python datetimes in column 0,
    one-sided rstar estimate is in column 2.
    """
    url = ('https://www.newyorkfed.org/medialibrary/media/research/economists'
           '/williams/data/Laubach_Williams_current_estimates.xlsx')
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name='data', skiprows=5, header=0)
    # Column 0 = Date, column 2 = one-sided rstar
    df = df.dropna(subset=[df.columns[0]])
    df[df.columns[0]] = pd.to_datetime(df.iloc[:, 0])
    df = df.set_index(df.columns[0])
    series = df.iloc[:, 1].dropna().astype(float)   # col index 1 = rstar (after dropping Unnamed:1 via iloc)
    # Use iloc col 1 which is rstar (first non-empty data col after Date)
    # Try column named 'rstar' first
    rstar_cols = [c for c in df.columns if str(c).strip().lower() == 'rstar']
    if rstar_cols:
        series = df[rstar_cols[0]].dropna().astype(float)
    else:
        series = df.iloc[:, 1].dropna().astype(float)
    if not isinstance(series.index, pd.DatetimeIndex) or series.empty:
        return pd.Series(dtype=float)
    return series


def fetch_richmond_nri():
    """Download natural rate of interest data from Richmond Fed (quarterly)."""
    urls = [
        'https://www.richmondfed.org/-/media/richmondfedorg/research/national_economy/natural_rate_of_interest/data/natural-rate-of-interest-data.xlsx',
        'https://www.richmondfed.org/-/media/richmondfedorg/research/national_economy/natural_rate_of_interest/natural_rate_of_interest_data.xlsx',
        'https://www.richmondfed.org/-/media/richmondfedorg/research/national_economy/natural_rate_of_interest/data/natural_rate_of_interest_data.xlsx',
    ]
    r = None
    for url in urls:
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200:
                r = resp
                break
        except Exception:
            continue
    if r is None:
        print("    Warning: Richmond Fed data unavailable — could not reach any known URL")
        return pd.Series(dtype=float)
    try:
        r.raise_for_status()
        df = pd.read_excel(io.BytesIO(r.content))
        df.columns = [str(c).strip() for c in df.columns]
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col]).set_index(date_col)
        median_cols = [c for c in df.columns if 'median' in c.lower()]
        if median_cols:
            return df[median_cols[0]].dropna().astype(float)
        numeric = df.select_dtypes(include='number').columns
        return df[numeric[0]].dropna().astype(float) if len(numeric) else pd.Series(dtype=float)
    except Exception as e:
        print(f"    Warning: Richmond Fed data unavailable — {e}")
        return pd.Series(dtype=float)


def build_money_matters():
    print("  Fetching money matters...")

    # Fed funds rate target bounds (daily → resample monthly)
    ffr_upper_d = fetch_fred('DFEDTARU')
    ffr_lower_d = fetch_fred('DFEDTARL')
    ffr_upper   = ffr_upper_d.resample('MS').last().ffill()
    ffr_lower   = ffr_lower_d.resample('MS').last().ffill()

    # Year-over-year CPI inflation for real rate calculation
    cpi = fetch_fred('CPIAUCSL')
    cpi_inf = cpi.pct_change(12) * 100

    df = pd.DataFrame({
        'ffr_upper': ffr_upper,
        'ffr_lower': ffr_lower,
        'cpi_inf':   cpi_inf,
    }).dropna()
    df['real_upper'] = (df['ffr_upper'] - df['cpi_inf']).round(3)
    df['real_lower'] = (df['ffr_lower'] - df['cpi_inf']).round(3)

    # Laubach-Williams natural rate (quarterly → forward-fill to monthly)
    try:
        lw_raw = fetch_ny_fed_lw()
        if isinstance(lw_raw.index, pd.DatetimeIndex) and not lw_raw.empty:
            lw = lw_raw.resample('MS').last().ffill()
        else:
            lw = pd.Series(dtype=float)
            print("    Warning: NY Fed LW data unavailable — unexpected format")
    except Exception as e:
        print(f"    Warning: NY Fed LW data unavailable — {e}")
        lw = pd.Series(dtype=float)

    result = pd.DataFrame({
        'real_upper': df['real_upper'],
        'real_lower': df['real_lower'],
        'natural_lw': lw,
    })
    result = result[result.index >= pd.Timestamp('2024-01-01')]

    return {
        'dates':             dates_list(result.index),
        'real_ffr_upper':    to_list(result['real_upper']),
        'real_ffr_lower':    to_list(result['real_lower']),
        'natural_rate_lw':   to_list(result['natural_lw']),
    }


# ── LABOR MARKET ──────────────────────────────────────────────────────────────

def build_labor():
    print("  Fetching labor market data...")

    # Unemployment rates from FRED (SA where available)
    lubbock_ur = fetch_fred('LUBB148UR')   # Lubbock, TX MSA — SA
    dfw_ur     = fetch_fred('DALL148UR')   # Dallas-Fort Worth-Arlington MSA — SA
    texas_ur   = fetch_fred('TXUR')        # Texas — SA
    us_ur      = fetch_fred('UNRATE')      # United States — SA

    # Nonfarm payroll employment from FRED (SA)
    lubbock_emp = fetch_fred('LUBB148NA')  # Lubbock nonfarm (thousands) — SA
    dfw_emp     = fetch_fred('DALL148NA')  # DFW nonfarm (thousands) — SA
    texas_emp   = fetch_fred('TXNA')       # Texas nonfarm (thousands) — SA
    us_emp      = fetch_fred('PAYEMS')     # US nonfarm (thousands) — SA

    # Employment indices (Jan 2020 = 100)
    emp = pd.DataFrame({
        'lubbock': lubbock_emp,
        'dfw':     dfw_emp,
        'texas':   texas_emp,
        'us':      us_emp,
    }).dropna(how='all')

    emp_idx = pd.DataFrame({
        'lubbock': index_to_base(emp['lubbock']),
        'dfw':     index_to_base(emp['dfw']),
        'texas':   index_to_base(emp['texas']),
        'us':      index_to_base(emp['us']),
    })

    emp_growth = pd.DataFrame({
        'lubbock': yoy(emp['lubbock']),
        'dfw':     yoy(emp['dfw']),
        'texas':   yoy(emp['texas']),
        'us':      yoy(emp['us']),
    })

    ur = pd.DataFrame({
        'lubbock': lubbock_ur,
        'dfw':     dfw_ur,
        'texas':   texas_ur,
        'us':      us_ur,
    })

    result = pd.concat([ur, emp_idx.add_suffix('_idx'), emp_growth.add_suffix('_growth')], axis=1)
    result = result[result.index >= pd.Timestamp(START_DATE)]

    return {
        'dates':               dates_list(result.index),
        'lubbock_unemployment': to_list(result['lubbock']),
        'dfw_unemployment':     to_list(result['dfw']),
        'texas_unemployment':   to_list(result['texas']),
        'us_unemployment':      to_list(result['us']),
        'lubbock_emp_index':    to_list(result['lubbock_idx']),
        'dfw_emp_index':        to_list(result['dfw_idx']),
        'texas_emp_index':      to_list(result['texas_idx']),
        'us_emp_index':         to_list(result['us_idx']),
        'lubbock_emp_growth':   to_list(result['lubbock_growth']),
        'dfw_emp_growth':       to_list(result['dfw_growth']),
        'texas_emp_growth':     to_list(result['texas_growth']),
        'us_emp_growth':        to_list(result['us_growth']),
    }


# ── WAGES ─────────────────────────────────────────────────────────────────────

def build_wages():
    print("  Fetching wages data...")

    # Average weekly wages — all seasonally adjusted (SA) so levels and ratios are smooth
    # Lubbock and DFW: FRED ENUC QCEW series, SA
    lubbock_wages = fetch_fred('ENUC311840010SA')   # Lubbock MSA, total covered, SA
    dfw_wages     = fetch_fred('ENUC191040010SA')   # DFW MSA, total covered, SA
    # Texas: No SA QCEW or SA CES available on FRED; apply 12-month trailing MA to NSA monthly
    # series before resampling to quarterly — this removes the seasonal cycle without external libs
    texas_wages_m = fetch_fred('SMU48000000500000011')   # Texas CES, NSA monthly
    if not texas_wages_m.empty:
        texas_wages = texas_wages_m.rolling(12, min_periods=4).mean().resample('QS').mean()
    else:
        texas_wages = pd.Series(dtype=float)
    # US: FRED CES average weekly earnings, all employees, total private, SA (monthly → quarterly)
    us_wages_m = fetch_fred('CES0500000011')         # US CES, SA monthly
    us_wages   = us_wages_m.resample('QS').mean() if not us_wages_m.empty else pd.Series(dtype=float)

    df = pd.DataFrame({
        'lubbock': lubbock_wages,
        'dfw':     dfw_wages,
        'texas':   texas_wages,
        'us':      us_wages,
    }).dropna(how='all')

    # YoY growth uses 4-quarter lag for quarterly data
    df['lubbock_g'] = yoy(df['lubbock'], 4)
    df['dfw_g']     = yoy(df['dfw'],     4)
    df['texas_g']   = yoy(df['texas'],   4)
    df['us_g']      = yoy(df['us'],      4)

    df['lubbock_texas_ratio'] = (df['lubbock'] / df['texas']).round(4)
    df['lubbock_us_ratio']    = (df['lubbock'] / df['us']).round(4)

    if isinstance(df.index, pd.DatetimeIndex) and not df.empty:
        df = df[df.index >= pd.Timestamp(START_DATE)]

    return {
        'dates':               dates_list(df.index),
        'lubbock_wages':       to_list(df['lubbock']),
        'dfw_wages':           to_list(df['dfw']),
        'texas_wages':         to_list(df['texas']),
        'us_wages':            to_list(df['us']),
        'lubbock_wage_growth': to_list(df['lubbock_g']),
        'dfw_wage_growth':     to_list(df['dfw_g']),
        'texas_wage_growth':   to_list(df['texas_g']),
        'us_wage_growth':      to_list(df['us_g']),
        'lubbock_texas_ratio': to_list(df['lubbock_texas_ratio']),
        'lubbock_us_ratio':    to_list(df['lubbock_us_ratio']),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs('data', exist_ok=True)
    print("Texas Trends data fetch starting...\n")

    sections = [
        ('price_pressures', build_price_pressures),
        ('money_matters',   build_money_matters),
        ('labor',           build_labor),
        ('wages',           build_wages),
    ]

    for name, builder in sections:
        try:
            data = builder()
            with open(f'data/{name}.json', 'w') as f:
                json.dump(data, f)
            print(f"  ✓ {name}.json saved")
        except Exception as e:
            print(f"  ✗ {name} FAILED: {e}")
            raise

    metadata = {
        'last_updated': datetime.now().strftime('%B %d, %Y'),
        'data_through': datetime.now().strftime('%Y-%m'),
    }
    with open('data/metadata.json', 'w') as f:
        json.dump(metadata, f)
    print("  ✓ metadata.json saved")
    print("\nAll data updated successfully.")


if __name__ == '__main__':
    main()
