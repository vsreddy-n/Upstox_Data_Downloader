import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta

# Safe optimization: HTTPx for faster HTTP with connection pooling
try:
    import httpx
    HTTPX_AVAILABLE = True
    print("✅ HTTPx available - using optimized HTTP client with connection pooling")
except ImportError:
    import requests
    HTTPX_AVAILABLE = False
    print("⚠️  HTTPx not available, falling back to requests")

# Install flowguard if not available: pip install flowguard
try:
    from flowguard import RateLimiter
    FLOWGUARD_AVAILABLE = True
except ImportError:
    print("⚠️  flowguard not installed. Install with: pip install flowguard")
    print("   Falling back to basic rate limiting...")
    FLOWGUARD_AVAILABLE = False

# ================================
# USER CONFIGURATION - DATE RANGE BASED
# ================================
# User provides start and end dates, system finds relevant expiries
USER_START_DATE = "2025-01-01"     # User provides this (example: 15-Apr-2025)
USER_END_DATE = "2025-05-31"       # User provides this (example: 15-May-2025)
TIMEFRAME = "5minute"              # User configurable: 1minute, 5minute, 15minute, 1day, etc.

# Expiry data source
EXPIRY_FILE_PATH = "data/Future_expiry_date.txt"  # Path to expiry dates file

# Index Selection - User Input
INDEX_TYPE = "NIFTY_50"            # User selects: NIFTY_50, BANK_NIFTY, SENSEX, etc.

# Index Mapping for Futures
INDEX_MAPPING = {
    "NIFTY_50": "NSE_INDEX|Nifty 50",
    "BANK_NIFTY": "NSE_INDEX|Nifty Bank", 
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY_IT": "NSE_INDEX|Nifty IT",
    "NIFTY_PHARMA": "NSE_INDEX|Nifty Pharma",
}

# Get the actual instrument key
INSTRUMENT_KEY = INDEX_MAPPING[INDEX_TYPE]

# ================================
# MULTIPLE ACCESS TOKENS
# ================================
# Import centralized token configuration
from upstox_tokens import get_multi_tokens, get_headers

# Get multiple tokens from centralized config
ACCESS_TOKENS = get_multi_tokens()

# Token rotation state
current_token_index = 0
token_request_counts = [0] * len(ACCESS_TOKENS)  # Track requests per token
token_start_times = [time.time()] * len(ACCESS_TOKENS)  # Track 30-min windows

def get_current_token():
    """Get current active token and rotate if needed"""
    global current_token_index
    return ACCESS_TOKENS[current_token_index]

def rotate_token():
    """Rotate to next available token"""
    global current_token_index
    
    if len(ACCESS_TOKENS) == 1:
        return  # No rotation possible with single token
    
    # Find next token that hasn't hit rate limit
    for i in range(len(ACCESS_TOKENS)):
        next_index = (current_token_index + 1 + i) % len(ACCESS_TOKENS)
        
        # Check if this token's 30-minute window has reset
        time_elapsed = time.time() - token_start_times[next_index]
        if time_elapsed >= 1800:  # 30 minutes = 1800 seconds
            # Reset this token's counters
            token_request_counts[next_index] = 0
            token_start_times[next_index] = time.time()
            current_token_index = next_index
            print(f"🔄 Rotated to futures token #{next_index + 1} (window reset)")
            return
        
        # Check if this token has capacity
        if token_request_counts[next_index] < 1800:  # Stay under 2000 limit
            current_token_index = next_index
            print(f"🔄 Rotated to futures token #{next_index + 1} ({token_request_counts[next_index]}/1800 requests used)")
            return
    
    # All tokens are at limit - wait for oldest to reset
    oldest_token = min(range(len(ACCESS_TOKENS)), key=lambda i: token_start_times[i])
    wait_time = 1800 - (time.time() - token_start_times[oldest_token])
    if wait_time > 0:
        print(f"⏳ All futures tokens at limit. Waiting {wait_time:.0f}s for token #{oldest_token + 1} to reset...")
        time.sleep(wait_time)
        token_request_counts[oldest_token] = 0
        token_start_times[oldest_token] = time.time()
        current_token_index = oldest_token

