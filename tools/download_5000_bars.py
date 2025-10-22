import pandas as pd
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / 'bot-a' / '.env.botA')

api_key = os.getenv('TWELVEDATA_API_KEY')

print("📥 Downloading 5000 hours of EURUSD data...")
print("⏱️ This will take 30-60 seconds...")
print("")

url = "https://api.twelvedata.com/time_series"
params = {
    'symbol': 'EUR/USD',
    'interval': '1h',
    'outputsize': 5000,
    'apikey': api_key
}

try:
    response = requests.get(url, params=params, timeout=90)
    data = response.json()
    
    if 'values' in data:
        df = pd.DataFrame(data['values'])
        df = df.iloc[::-1]  # Reverse chronological
        
        output_file = Path.home() / 'bot-a' / 'data' / 'EURUSD_H1_5000.csv'
        df.to_csv(output_file, index=False)
        
        print(f"✅ Downloaded {len(df)} bars")
        print(f"📊 Range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
        print(f"📁 File: {output_file}")
        print("")
        print("🎯 Ready for extended backtest!")
    else:
        print(f"❌ API Error: {data}")
        print("\nTry again later or use HistData.com")
except Exception as e:
    print(f"❌ Error: {e}")
