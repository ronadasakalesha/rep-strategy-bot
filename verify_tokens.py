import json
import os

def verify_tokens():
    file_path = "fno_tokens.json"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, 'r') as f:
        tokens = json.load(f)

    print(f"Total Tokens found: {len(tokens)}")

    # Check for sample FNO stocks
    samples = ["RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN", "IDEA", "BHEL", "ZEEL", "CANBK", "PNB"]
    
    missing = []
    found_symbols = [t['symbol'] for t in tokens]
    
    for s in samples:
        if s in found_symbols:
            print(f"✅ Found: {s}")
        else:
            print(f"❌ Missing: {s}")
            missing.append(s)
            
    if not missing:
        print("\nSUCCESS: All sample FNO stocks found.")
    else:
        print(f"\nWARNING: Missing stocks: {missing}")

if __name__ == "__main__":
    verify_tokens()
