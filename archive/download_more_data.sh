#!/bin/bash

echo "📥 DOWNLOADING MORE HISTORICAL DATA"
echo "===================================="
echo ""
echo "Option A: Download from TwelveData (5000 bars)"
echo "Option B: Manual download from HistData.com"
echo ""
echo "Preparing download script..."

cat > download_5000_bars.py << 'PYEOF'
import pandas as pd
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / 'bot-a' / '.env.botA')

api_key = os.getenv('TWELVEDATA_API_KEY')

print("📥 Fetching 5000 hours...")

url = "https://api.twelvedata.com/time_series"
params = {
    'symbol': 'EUR/USD',
    'interval': '1h',
    'outputsize': 5000,
    'apikey': api_key
}

try:
    response = requests.get(url, params=params, timeout=60)
    data = response.json()
    
    if 'values' in data:
        df = pd.DataFrame(data['values'])
        df = df.iloc[::-1]
        
        output_file = Path.home() / 'bot-a' / 'data' / 'EURUSD_H1_5000.csv'
        df.to_csv(output_file, index=False)
        
        print(f"✅ Downloaded {len(df)} bars")
        print(f"📊 Range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
        print(f"📁 Saved to: {output_file}")
    else:
        print(f"❌ API Error: {data}")
except Exception as e:
    print(f"❌ Download failed: {e}")
    print("\nAlternative: Download from HistData.com")
    print("https://www.histdata.com/download-free-forex-data/")
PYEOF

python3 download_5000_bars.py
