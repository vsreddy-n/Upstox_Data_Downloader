# Upstox Data Extraction Workflow

## 📋 Overview

This system provides automated data extraction from Upstox API for:
- **Index Data** (Nifty 50, Bank Nifty, etc.)
- **Options Data** (Call/Put options)
- **Futures Data** (Index futures)

All extractors automatically handle:
- ✅ Token management
- ✅ Rate limiting
- ✅ Data sorting (chronological)
- ✅ Value rounding (no decimals)
- ✅ CSV output formatting

---

## 🔄 Recommended Workflow Sequence

### Step 1: Initial Setup (One-Time)
1. **Configure Tokens** (see Token Management section below)
2. **Test Token Configuration** with `python test_tokens.py`

### Step 2: Data Extraction (Recommended Order)
1. **Index Data** → Extract first (fastest, single API call)
2. **Options Data** → Extract second (moderate complexity)
3. **Futures Data** → Extract last (most complex, automatic expiry handling)

### Step 3: Verification
1. **Check output files** in `data/` folder
2. **Verify data completeness** using terminal output
3. **Backup important datasets**

---

## 🔑 Token Management

### Setup Tokens (One-Time)
1. Edit `upstox_tokens.py`
2. Update your API tokens:
```python
PRIMARY_ACCESS_TOKEN = 'your_primary_token'
MULTI_ACCESS_TOKENS = [
    'token_1',
    'token_2',
    'token_3',
    'token_4'
]
```

### Test Token Configuration
```bash
python test_tokens.py
```

---

## 📈 Index Data Extraction

### Purpose
Extract index price data (OHLC) for analysis.

### Configuration
Edit `upstox_index_extractor.py`:
```python
START_DATE = "2025-01-13"
END_DATE = "2025-01-17"
TIMEFRAME = "5minute"  # 1minute, 5minute, 15minute, 30minute, 1hour, 1day
INDEX_TYPE = "NIFTY_50"  # NIFTY_50, BANK_NIFTY, SENSEX, etc.
```

### Run Extraction
```bash
python upstox_index_extractor.py
```

### Output
- **File**: `data/NIFTY_50_index_5minute_2025-01-13_2025-01-17.csv`
- **Columns**: `symbol, date, time, idx_open, idx_high, idx_low, idx_close`
- **Format**: Sorted chronologically, whole numbers only

---

## 📊 Options Data Extraction

### Purpose
Extract options chain data (Call/Put) for trading analysis.

### Configuration
Edit `upstox_options_extractor.py`:
```python
USER_START_DATE = "2025-01-13"
USER_END_DATE = "2025-01-17"
TIMEFRAME = "5minute"
INDEX_TYPE = "NIFTY_50"
```

### Run Extraction
```bash
python upstox_options_extractorm.py
```

### Output
- **File**: `data/NIFTY_50_OPTIONS_5minute_2025-01-13_2025-01-17_historical_data.csv`
- **Columns**: `symbol, date, time, strikeprice, expirydate, option_type, open, high, low, close, opt_vol, opt_oi`
- **Format**: Sorted chronologically, whole numbers only

---

## 🔮 Futures Data Extraction

### Purpose
Extract futures contract data with automatic expiry selection.

### Configuration
Edit `upstox_futures_extractor.py`:
```python
USER_START_DATE = "2025-04-15"  # Your desired start date
USER_END_DATE = "2025-05-15"    # Your desired end date
TIMEFRAME = "5minute"
INDEX_TYPE = "NIFTY_50"
```

### ⚠️ Important: Futures Expiry Management

**AUTOMATIC EXPIRY HANDLING**: The system automatically fetches current expiry dates from Upstox API. No manual updates required for normal operation.

**MANUAL EXPIRY UPDATE (Only if API fails)**:
If the API expiry fetch fails, you may need to manually update `data/future_expiry_date.txt`:
1. Check NSE website for current futures expiry dates
2. Update the file with format: `DD MMM YYYY` (e.g., `30 JAN 2025`)
3. Include both monthly and weekly expiries
4. **Note**: This is a backup option - the system primarily uses API data

### How It Works
1. **Fetches all available expiry dates** from API automatically
2. **Finds relevant expiries** that cover your date range
3. **Prioritizes monthly expiries** (better liquidity)
4. **Automatically calculates periods**:
   - 15-Apr to 24-Apr → 24-Apr expiry
   - 25-Apr to 15-May → 29-May expiry

### Run Extraction
```bash
python upstox_futures_extractor.py
```

### Output
- **File**: `data/NIFTY_50_FUTURES_5minute_2025-04-15_2025-05-15_historical_data.csv`
- **Columns**: `symbol, date, time, fut_open, fut_high, fut_low, fut_close, fut_vol, fut_oi`
- **Format**: Sorted chronologically, whole numbers only
- **Additional Files**:
  - `*_expiry_dates.json` (selected expiry dates)
  - `*_instrument_keys.json` (futures instrument keys)

---

## ⚙️ Configuration Options

### Index Types
```python
INDEX_TYPE = "NIFTY_50"      # Nifty 50
INDEX_TYPE = "BANK_NIFTY"    # Bank Nifty
INDEX_TYPE = "SENSEX"        # BSE Sensex
INDEX_TYPE = "NIFTY_IT"      # Nifty IT
INDEX_TYPE = "NIFTY_PHARMA"  # Nifty Pharma
```

