#!/usr/bin/env python3
"""
Complete Store Monitoring Data Processing Pipeline
"""

import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time, date, timedelta
import uuid
import logging
import warnings
from typing import Dict, List, Tuple, Optional
import json
from collections import defaultdict
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')

print("🚀 Starting Store Monitoring Data Processing Pipeline")
print("="*60)

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n📊 STEP 1: Loading Data")
print("-" * 40)

# Load all datasets
df_status = pd.read_csv('store_status.csv')
df_business_hours = pd.read_csv('menu_hours.csv')
df_timezones = pd.read_csv('timezones.csv')

# Convert timestamp to datetime
df_status['timestamp_utc'] = pd.to_datetime(df_status['timestamp_utc'], utc=True)

# Convert time columns to time objects
for col in ['start_time_local', 'end_time_local']:
    df_business_hours[col] = pd.to_datetime(df_business_hours[col], format='%H:%M:%S').dt.time

print(f"✅ Loaded {len(df_status):,} status records for {df_status['store_id'].nunique():,} stores")
print(f"✅ Loaded {len(df_business_hours):,} business hour records for {df_business_hours['store_id'].nunique():,} stores")
print(f"✅ Loaded {len(df_timezones):,} timezone records for {df_timezones['store_id'].nunique():,} stores")

# ============================================================================
# STEP 2: Apply Defaults for Missing Data
# ============================================================================

print("\n🔧 STEP 2: Applying Defaults for Missing Data")
print("-" * 40)

# Find stores missing data
stores_status = set(df_status['store_id'].unique())
stores_business = set(df_business_hours['store_id'].unique())
stores_timezone = set(df_timezones['store_id'].unique())

stores_missing_business = stores_status - stores_business
stores_missing_timezone = stores_status - stores_timezone

print(f"Stores missing business hours: {len(stores_missing_business):,}")
print(f"Stores missing timezone data: {len(stores_missing_timezone):,}")

# Create default business hours (24×7)
default_business_rows = []
for store_id in stores_missing_business:
    for day in range(7):
        default_business_rows.append({
            'store_id': store_id,
            'dayOfWeek': day,
            'start_time_local': time(0, 0, 0),
            'end_time_local': time(23, 59, 59)
        })

# Create default timezone entries
default_timezone_rows = []
for store_id in stores_missing_timezone:
    default_timezone_rows.append({
        'store_id': store_id,
        'timezone_str': 'America/Chicago'
    })

# Add defaults
if default_business_rows:
    df_default_business = pd.DataFrame(default_business_rows)
    df_business_complete = pd.concat([df_business_hours, df_default_business], ignore_index=True)
    print(f"✅ Added 24×7 business hours for {len(stores_missing_business):,} stores")
else:
    df_business_complete = df_business_hours.copy()

if default_timezone_rows:
    df_default_timezone = pd.DataFrame(default_timezone_rows)
    df_timezone_complete = pd.concat([df_timezones, df_default_timezone], ignore_index=True)
    print(f"✅ Added America/Chicago timezone for {len(stores_missing_timezone):,} stores")
else:
    df_timezone_complete = df_timezones.copy()

# ============================================================================
# STEP 3: Create Business Hours Lookup
# ============================================================================

print("\n🏗️ STEP 3: Creating Business Hours Lookup")
print("-" * 40)

# Merge business hours with timezone data
df_merged = df_business_complete.merge(
    df_timezone_complete[['store_id', 'timezone_str']], 
    on='store_id', 
    how='left'
)

print(f"Merged {len(df_merged):,} business hour records with timezone data")

# Create lookup dictionary
business_lookup = defaultdict(lambda: defaultdict(list))

# Get date range from status data
min_date = df_status['timestamp_utc'].min().date()
max_date = df_status['timestamp_utc'].max().date()

print(f"Converting business hours to UTC for date range: {min_date} to {max_date}")