def track_request():
    """Track request for current token and rotate if needed"""
    global current_token_index
    
    # Increment request count for current token
    token_request_counts[current_token_index] += 1
    
    # Check if current token is approaching limit
    if token_request_counts[current_token_index] >= 1800:  # 90% of 2000 limit
        print(f"⚠️  Futures token #{current_token_index + 1} approaching limit ({token_request_counts[current_token_index]}/2000)")
        rotate_token()

# ================================
# RATE LIMITING SETUP
# ================================
if FLOWGUARD_AVAILABLE:
    # VERY Conservative settings to avoid 429 errors: 15 req/sec, 200 req/min
    rate_limiter = RateLimiter(sec=15, min=200, max_burst=3)
    print("✅ Using flowguard rate limiter (15 req/sec, 200 req/min)")
else:
    rate_limiter = None
    print("⚠️  Using basic rate limiting (100ms delays)")

# ================================
# UTILITY FUNCTIONS
# ================================

def get_current_headers():
    """Get headers with current active token"""
    return {
        'accept': 'application/json',
        'Authorization': f'Bearer {get_current_token()}'
    }

# Global HTTP client for connection pooling (optimization #2)
http_client = None

def get_http_client():
    """Get or create HTTP client with connection pooling"""
    global http_client
    if http_client is None:
        if HTTPX_AVAILABLE:
            # HTTPx with connection pooling for better performance
            http_client = httpx.Client(
                timeout=30.0,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)
            )
        else:
            # Requests session for connection pooling
            import requests
            http_client = requests.Session()
    return http_client

def make_request(method, url, headers=None, params=None, data=None):
    """Optimized HTTP request with connection pooling"""
    try:
        client = get_http_client()
        
        if method == 'GET':
            response = client.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = client.post(url, headers=headers, params=params, json=data)
        elif method == 'PUT':
            response = client.put(url, headers=headers, params=params, json=data)
        else:
            raise ValueError('Invalid HTTP method.')
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return response
            
    except Exception as e:
        print(f'An error occurred: {e}')
        return None

def is_monthly_expiry(expiry_date):
    """Check if an expiry date is likely a monthly expiry (last Thursday of month)"""
    from datetime import datetime, timedelta

    expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")

    # Check if it's a Thursday (weekday 3)
    if expiry_dt.weekday() != 3:
        return False

    # Check if it's the last Thursday of the month
    # Find the last day of the month
    if expiry_dt.month == 12:
        next_month = expiry_dt.replace(year=expiry_dt.year + 1, month=1, day=1)
    else:
        next_month = expiry_dt.replace(month=expiry_dt.month + 1, day=1)

    last_day_of_month = next_month - timedelta(days=1)

    # Find the last Thursday of the month
    days_back = (last_day_of_month.weekday() - 3) % 7
    last_thursday = last_day_of_month - timedelta(days=days_back)

    return expiry_dt.date() == last_thursday.date()

