"""
Upstox Token Configuration File
===============================
Centralized token management for all Upstox data extractors.
Update your tokens here and all extractors will use them automatically.
"""

# ================================
# SINGLE TOKEN CONFIGURATION
# ================================
# Primary token used by single-token extractors
PRIMARY_ACCESS_TOKEN = 'XXXXXXXXXXX'

# ================================
# MULTI-TOKEN CONFIGURATION
# ================================
# Multiple tokens for multi-token extractors (for better rate limits)
# Using your existing 4 tokens from the multi-token extractor
MULTI_ACCESS_TOKENS = [
    # Token 1
     
    # Token 2
 
    # Token 3
 
    # Token 4
 
    # Add more tokens as needed...
]

# ================================
# TOKEN VALIDATION
# ================================
def validate_tokens():
    """Validate that tokens are properly configured"""
    issues = []
    
    # Check primary token
    if not PRIMARY_ACCESS_TOKEN or PRIMARY_ACCESS_TOKEN == 'your_token_here':
        issues.append("❌ PRIMARY_ACCESS_TOKEN not configured")
    elif len(PRIMARY_ACCESS_TOKEN) < 100:
        issues.append("⚠️  PRIMARY_ACCESS_TOKEN looks too short")
    
    # Check multi tokens
    valid_multi_tokens = [token for token in MULTI_ACCESS_TOKENS if token and not token.startswith('your_')]
    
    if len(valid_multi_tokens) == 0:
        issues.append("❌ No valid tokens in MULTI_ACCESS_TOKENS")
    elif len(valid_multi_tokens) == 1:
        issues.append("⚠️  Only 1 token in MULTI_ACCESS_TOKENS (multi-token won't help)")
    
    return issues, valid_multi_tokens

def get_primary_token():
    """Get the primary access token for single-token extractors"""
    return PRIMARY_ACCESS_TOKEN

def get_multi_tokens():
    """Get valid multi-access tokens for multi-token extractors"""
    issues, valid_tokens = validate_tokens()
    
    if issues:
        print("🔑 TOKEN CONFIGURATION ISSUES:")
        for issue in issues:
            print(f"   {issue}")
        print()
    
    return valid_tokens

def get_headers(token=None):
    """Get standard headers with specified token or primary token"""
    if token is None:
        token = PRIMARY_ACCESS_TOKEN
    
    return {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}'
    }

# ================================
# TOKEN INFORMATION
# ================================
def show_token_info():
    """Display token configuration information"""
    issues, valid_multi_tokens = validate_tokens()
    
    print("🔑 TOKEN CONFIGURATION STATUS")
    print("=" * 50)
    
    # Primary token status
    if PRIMARY_ACCESS_TOKEN and PRIMARY_ACCESS_TOKEN != 'your_token_here':
        print(f"✅ Primary Token: Configured ({len(PRIMARY_ACCESS_TOKEN)} chars)")
    else:
        print("❌ Primary Token: Not configured")
    
    # Multi-token status
    print(f"📊 Multi-Tokens: {len(valid_multi_tokens)} valid tokens")
    for i, token in enumerate(valid_multi_tokens, 1):
        print(f"   Token #{i}: {token[:20]}...{token[-10:]} ({len(token)} chars)")
    
    # Rate limit calculation
    if len(valid_multi_tokens) > 1:
        total_rate_limit = len(valid_multi_tokens) * 1800  # 1800 req/30min per token
        print(f"🚀 Effective Rate Limit: {total_rate_limit} req/30min")
        print(f"   ({len(valid_multi_tokens)} tokens × 1800 req/30min each)")
    
    # Issues
    if issues:
        print("\n⚠️  ISSUES TO FIX:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ All tokens properly configured!")
    
    print("=" * 50)

# ================================
# USAGE INSTRUCTIONS
# ================================
"""
HOW TO USE THIS FILE:
====================

1. UPDATE YOUR TOKENS:
   - Replace PRIMARY_ACCESS_TOKEN with your main Upstox token
   - Add additional tokens to MULTI_ACCESS_TOKENS list
   - Remove the # comments from token lines

2. SINGLE-TOKEN EXTRACTORS WILL USE:
   - PRIMARY_ACCESS_TOKEN

3. MULTI-TOKEN EXTRACTORS WILL USE:
   - All valid tokens from MULTI_ACCESS_TOKENS list

4. TO CHECK YOUR CONFIGURATION:
   python -c "from upstox_tokens import show_token_info; show_token_info()"

5. EXAMPLE CONFIGURATION:
   PRIMARY_ACCESS_TOKEN = 'eyJ0eXAiOiJKV1Q...'
   
   MULTI_ACCESS_TOKENS = [
       'eyJ0eXAiOiJKV1Q...',  # Token 1
       'eyJ0eXAiOiJKV1Q...',  # Token 2  
       'eyJ0eXAiOiJKV1Q...',  # Token 3
   ]

6. SECURITY NOTE:
   - Keep this file secure and don't share it
   - Add upstox_tokens.py to .gitignore if using version control
   - Tokens expire periodically and need to be refreshed
"""

if __name__ == "__main__":
    # Show token info when run directly
    show_token_info()