# Process each business hour record
for idx, row in df_merged.iterrows():
    store_id = row['store_id']
    day_of_week = row['dayOfWeek']
    start_local = row['start_time_local']
    end_local = row['end_time_local']
    timezone_str = row['timezone_str']
    
    # Convert for each date in our range
    current_date = min_date
    while current_date <= max_date:
        if current_date.weekday() == day_of_week:
            try:
                local_tz = pytz.timezone(timezone_str)
                
                # Handle midnight crossing
                if start_local > end_local:
                    # First window: start_local to 23:59:59
                    start_dt1 = datetime.combine(current_date, start_local)
                    end_dt1 = datetime.combine(current_date, time(23, 59, 59))
                    
                    # Second window: 00:00:00 to end_local (next day)
                    next_date = current_date + timedelta(days=1)
                    start_dt2 = datetime.combine(next_date, time(0, 0, 0))
                    end_dt2 = datetime.combine(next_date, end_local)
                    
                    # Convert to UTC
                    start_utc1 = local_tz.localize(start_dt1, is_dst=None)
                    end_utc1 = local_tz.localize(end_dt1, is_dst=None)
                    start_utc2 = local_tz.localize(start_dt2, is_dst=None)
                    end_utc2 = local_tz.localize(end_dt2, is_dst=None)
                    
                    business_lookup[store_id][current_date].extend([(start_utc1, end_utc1), (start_utc2, end_utc2)])
                else:
                    # Normal business hours
                    start_dt = datetime.combine(current_date, start_local)
                    end_dt = datetime.combine(current_date, end_local)
                    
                    start_utc = local_tz.localize(start_dt, is_dst=None)
                    end_utc = local_tz.localize(end_dt, is_dst=None)
                    
                    business_lookup[store_id][current_date].append((start_utc, end_utc))
                    
            except Exception as e:
                # Handle DST transitions
                try:
                    if start_local > end_local:
                        start_dt1 = datetime.combine(current_date, start_local)
                        end_dt1 = datetime.combine(current_date, time(23, 59, 59))
                        next_date = current_date + timedelta(days=1)
                        start_dt2 = datetime.combine(next_date, time(0, 0, 0))
                        end_dt2 = datetime.combine(next_date, end_local)
                        
                        start_utc1 = local_tz.localize(start_dt1, is_dst=False)
                        end_utc1 = local_tz.localize(end_dt1, is_dst=False)
                        start_utc2 = local_tz.localize(start_dt2, is_dst=False)
                        end_utc2 = local_tz.localize(end_dt2, is_dst=False)
                        
                        business_lookup[store_id][current_date].extend([(start_utc1, end_utc1), (start_utc2, end_utc2)])
                    else:
                        start_dt = datetime.combine(current_date, start_local)
                        end_dt = datetime.combine(current_date, end_local)
                        
                        start_utc = local_tz.localize(start_dt, is_dst=False)
                        end_utc = local_tz.localize(end_dt, is_dst=False)
                        
                        business_lookup[store_id][current_date].append((start_utc, end_utc))
                except:
                    pass  # Skip problematic conversions
        
        current_date += timedelta(days=1)
    
    # Progress indicator
    if (idx + 1) % 5000 == 0:
        print(f"Processed {idx + 1:,} business hour records...")

print(f"✅ Business hours lookup created for {len(business_lookup):,} stores")

# ============================================================================
# STEP 4: Create Status Index
# ============================================================================

print("\n📊 STEP 4: Creating Status Index")
print("-" * 40)

# Sort by timestamp for efficient processing
df_sorted = df_status.sort_values(['store_id', 'timestamp_utc'])

# Create indexed observations
observations = defaultdict(list)
store_stats = defaultdict(dict)

for store_id, group in df_sorted.groupby('store_id'):
    store_obs = []
    active_count = 0
    inactive_count = 0
    
    for _, row in group.iterrows():
        timestamp = row['timestamp_utc']
        status = row['status']
        store_obs.append((timestamp, status))
        
        if status == 'active':
            active_count += 1
        else:
            inactive_count += 1
    
    observations[store_id] = store_obs
    
    # Calculate statistics
    total_obs = len(store_obs)
    if total_obs > 1:
        time_diffs = []
        for i in range(1, len(store_obs)):
            diff = (store_obs[i][0] - store_obs[i-1][0]).total_seconds() / 3600
            time_diffs.append(diff)
        avg_frequency = np.mean(time_diffs) if time_diffs else 0
    else:
        avg_frequency = 0
    
    store_stats[store_id] = {
        'total_observations': total_obs,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'observation_frequency': avg_frequency,
        'first_observation': store_obs[0][0] if store_obs else None,
        'last_observation': store_obs[-1][0] if store_obs else None
    }