### Timeframes
```python
# Index Data (v3 API)
TIMEFRAME = "1minute"   # 1-minute candles
TIMEFRAME = "5minute"   # 5-minute candles  
TIMEFRAME = "15minute"  # 15-minute candles
TIMEFRAME = "30minute"  # 30-minute candles
TIMEFRAME = "1hour"     # 1-hour candles
TIMEFRAME = "1day"      # Daily candles

# Options/Futures Data (v2 API)
TIMEFRAME = "1minute"   # 1-minute candles
TIMEFRAME = "5minute"   # 5-minute candles
TIMEFRAME = "15minute"  # 15-minute candles
TIMEFRAME = "1day"      # Daily candles
```

### Trading Hours Filter
```python
TRADING_HOURS_FILTER = True   # Filter to market hours only
TRADING_START_TIME = "09:15"  # Market open
TRADING_END_TIME = "15:30"    # Market close
```

---

## 🚀 Performance Features

### Multi-Token Support
- **Single Token**: 1800 requests/30min
- **Multi-Token**: 4 × 1800 = 7200 requests/30min
- **Speed**: Up to 4x faster extraction

### Rate Limiting
- **Automatic**: Built-in rate limit management
- **Safe**: Conservative limits to avoid 429 errors
- **Smart**: Token rotation when limits approached

### Optimizations
- **HTTPx**: Faster HTTP client with connection pooling
- **Sequential**: Safe processing to ensure zero data loss
- **Auto-sorting**: Chronological data ordering
- **Auto-rounding**: Whole number formatting

---

## 📁 File Structure

```
06_upstox_data/
├── upstox_tokens.py                      # Token configuration
├── test_tokens.py                        # Token testing
├── upstox_index_extractor.py            # Index data extraction
├── upstox_options_extractor.py           # Options data extraction
├── upstox_futures_extractor.py          # Futures data extraction
└── data/                                 # Output folder
    ├── *.json                           # Expiry dates & instrument keys
    └── *.csv                            # Historical data
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Token Errors
```bash
# Test your tokens
python test_tokens.py

# Check token expiry and refresh if needed
```

#### 2. No Data Found
- **Check date range**: Ensure dates have trading data
- **Check timeframe**: Some timeframes may not be available
- **Check expiry dates**: For futures, check available expiries

#### 3. Rate Limit Errors
- **Reduce date range** for single token extractors
- **Wait between runs** if hitting limits

#### 4. API Endpoint Errors
- **Index data**: Uses v3 API (different timeframe support)
- **Options/Futures**: Uses v2 expired instruments API
- **Check instrument keys** are correct

#### 5. Futures Expiry Issues
- **API Fetch Failure**: If expiry dates can't be fetched from API, manually update `data/future_expiry_date.txt`
- **Date Format**: Use `DD MMM YYYY` format (e.g., `30 JAN 2025`)
- **Missing Expiries**: Check NSE website for latest futures expiry calendar
- **Backup File**: The manual file is only used when API fails

### Debug Information
All extractors show:
- ✅ Available expiry dates
- ✅ Selected date ranges
- ✅ Token usage statistics
- ✅ Processing progress
- ✅ Error details

---

## 📊 Output Format

### CSV Columns

#### Index Data
```csv
symbol,date,time,idx_open,idx_high,idx_low,idx_close
NIFTY_50,2025-01-17,09:15:00,23204,23208,23195,23203
```

#### Options Data
```csv
symbol,date,time,strikeprice,expirydate,option_type,open,high,low,close,opt_vol,opt_oi
NIFTY17JAN202523200CE,2025-01-17,09:15:00,23200,2025-01-17,CE,45,48,42,46,1250,15000
```

#### Futures Data
```csv
symbol,date,time,fut_open,fut_high,fut_low,fut_close,fut_vol,fut_oi
NIFTY24APR2025,2025-04-15,09:15:00,23295,23350,23252,23340,5000,25000
```

### Data Quality
- ✅ **Chronologically sorted** (oldest to newest)
- ✅ **Whole numbers only** (no decimals)
- ✅ **Complete coverage** of requested date range
- ✅ **Trading hours filtered** (09:15 to 15:30)

---

## 🎯 Best Practices

### 1. Execution Order
- **Follow recommended sequence**: Index → Options → Futures
- **Test with small date ranges** before large extractions
- **Verify each step** before proceeding to next

### 2. Date Selection
- **Use past dates** for reliable data availability
- **Check market holidays** before setting date ranges
- **Start with small ranges** for testing

### 3. Token Management
- **Use multiple tokens** for large extractions
- **Monitor token usage** in output logs
- **Refresh tokens** before expiry

### 4. Data Processing
- **Verify output files** after extraction
- **Check data completeness** using date ranges shown
- **Backup important datasets**

### 5. Futures Expiry Management
- **Let system auto-fetch** expiry dates from API
- **Only manually update** `data/future_expiry_date.txt` if API fails
- **Check NSE calendar** for accurate expiry dates when updating manually
- **Include both monthly and weekly** expiries in manual updates

---

## 📞 Support

For issues or questions:
1. **Follow the recommended workflow sequence** (Index → Options → Futures)
2. **Check troubleshooting section** above for common issues
3. **Review error messages** in terminal output carefully
4. **Test with smaller date ranges** first
5. **Verify token configuration** with `test_tokens.py`
6. **For futures issues**: Check if API expiry fetch failed and manually update if needed

### Quick Fixes
- **Token errors**: Run `python test_tokens.py`
- **No data**: Check date ranges and market holidays
- **Futures expiry**: Let API auto-fetch, manual update only if API fails

---

*Last Updated: January 2025*