def find_relevant_expiries(start_date, end_date, all_expiry_dates):
    """Find expiries that cover the user's date range, preferring monthly expiries"""
    from datetime import datetime

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    print(f"📅 User date range: {start_date} to {end_date}")
    print(f"📊 Available expiry dates: {len(all_expiry_dates)} total")

    # Sort expiry dates chronologically
    sorted_expiries = sorted(all_expiry_dates)

    # Separate monthly and weekly expiries
    monthly_expiries = []
    weekly_expiries = []

    for expiry in sorted_expiries:
        if is_monthly_expiry(expiry):
            monthly_expiries.append(expiry)
        else:
            weekly_expiries.append(expiry)

    print(f"📊 Monthly expiries: {len(monthly_expiries)}, Weekly expiries: {len(weekly_expiries)}")
    print(f"🎯 Prioritizing monthly expiries for better liquidity")

    relevant_expiries = []
    current_date = start_dt

    # Use monthly expiries to cover the date range
    for expiry_str in monthly_expiries:
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")

        # If this monthly expiry is on or after our current position
        if expiry_dt >= current_date:
            relevant_expiries.append(expiry_str)
            print(f"   ✓ {expiry_str} - monthly expiry (preferred)")

            # If this expiry covers our end date, we're done
            if expiry_dt >= end_dt:
                print(f"   🎯 {expiry_str} - covers end date, selection complete")
                break

            # Move current position to day after this expiry
            current_date = expiry_dt + timedelta(days=1)

    # If monthly expiries don't fully cover the range, fill gaps with weekly expiries
    if relevant_expiries:
        last_monthly_expiry = datetime.strptime(relevant_expiries[-1], "%Y-%m-%d")
        if last_monthly_expiry < end_dt:
            print(f"   📅 Monthly expiries don't fully cover range, checking weekly expiries...")

            for expiry_str in weekly_expiries:
                expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")

                if expiry_dt > last_monthly_expiry and expiry_dt >= end_dt:
                    relevant_expiries.append(expiry_str)
                    print(f"   ✓ {expiry_str} - weekly expiry (gap filler)")
                    break

    if not relevant_expiries:
        print(f"❌ No suitable expiries found that cover the date range {start_date} to {end_date}")
        print(f"   Available monthly expiries: {monthly_expiries[:5]}...")
        return []

    print(f"✅ Selected {len(relevant_expiries)} relevant expiries: {relevant_expiries}")

    # Show the coverage breakdown
    print(f"\n📋 Coverage breakdown:")
    for i, expiry in enumerate(relevant_expiries):
        expiry_type = "Monthly" if is_monthly_expiry(expiry) else "Weekly"

        if i == 0:
            # First expiry covers from start_date to expiry
            period_start = start_date
        else:
            # Subsequent expiries cover from day after previous expiry
            prev_expiry_dt = datetime.strptime(relevant_expiries[i-1], "%Y-%m-%d")
            period_start_dt = prev_expiry_dt + timedelta(days=1)
            period_start = period_start_dt.strftime("%Y-%m-%d")

        # Period ends at current expiry (but not beyond user's end date)
        expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
        period_end = min(expiry, end_date)

        print(f"   📅 {period_start} to {period_end} → {expiry} expiry ({expiry_type})")

    return relevant_expiries

def calculate_data_range(expiry_date, previous_expiry=None, user_start_date=None, user_end_date=None):
    """Calculate start and end dates for historical data collection based on user's date range"""
    from datetime import datetime

    user_start_dt = datetime.strptime(user_start_date, "%Y-%m-%d")
    user_end_dt = datetime.strptime(user_end_date, "%Y-%m-%d")
    expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")

    if previous_expiry is None:
        # First expiry - start from user's start date
        start_date = user_start_date
        print(f"    📅 First expiry: From user start date {user_start_date}")
    else:
        # Subsequent expiry - start from day after previous expiry
        prev_dt = datetime.strptime(previous_expiry, "%Y-%m-%d")
        start_dt = prev_dt + timedelta(days=1)
        start_date = start_dt.strftime("%Y-%m-%d")
        print(f"    📅 Subsequent expiry: From day after {previous_expiry}")

    # End date is the minimum of expiry date and user's end date
    end_dt = min(expiry_dt, user_end_dt)
    end_date = end_dt.strftime("%Y-%m-%d")

    return start_date, end_date

def create_filename(file_type):
    """Create standardized filename based on user's date range"""
    base_name = f"{INDEX_TYPE}_FUTURES_{TIMEFRAME}_{USER_START_DATE}_{USER_END_DATE}"

    if file_type == "expiry":
        return f"{base_name}_expiry_dates.json"
    elif file_type == "instruments":
        return f"{base_name}_instrument_keys.json"
    elif file_type == "historical":
        return f"{base_name}_historical_data.csv"

    return base_name

def create_futures_symbol(base_symbol, expiry_date):
    """Optimized futures symbol creation (optimization #3)"""
    try:
        # Parse expiry date: "2025-01-30"
        date_obj = datetime.strptime(expiry_date, "%Y-%m-%d")

        # Optimized string formatting
        day = date_obj.strftime("%d")           # "30"
        month = date_obj.strftime("%b").upper() # "JAN"
        year = date_obj.strftime("%Y")          # "2025"

        # Format: NIFTY30JAN2025 (no strike price or option type for futures)
        symbol = f"{base_symbol}{day}{month}{year}"
        return symbol
    except Exception as e:
        print(f"Error creating futures symbol: {e}")
        return f"{base_symbol}_FUTURES"