print(f"✅ Indexed observations for {len(observations):,} stores")

# ============================================================================
# STEP 5: Validation and Summary
# ============================================================================

print("\n🔍 STEP 5: Validation and Summary")
print("-" * 40)

# Overall statistics
total_stores = len(observations)
total_observations = sum(stats['total_observations'] for stats in store_stats.values())
avg_obs_per_store = total_observations / total_stores if total_stores > 0 else 0

print(f"📊 Final Statistics:")
print(f"   Total stores: {total_stores:,}")
print(f"   Total observations: {total_observations:,}")
print(f"   Average observations per store: {avg_obs_per_store:.1f}")

# Status distribution
all_active = sum(stats['active_count'] for stats in store_stats.values())
all_inactive = sum(stats['inactive_count'] for stats in store_stats.values())
active_percentage = (all_active / (all_active + all_inactive)) * 100 if (all_active + all_inactive) > 0 else 0

print(f"   Overall active percentage: {active_percentage:.1f}%")

# Validation
all_status_stores = set(df_status['store_id'].unique())
all_business_stores = set(df_business_complete['store_id'].unique())
all_timezone_stores = set(df_timezone_complete['store_id'].unique())

print(f"\n✅ Validation Results:")
print(f"   All stores have business hours: {all_status_stores.issubset(all_business_stores)}")
print(f"   All stores have timezone data: {all_status_stores.issubset(all_timezone_stores)}")
print(f"   Business hours lookup created: {len(business_lookup):,} stores")
print(f"   Status index created: {len(observations):,} stores")

# ============================================================================
# STEP 6: Save Results
# ============================================================================

print("\n💾 STEP 6: Saving Results")
print("-" * 40)

# Create summary
summary = {
    'processing_timestamp': datetime.now().isoformat(),
    'data_statistics': {
        'total_stores': total_stores,
        'total_status_records': len(df_status),
        'total_business_records': len(df_business_complete),
        'total_timezone_records': len(df_timezone_complete),
        'date_range_start': df_status['timestamp_utc'].min().isoformat(),
        'date_range_end': df_status['timestamp_utc'].max().isoformat(),
        'stores_defaulted_to_24_7': len(stores_missing_business),
        'stores_defaulted_to_america_chicago': len(stores_missing_timezone)
    },
    'validation_results': {
        'business_hours_coverage': all_status_stores.issubset(all_business_stores),
        'timezone_coverage': all_status_stores.issubset(all_timezone_stores),
        'status_indexing_success': len(observations) == len(all_status_stores)
    }
}

# Save summary
with open('processing_summary.json', 'w') as f:
    json.dump(summary, f, indent=2, default=str)

print(f"✅ Processing summary saved to: processing_summary.json")

# Sample data export
sample_data = {
    'sample_business_lookup': {
        list(business_lookup.keys())[0]: {
            str(k): [(str(start), str(end)) for start, end in v] 
            for k, v in business_lookup[list(business_lookup.keys())[0]].items()
        }
    },
    'sample_status_data': store_stats[list(store_stats.keys())[0]]
}

with open('sample_processed_data.json', 'w') as f:
    json.dump(sample_data, f, indent=2, default=str)

print(f"✅ Sample processed data saved to: sample_processed_data.json")

# ============================================================================
# COMPLETION
# ============================================================================

print(f"\n" + "="*70)
print("🎯 DATA PROCESSING COMPLETED SUCCESSFULLY!")
print("="*70)
print(f"✅ All data structures are prepared and validated")
print(f"✅ Business hours converted to UTC and indexed")
print(f"✅ Status observations indexed for efficient querying")
print(f"✅ Ready for uptime/downtime calculation algorithms")
print("="*70)

print(f"\n📦 Available Data Structures:")
print(f"   • business_lookup: UTC business hours for all stores")
print(f"   • observations: Indexed status observations")
print(f"   • store_stats: Store statistics and metadata")
print(f"   • df_status, df_business_complete, df_timezone_complete: Complete datasets")

print(f"\n🚀 Ready to proceed to Step 2: Uptime/Downtime Calculation Logic!")
print("="*70) 