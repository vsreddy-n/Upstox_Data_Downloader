import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from urllib.parse import quote

# ================================
# USER CONFIGURATION
# ================================
START_DATE = "2024-12-20"
END_DATE = "2024-12-25"
TIMEFRAME = "5minute"  # v3 API supports: 1minute, 5minute, 15minute, 30minute, 1hour, 1day

# Index Configuration
INDEX_TYPE = "NIFTY_50"
INDEX_MAPPING = {
    "NIFTY_50": "NSE_INDEX|Nifty 50",
    "BANK_NIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY_IT": "NSE_INDEX|Nifty IT",
    "NIFTY_PHARMA": "NSE_INDEX|Nifty Pharma",
}

INSTRUMENT_KEY = INDEX_MAPPING[INDEX_TYPE]

# Import centralized token configuration
from upstox_tokens import get_primary_token, get_headers

# Get access token from centralized config
ACCESS_TOKEN = get_primary_token()

# Filtering Configuration
TRADING_HOURS_FILTER = True
TRADING_START_TIME = "09:15"
TRADING_END_TIME = "15:30"
ROUND_PRICES = True  # Round all prices to whole numbers (no decimals)

# ================================
# UTILITY FUNCTIONS
# ================================

# Use centralized headers function
headers = get_headers(ACCESS_TOKEN)

def make_request(url, params=None):
    """Make HTTP request with error handling"""
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Request error: {e}")
        return None

def fetch_historical_data(instrument_key, from_date, to_date):
    """Fetch historical candle data from Upstox API"""
    print(f"📊 Fetching {TIMEFRAME} data for {instrument_key}")
    print(f"📅 Date range: {from_date} to {to_date}")

    # Use correct v3 API format: /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}
    # Try different unit names - "minute" was rejected, let's try alternatives
    if TIMEFRAME == "5minute":
        unit = "minutes"  # Try plural
        interval = "5"
    elif TIMEFRAME == "1minute":
        unit = "minutes"
        interval = "1"
    elif TIMEFRAME == "15minute":
        unit = "minutes"
        interval = "15"
    elif TIMEFRAME == "30minute":
        unit = "minutes"
        interval = "30"
    elif TIMEFRAME == "1hour":
        unit = "hours"  # Try plural
        interval = "1"
    elif TIMEFRAME == "1day":
        unit = "days"   # Try plural
        interval = "1"
    else:
        # Default to 5minute
        unit = "minutes"
        interval = "5"

    url = f"https://api.upstox.com/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}"
    params = None  # No query parameters needed

    # Clean output - remove debug info
    # print(f"🔍 DEBUG: Using v3 API: {url}")

    # Add delay to respect rate limits
    time.sleep(0.1)  # Reduced from 1.0s to 0.1s for better performance

    response = make_request(url, params)
    
    if response and response.get('status') == 'success':
        candles = response['data']['candles']
        print(f"✅ Retrieved {len(candles)} candles")
        return candles
    else:
        print("❌ Failed to fetch historical data")
        return None