def make_request_with_token_rotation(method, url, params=None, data=None):
    """Make request with automatic token rotation on rate limits"""
    max_retries = len(ACCESS_TOKENS) + 1  # Try all tokens plus one retry

    for attempt in range(max_retries):
        # Track request for current token
        track_request()

        # Get current headers with active token
        headers = get_current_headers()

        # Add delay to respect rate limits
        time.sleep(0.2)  # Reduced from 0.6s to 0.2s for better performance

        response = make_request(method, url, headers=headers, params=params, data=data)

        if response and (isinstance(response, dict) and response.get('status') == 'success'):
            return response
        elif response is None:
            print(f"    Futures request failed for {url} - no response")
            return None
        else:
            print(f"    Futures request failed for {url} - invalid response")
            return None

    print(f"    All futures tokens exhausted for {url}")
    return None

def save_historical_data(all_data):
    """Save historical data to single CSV file in data folder with auto-sorting"""
    if not all_data:
        return None

    # Create DataFrame with specific column order
    df = pd.DataFrame(all_data)

    # Ensure columns are in the correct order
    column_order = ['symbol', 'date', 'time', 'fut_open', 'fut_high', 'fut_low', 'fut_close', 'fut_vol', 'fut_oi']
    df = df[column_order]

    # Auto-sort by date and time
    print(f"🔄 Auto-sorting {len(all_data)} records by date and time...")
    df['datetime_combined'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df = df.sort_values('datetime_combined')
    df = df.drop('datetime_combined', axis=1)
    df = df.reset_index(drop=True)

    # Show date range after sorting
    first_datetime = f"{df.iloc[0]['date']} {df.iloc[0]['time']}"
    last_datetime = f"{df.iloc[-1]['date']} {df.iloc[-1]['time']}"
    print(f"📊 Data range: {first_datetime} to {last_datetime}")

    filename = create_filename("historical")
    df.to_csv(filename, index=False)

    print(f"📁 Saved {len(all_data)} futures records to: {filename}")
    print(f"✅ Data automatically sorted chronologically")
    return filename

# ================================
# MAIN FUNCTIONS FOR FUTURES
# ================================

def show_available_expiries(all_expiry_dates):
    """Show available expiry dates for debugging"""
    print(f"\n🔍 DEBUG: Available expiry dates around user's date range:")

    # Sort expiries
    sorted_expiries = sorted(all_expiry_dates)

    # Show expiries around user's date range
    user_start_dt = datetime.strptime(USER_START_DATE, "%Y-%m-%d")
    user_end_dt = datetime.strptime(USER_END_DATE, "%Y-%m-%d")

    relevant_window = []
    for expiry in sorted_expiries:
        expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
        # Show expiries within 2 months of user's date range
        if (expiry_dt >= user_start_dt - timedelta(days=60) and
            expiry_dt <= user_end_dt + timedelta(days=60)):
            expiry_type = "Monthly" if is_monthly_expiry(expiry) else "Weekly"
            relevant_window.append(f"   {expiry} ({expiry_type})")

    for line in relevant_window:
        print(line)

def get_expiry_dates():
    """Step 1: Get expiry dates and find relevant ones for user's date range"""
    print("Step 1: Fetching futures expiry dates...")

    url = "https://api.upstox.com/v2/expired-instruments/expiries"
    params = {
        'instrument_key': INSTRUMENT_KEY
    }

    response = make_request_with_token_rotation('GET', url, params=params)

    if response and response.get('status') == 'success':
        all_expiry_dates = response['data']

        print(f"📊 Fetched {len(all_expiry_dates)} total expiry dates from API")

        # Show available expiries for debugging
        show_available_expiries(all_expiry_dates)

        # Find expiries that cover the user's date range
        relevant_expiries = find_relevant_expiries(USER_START_DATE, USER_END_DATE, all_expiry_dates)

        if not relevant_expiries:
            print("❌ No relevant expiry dates found for the specified date range")
            print("💡 Try adjusting USER_START_DATE and USER_END_DATE")
            return []

        # Save relevant expiries to JSON
        filename = create_filename("expiry")
        with open(filename, 'w') as f:
            json.dump(relevant_expiries, f, indent=2)

        print(f"✓ Found {len(relevant_expiries)} relevant futures expiry dates")
        print(f"✓ Saved to: {filename}")

        return relevant_expiries
    else:
        print("✗ Failed to fetch futures expiry dates")
        return []

def fetch_futures_contracts_for_expiry(expiry_date):
    """Fetch futures contracts for a single expiry date with token rotation"""
    print(f"  Processing futures expiry: {expiry_date}")

    # For futures, we use a different endpoint - future/contract (singular) instead of option/contract
    url = "https://api.upstox.com/v2/expired-instruments/future/contract"
    params = {
        'instrument_key': INSTRUMENT_KEY,
        'expiry_date': expiry_date
    }

    response = make_request_with_token_rotation('GET', url, params=params)

    if response and response.get('status') == 'success':
        contracts = response['data']
        instrument_keys = [contract['instrument_key'] for contract in contracts]

        # Store contract details for later use (futures have no strike price or option type)
        contract_details = {}
        for contract in contracts:
            contract_details[contract['instrument_key']] = {
                'symbol': contract['underlying_symbol'],
                'expiry_date': contract['expiry'],
                'lot_size': contract.get('lot_size', 1),  # Futures have lot sizes
                'tick_size': contract.get('tick_size', 0.05)  # Futures have tick sizes
            }

        print(f"    ✓ Found {len(instrument_keys)} futures instruments for {expiry_date}")
        return expiry_date, instrument_keys, contract_details
    else:
        print(f"    ✗ Failed to fetch futures instruments for {expiry_date}")
        return expiry_date, [], {}

def get_instrument_keys(expiry_dates):
    """Step 2: Get futures instrument keys for each expiry date with token rotation"""
    print("\nStep 2: Fetching futures instrument keys...")

    instrument_data = {}
    contract_details = {}

    # Process each expiry date sequentially
    for expiry_date in expiry_dates:
        expiry_date, instrument_keys, expiry_contract_details = fetch_futures_contracts_for_expiry(expiry_date)
        instrument_data[expiry_date] = instrument_keys
        contract_details.update(expiry_contract_details)

    # Save to JSON
    filename = create_filename("instruments")
    with open(filename, 'w') as f:
        json.dump(instrument_data, f, indent=2)

    print(f"✓ Saved futures instrument keys to: {filename}")
    return instrument_data, contract_details

def fetch_historical_data_for_futures_instrument(instrument_key, start_date, end_date, contract_details):
    """Fetch historical data for a single futures instrument with token rotation"""
    url = f"https://api.upstox.com/v2/expired-instruments/historical-candle/{instrument_key}/{TIMEFRAME}/{end_date}/{start_date}"

    response = make_request_with_token_rotation('GET', url)

    if response and response.get('status') == 'success':
        candle_data = response['data']['candles']

        # Get contract details for this futures instrument
        contract_info = contract_details.get(instrument_key, {})
        base_symbol = contract_info.get('symbol', 'UNKNOWN')
        expiry_date_formatted = contract_info.get('expiry_date', end_date)
        lot_size = contract_info.get('lot_size', 1)
        tick_size = contract_info.get('tick_size', 0.05)

        # Create the formatted futures symbol: NIFTYDDMMMYYYY
        formatted_symbol = create_futures_symbol(base_symbol, expiry_date_formatted)

        processed_data = []

        # Process each candle
        for candle in candle_data:
            # Parse timestamp to get date and time
            timestamp_str = candle[0]
            try:
                # Parse the timestamp (format: 2025-01-16T15:25:00+05:30)
                dt = datetime.strptime(timestamp_str.split('+')[0], "%Y-%m-%dT%H:%M:%S")
                date_part = dt.strftime("%Y-%m-%d")
                time_part = dt.strftime("%H:%M:%S")
            except:
                # Fallback if parsing fails
                date_part = timestamp_str.split('T')[0] if 'T' in timestamp_str else timestamp_str[:10]
                time_part = timestamp_str.split('T')[1][:8] if 'T' in timestamp_str else "00:00:00"

            # Round all values to whole numbers (no decimals)
            row = {
                'symbol': formatted_symbol,
                'date': date_part,
                'time': time_part,
                'fut_open': round(candle[1]),
                'fut_high': round(candle[2]),
                'fut_low': round(candle[3]),
                'fut_close': round(candle[4]),
                'fut_vol': round(candle[5]),
                'fut_oi': round(candle[6]) if len(candle) > 6 else 0
            }
            processed_data.append(row)

        return instrument_key, processed_data, len(candle_data)
    else:
        return instrument_key, [], 0

def get_historical_data(instrument_data, contract_details, expiry_dates):
    """Step 3: Get historical candle data for all futures instruments with token rotation"""
    print("\nStep 3: Fetching futures historical data...")

    all_historical_data = []
    date_ranges = []  # Store date ranges for terminal output
    expiry_status = {}  # Track success/failure per expiry

    for i, expiry_date in enumerate(expiry_dates):
        # Calculate data range for this expiry
        previous_expiry = expiry_dates[i-1] if i > 0 else None
        start_date, end_date = calculate_data_range(
            expiry_date,
            previous_expiry,
            USER_START_DATE,
            USER_END_DATE
        )

        date_ranges.append(f"{expiry_date}: {start_date} to {end_date}")
        print(f"  Futures Expiry: {expiry_date} | Data range: {start_date} to {end_date}")

        instruments = instrument_data.get(expiry_date, [])

        if not instruments:
            expiry_status[expiry_date] = {'status': 'failed', 'reason': 'No futures instruments found', 'processed': 0, 'total': 0}
            continue

        print(f"    Processing {len(instruments)} futures instruments with token rotation...")

        # Track success for this expiry
        successful_instruments = 0
        total_records_for_expiry = 0

        # Process each futures instrument sequentially with token rotation
        for i, instrument_key in enumerate(instruments, 1):
            print(f"      Processing {i}/{len(instruments)}: {instrument_key} [Token #{current_token_index + 1}]")

            instrument_key, processed_data, candle_count = fetch_historical_data_for_futures_instrument(
                instrument_key, start_date, end_date, contract_details
            )

            if processed_data:
                all_historical_data.extend(processed_data)
                successful_instruments += 1
                total_records_for_expiry += candle_count
                print(f"      ✓ {instrument_key}: Added {candle_count} candles")
            else:
                print(f"      ✗ {instrument_key}: Failed to fetch data")

        # Determine status for this expiry
        if successful_instruments == 0:
            expiry_status[expiry_date] = {'status': 'failed', 'reason': 'All futures instruments failed', 'processed': 0, 'total': len(instruments)}
        elif successful_instruments < len(instruments):
            expiry_status[expiry_date] = {'status': 'partial', 'reason': f'{successful_instruments}/{len(instruments)} futures instruments', 'processed': successful_instruments, 'total': len(instruments)}
        else:
            expiry_status[expiry_date] = {'status': 'success', 'reason': f'All {len(instruments)} futures instruments', 'processed': successful_instruments, 'total': len(instruments)}

    # Save historical data to single CSV file
    if all_historical_data:
        print(f"\n📁 Saving {len(all_historical_data)} futures records to CSV...")
        saved_file = save_historical_data(all_historical_data)

        return all_historical_data, date_ranges, expiry_status, saved_file
    else:
        print("✗ No futures historical data collected")
        return [], date_ranges, expiry_status, None

# ================================
# MAIN EXECUTION
# ================================

def print_status_summary(expiry_status, date_ranges, saved_file):
    """Print final status summary with icons"""
    print("\n📅 FUTURES DATE RANGES RETRIEVED:")

    for date_range in date_ranges:
        expiry_date = date_range.split(':')[0]
        status_info = expiry_status.get(expiry_date, {})
        status = status_info.get('status', 'unknown')
        reason = status_info.get('reason', 'Unknown')
        processed = status_info.get('processed', 0)
        total = status_info.get('total', 0)

        if status == 'success':
            icon = "✅"
            details = f"({processed} futures instruments, complete)"
        elif status == 'partial':
            icon = "⚠️ "
            details = f"({processed}/{total} futures instruments, partial)"
        elif status == 'failed':
            icon = "❌"
            details = f"({reason})"
        else:
            icon = "❓"
            details = f"(Unknown status)"

        print(f"   {icon} {date_range} {details}")

    # Summary statistics
    success_count = sum(1 for status in expiry_status.values() if status.get('status') == 'success')
    partial_count = sum(1 for status in expiry_status.values() if status.get('status') == 'partial')
    failed_count = sum(1 for status in expiry_status.values() if status.get('status') == 'failed')

    print(f"\n📊 FUTURES SUMMARY:")
    print(f"   ✅ Successful: {success_count} expiry dates")
    if partial_count > 0:
        print(f"   ⚠️  Partial: {partial_count} expiry dates")
    if failed_count > 0:
        print(f"   ❌ Failed: {failed_count} expiry dates")

    # Show saved file
    if saved_file:
        print(f"\n📁 FUTURES FILE SAVED:")
        print(f"   📄 {saved_file}")

def print_token_summary():
    """Print token usage summary"""
    print(f"\n🔑 FUTURES TOKEN USAGE SUMMARY:")
    for i, count in enumerate(token_request_counts):
        percentage = (count / 2000) * 100
        print(f"   Token #{i + 1}: {count}/2000 requests ({percentage:.1f}%)")

def main():
    """Multi-token futures data extraction with automatic rotation"""
    start_time = time.time()

    print("=" * 70)
    print("UPSTOX FUTURES DATA EXTRACTOR (DATE RANGE BASED)")
    print("=" * 70)
    print(f"Index: {INDEX_TYPE}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"User Date Range: {USER_START_DATE} to {USER_END_DATE}")
    print(f"Tokens Available: {len(ACCESS_TOKENS)}")
    print(f"Effective Rate Limit: {len(ACCESS_TOKENS) * 1800} req/30min")

    # Show active safe optimizations
    optimizations = []
    if HTTPX_AVAILABLE:
        optimizations.append("HTTPx + Connection Pooling")
    optimizations.append("Optimized Data Processing")
    optimizations.append("Automatic Token Rotation")

    print(f"Optimizations: {', '.join(optimizations)}")
    print("Processing: Sequential with Token Rotation (600ms delays per token)")
    print(f"Output: All files saved in data folder")
    print(f"CSV Columns: symbol, date, time, fut_open, fut_high, fut_low, fut_close, fut_vol, fut_oi")
    print("=" * 60)

    # Create data directory if it doesn't exist and change to it
    os.makedirs("data", exist_ok=True)
    os.chdir("data")

    # Step 1: Get futures expiry dates (JSON saved in main data directory)
    expiry_dates = get_expiry_dates()

    if not expiry_dates:
        print("No futures expiry dates found. Exiting...")
        return

    # Step 2: Get futures instrument keys (JSON saved in main data directory)
    instrument_data, contract_details = get_instrument_keys(expiry_dates)

    # Step 3: Get futures historical data (CSV files saved)
    all_data, date_ranges, expiry_status, saved_files = get_historical_data(instrument_data, contract_details, expiry_dates)

    print("\n" + "=" * 60)
    print("FUTURES EXTRACTION COMPLETE!")
    print("=" * 60)
    print(f"✓ Processed {len(expiry_dates)} futures expiry dates")
    print(f"✓ Total futures instruments: {sum(len(instruments) for instruments in instrument_data.values())}")
    print(f"✓ Total futures historical records: {len(all_data)}")

    # Print detailed status summary
    print_status_summary(expiry_status, date_ranges, saved_files)

    # Print token usage summary
    print_token_summary()

    # Calculate and display execution time
    end_time = time.time()
    execution_time = end_time - start_time
    execution_minutes = execution_time / 60

    print(f"\n⏱️  EXECUTION TIME:")
    print(f"   Total time: {execution_time:.2f} seconds ({execution_minutes:.2f} minutes)")
    print(f"   Performance: {len(all_data)} futures records in {execution_minutes:.2f} minutes")

    print("=" * 60)

    # Cleanup HTTP client
    if http_client:
        try:
            http_client.close()
        except:
            pass

if __name__ == "__main__":
    main()
