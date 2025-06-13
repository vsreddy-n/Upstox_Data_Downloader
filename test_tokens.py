#!/usr/bin/env python3
"""
Test script to verify token configuration
"""

from upstox_tokens import show_token_info, get_primary_token, get_multi_tokens

def main():
    print("🔑 TESTING CENTRALIZED TOKEN CONFIGURATION")
    print("=" * 60)
    
    # Show token configuration
    show_token_info()
    
    # Test primary token
    print("\n🧪 TESTING PRIMARY TOKEN:")
    primary = get_primary_token()
    if primary:
        print(f"✅ Primary token loaded: {primary[:20]}...{primary[-10:]}")
    else:
        print("❌ Primary token not loaded")
    
    # Test multi tokens
    print("\n🧪 TESTING MULTI TOKENS:")
    multi = get_multi_tokens()
    if multi:
        print(f"✅ Multi tokens loaded: {len(multi)} tokens")
        for i, token in enumerate(multi, 1):
            print(f"   Token #{i}: {token[:20]}...{token[-10:]}")
    else:
        print("❌ Multi tokens not loaded")
    
    print("\n" + "=" * 60)
    print("✅ Token configuration test complete!")

if __name__ == "__main__":
    main()