def process_and_save_data(instrument_key, candles, from_date, to_date):
    """Process candle data and save to CSV"""
    if not candles:
        print("⚠️  No candles to process")
        return None

    from datetime import time as time_obj

    # Parse date range for filtering
    start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(to_date, "%Y-%m-%d").date()

    # Trading hours filter
    if TRADING_HOURS_FILTER:
        start_hour, start_minute = map(int, TRADING_START_TIME.split(':'))
        end_hour, end_minute = map(int, TRADING_END_TIME.split(':'))
        trading_start = time_obj(start_hour, start_minute)
        trading_end = time_obj(end_hour, end_minute)
    else:
        trading_start = time_obj(0, 0)
        trading_end = time_obj(23, 59)

    records = []
    filtered_count = 0

    print(f"🔄 Processing {len(candles)} candles...")

    for candle in candles:
        # Parse timestamp
        timestamp_str = candle[0]
        try:
            # Handle different timestamp formats
            if '+' in timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.split('+')[0])
            else:
                dt = datetime.fromisoformat(timestamp_str)
        except:
            # Fallback parsing
            dt = datetime.strptime(timestamp_str[:19], "%Y-%m-%dT%H:%M:%S")

        # Filter 1: Date range check
        candle_date = dt.date()
        if candle_date < start_date or candle_date > end_date:
            filtered_count += 1
            continue

        # Filter 2: Trading hours check
        candle_time = dt.time()
        if TRADING_HOURS_FILTER and (candle_time < trading_start or candle_time > trading_end):
            filtered_count += 1
            continue

        # Apply price rounding (round to whole numbers, no decimals)
        idx_open = round(candle[1]) if ROUND_PRICES else candle[1]
        idx_high = round(candle[2]) if ROUND_PRICES else candle[2]
        idx_low = round(candle[3]) if ROUND_PRICES else candle[3]
        idx_close = round(candle[4]) if ROUND_PRICES else candle[4]

        # Format date and time as requested
        date_str = candle_date.strftime("%Y-%m-%d")  # YYYY-MM-DD
        time_str = candle_time.strftime("%H:%M:%S")  # HH:MM:SS

        record = {
            'symbol': INDEX_TYPE,
            'date': date_str,
            'time': time_str,
            'idx_open': idx_open,
            'idx_high': idx_high,
            'idx_low': idx_low,
            'idx_close': idx_close
        }
        records.append(record)

    print(f"✅ Processed {len(records)} valid records")
    print(f"🔄 Filtered out {filtered_count} records")

    if records:
        # Create DataFrame
        df = pd.DataFrame(records)

        # Auto-sort by date and time
        print(f"🔄 Auto-sorting {len(records)} records by date and time...")
        df['datetime_combined'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df = df.sort_values('datetime_combined')
        df = df.drop('datetime_combined', axis=1)
        df = df.reset_index(drop=True)

        # Show date range after sorting
        first_datetime = f"{df.iloc[0]['date']} {df.iloc[0]['time']}"
        last_datetime = f"{df.iloc[-1]['date']} {df.iloc[-1]['time']}"
        print(f"📊 Data range: {first_datetime} to {last_datetime}")

        # Create filename
        csv_filename = f"data/{INDEX_TYPE}_index_{TIMEFRAME}_{from_date}_{to_date}.csv"

        # Save to CSV
        df.to_csv(csv_filename, index=False)
        print(f"💾 Saved to: {csv_filename}")
        print(f"✅ Data automatically sorted chronologically")

        # Show sample data with final column format (no volume/OI for index data)
        print(f"\n📊 Sample data (first 3 rows):")
        print(df[['symbol', 'date', 'time', 'idx_open', 'idx_high', 'idx_low', 'idx_close']].head(3).to_string(index=False))

        return csv_filename
    else:
        print("⚠️  No records to save after filtering")
        return None

def validate_dates(start_date, end_date):
    """Validate date format and range"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        today = datetime.now()

        # Check if end date is in the future
        if end.date() > today.date():
            print(f"⚠️  END_DATE ({end_date}) is in the future!")
            print(f"📅 Today is {today.date()}")
            return False

        # Check if start date is after end date
        if start > end:
            print(f"❌ START_DATE ({start_date}) is after END_DATE ({end_date})")
            return False

        return True

    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print(f"💡 Use YYYY-MM-DD format (e.g., 2025-01-16)")
        return False

def main():
    """Main execution function"""
    print("=" * 70)
    print("📈 UPSTOX INDEX DATA EXTRACTOR (CSV OUTPUT)")
    print("=" * 70)
    print(f"📅 Period: {START_DATE} to {END_DATE}")
    print(f"⏰ Timeframe: {TIMEFRAME}")
    print(f"🎯 Index: {INDEX_TYPE}")
    print(f"⏰ Trading Hours Filter: {TRADING_HOURS_FILTER}")
    if TRADING_HOURS_FILTER:
        print(f"   Trading Hours: {TRADING_START_TIME} to {TRADING_END_TIME}")
    print(f"💰 Price Rounding: {ROUND_PRICES}")
    print("=" * 70)

    # Validate dates
    if not validate_dates(START_DATE, END_DATE):
        print("\n❌ Date validation failed. Please fix the dates.")
        return

    # Create output directory
    os.makedirs("data", exist_ok=True)

    try:
        # Fetch historical data
        candles = fetch_historical_data(INSTRUMENT_KEY, START_DATE, END_DATE)

        if candles:
            # Process and save data
            csv_file = process_and_save_data(INSTRUMENT_KEY, candles, START_DATE, END_DATE)
            
            if csv_file:
                print(f"\n✅ Data extraction complete!")
                print(f"📁 File saved: {csv_file}")
            else:
                print("\n⚠️  No data to save after filtering")
        else:
            print("\n❌ No data retrieved from API")

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

    print("\n🔒 Extraction complete")

if __name__ == "__main__":
    main()
