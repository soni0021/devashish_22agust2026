# Google Colab System Prompt: Store Monitoring Data Processing (Part 1/3)
# 
# This script implements the data processing pipeline for a restaurant store monitoring system.
# It handles CSV data loading, validation, timezone conversions, and preparation for uptime/downtime calculations.
#
# To use in Google Colab:
# 1. Upload this script to Colab
# 2. Upload the three CSV files: store_status.csv, menu_hours.csv, timezones.csv
# 3. Run each cell sequentially

# ============================================================================
# CELL 1: Install Required Libraries
# ============================================================================

# Install additional libraries not available in Colab by default
# !pip install pytz zoneinfo-backport
# !pip install pandas numpy matplotlib seaborn
# !pip install sqlalchemy

# Import all necessary libraries
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time, date, timedelta
import uuid
import logging
import warnings
from typing import Dict, List, Tuple, Optional
import json
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import os

# Configure logging for Colab
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

print("✅ All libraries imported successfully!")
print("📊 Pandas version:", pd.__version__)
print("🕒 Pytz version:", pytz.__version__)

# ============================================================================
# CELL 2: Download and Prepare Data Files
# ============================================================================

# For this demo, we'll work with the uploaded CSV files
# In real scenario, download from the provided Google Storage link

# Option 1: Upload files manually to Colab
# from google.colab import files
# print("📁 Please upload your CSV files:")
# print("1. store_status.csv")
# print("2. menu_hours.csv") 
# print("3. timezones.csv")

# Uncomment to upload files
# uploaded = files.upload()

# Option 2: Download from URL (if provided)
import requests
import zipfile
import io

def download_and_extract_data(url: str, extract_path: str = './data/'):
    """Download and extract ZIP file from URL"""
    try:
        print(f"🔄 Downloading data from {url}")
        response = requests.get(url)
        
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(extract_path)
            print(f"✅ Data extracted to {extract_path}")
            return True
        else:
            print(f"❌ Failed to download. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        return False

# If you have the ZIP URL, use this:
# data_url = "https://storage.googleapis.com/hiring-problem-statements/store-monitoring-data.zip"
# download_and_extract_data(data_url)

# Create sample data directory
os.makedirs('./data/', exist_ok=True)
print("📂 Data directory created: ./data/")

# ============================================================================
# CELL 3: Define Data Loading Functions
# ============================================================================

class DataValidator:
    """Data validation utilities for store monitoring system"""
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """Validate if string is a valid UUID"""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_timezone(tz_string: str) -> bool:
        """Validate if timezone string is valid"""
        try:
            pytz.timezone(tz_string)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False
    
    @staticmethod
    def validate_time_format(time_string: str) -> bool:
        """Validate HH:MM:SS time format"""
        try:
            datetime.strptime(time_string, '%H:%M:%S')
            return True
        except ValueError:
            return False

def load_store_status(file_path: str) -> pd.DataFrame:
    """
    Load and validate store status data
    Expected columns: store_id, timestamp_utc, status
    """
    try:
        print(f"📖 Loading store status data from {file_path}")
        df = pd.read_csv(file_path)
        
        # Basic validation
        expected_columns = ['store_id', 'timestamp_utc', 'status']
        if not all(col in df.columns for col in expected_columns):
            raise ValueError(f"Missing required columns. Expected: {expected_columns}")
        
        # Convert timestamp to datetime
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'], utc=True)
        
        # Validate status values
        valid_statuses = {'active', 'inactive'}
        invalid_statuses = set(df['status'].unique()) - valid_statuses
        if invalid_statuses:
            logger.warning(f"Found invalid status values: {invalid_statuses}")
        
        # Validate store IDs
        invalid_uuids = []
        for store_id in df['store_id'].unique():
            if not DataValidator.validate_uuid(store_id):
                invalid_uuids.append(store_id)
        
        if invalid_uuids:
            logger.warning(f"Found {len(invalid_uuids)} invalid store IDs")
        
        print(f"✅ Loaded {len(df)} status records for {df['store_id'].nunique()} unique stores")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load store status: {e}")
        raise

def load_business_hours(file_path: str) -> pd.DataFrame:
    """
    Load and validate business hours data
    Expected columns: store_id, dayOfWeek, start_time_local, end_time_local
    """
    try:
        print(f"📖 Loading business hours data from {file_path}")
        df = pd.read_csv(file_path)
        
        expected_columns = ['store_id', 'dayOfWeek', 'start_time_local', 'end_time_local']
        if not all(col in df.columns for col in expected_columns):
            raise ValueError(f"Missing required columns. Expected: {expected_columns}")
        
        # Validate day of week values (0-6)
        invalid_days = df[~df['dayOfWeek'].isin(range(7))]
        if not invalid_days.empty:
            logger.warning(f"Found {len(invalid_days)} records with invalid dayOfWeek values")
        
        # Validate time formats
        for col in ['start_time_local', 'end_time_local']:
            df[col] = pd.to_datetime(df[col], format='%H:%M:%S').dt.time
        
        print(f"✅ Loaded {len(df)} business hour records for {df['store_id'].nunique()} unique stores")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load business hours: {e}")
        raise

def load_store_timezones(file_path: str) -> pd.DataFrame:
    """
    Load and validate store timezone data
    Expected columns: store_id, timezone_str
    """
    try:
        print(f"📖 Loading store timezone data from {file_path}")
        df = pd.read_csv(file_path)
        
        expected_columns = ['store_id', 'timezone_str']
        if not all(col in df.columns for col in expected_columns):
            raise ValueError(f"Missing required columns. Expected: {expected_columns}")
        
        # Validate timezone strings
        invalid_timezones = []
        for tz in df['timezone_str'].unique():
            if not DataValidator.validate_timezone(tz):
                invalid_timezones.append(tz)
        
        if invalid_timezones:
            logger.warning(f"Found invalid timezones: {invalid_timezones}")
        
        print(f"✅ Loaded timezone data for {len(df)} unique stores")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load store timezones: {e}")
        raise

print("✅ Data loading functions defined successfully!")

# ============================================================================
# CELL 4: Load All Data Files
# ============================================================================

# Define file paths (adjust these based on your uploaded files)
file_paths = {
    'status': 'store_status.csv',
    'business_hours': 'menu_hours.csv', 
    'timezones': 'timezones.csv'
}

# Alternative: if files are in data directory
# file_paths = {
#     'status': './data/store_status.csv',
#     'business_hours': './data/menu_hours.csv',
#     'timezones': './data/timezones.csv'
# }

# Load all data
try:
    # Load each dataset
    df_status = load_store_status(file_paths['status'])
    df_business_hours = load_business_hours(file_paths['business_hours'])
    df_timezones = load_store_timezones(file_paths['timezones'])
    
    print("\n" + "="*50)
    print("📊 DATA LOADING SUMMARY")
    print("="*50)
    print(f"Status records: {len(df_status):,}")
    print(f"Business hour records: {len(df_business_hours):,}")
    print(f"Timezone records: {len(df_timezones):,}")
    print(f"Unique stores in status data: {df_status['store_id'].nunique():,}")
    print(f"Unique stores in business hours: {df_business_hours['store_id'].nunique():,}")
    print(f"Unique stores in timezone data: {df_timezones['store_id'].nunique():,}")
    
    # Check data date ranges
    print(f"\nStatus data date range:")
    print(f"  From: {df_status['timestamp_utc'].min()}")
    print(f"  To: {df_status['timestamp_utc'].max()}")
    
except Exception as e:
    print(f"❌ Error loading data: {e}")
    print("Please check your file paths and data format") 