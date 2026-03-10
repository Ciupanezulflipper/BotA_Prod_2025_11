#!/usr/bin/env python3
"""
Walk-forward backtest framework - Ready for Saturday implementation
"""

import pandas as pd
from datetime import datetime
import sys

def download_instructions():
    """Show where to get data"""
    print("📥 STEP 1: DOWNLOAD DATA")
    print("="*60)
    print("Go to: https://www.histdata.com/download-free-forex-data/")
    print("Select: EURUSD / ASCII / 1 Hour / 2020-2025")
    print("Save to: ~/bot-a/data/EURUSD_H1.csv")
    print("")

def prep_workspace():
    """Create needed directories"""
    from pathlib import Path
    
    data_dir = Path.home() / "bot-a" / "data"
    data_dir.mkdir(exist_ok=True)
    
    results_dir = Path.home() / "bot-a" / "backtest_results"
    results_dir.mkdir(exist_ok=True)
    
    print("✅ Directories created:")
    print(f"   Data: {data_dir}")
    print(f"   Results: {results_dir}")

def test_data_loading():
    """Test if we can load data"""
    from pathlib import Path
    
    data_file = Path.home() / "bot-a" / "data" / "EURUSD_H1.csv"
    
    if data_file.exists():
        print("✅ Found data file!")
        try:
            df = pd.read_csv(data_file, nrows=5)
            print(f"✅ Sample loaded: {len(df)} rows")
            print(df.head())
        except Exception as e:
            print(f"❌ Error loading: {e}")
    else:
        print("⚠️ Data file not found (expected - download tomorrow)")
        print(f"   Expected location: {data_file}")

if __name__ == "__main__":
    print("🧪 BACKTEST V2 FRAMEWORK")
    print("="*60)
    print("")
    
    download_instructions()
    prep_workspace()
    print("")
    test_data_loading()
    
    print("")
    print("="*60)
    print("✅ Framework ready for tomorrow!")
    print("⏰ Tomorrow's tasks:")
    print("   1. Download data (30 min)")
    print("   2. Implement strategies (90 min)")
    print("   3. Run backtests (60 min)")
    print("   4. Analyze results (60 min)")
    print("="*60)
