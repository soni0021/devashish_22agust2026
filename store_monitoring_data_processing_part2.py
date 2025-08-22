# Google Colab System Prompt: Store Monitoring Data Processing (Part 2/3)
# 
# This script continues the data processing pipeline with data quality analysis,
# default value application, and timezone conversion.

# ============================================================================
# CELL 5: Data Quality Analysis and Visualization
# ============================================================================

def analyze_data_quality(df_status, df_business_hours, df_timezones):
    """Comprehensive data quality analysis"""
    
    print("🔍 DATA QUALITY ANALYSIS")
    print("="*50)
    
    # Get unique store sets
    stores_status = set(df_status['store_id'].unique())
    stores_business = set(df_business_hours['store_id'].unique())
    stores_timezone = set(df_timezones['store_id'].unique())
    
    # Store coverage analysis
    print(f"Store Coverage Analysis:")
    print(f"  Stores in status data: {len(stores_status):,}")
    print(f"  Stores in business hours: {len(stores_business):,}")
    print(f"  Stores in timezone data: {len(stores_timezone):,}")
    
    # Find stores missing data
    stores_missing_business = stores_status - stores_business
    stores_missing_timezone = stores_status - stores_timezone
    
    print(f"\nMissing Data Analysis:")
    print(f"  Stores missing business hours: {len(stores_missing_business):,}")
    print(f"  Stores missing timezone data: {len(stores_missing_timezone):,}")
    
    if len(stores_missing_business) > 0:
        print(f"  → These will default to 24×7 operation")
    if len(stores_missing_timezone) > 0:
        print(f"  → These will default to America/Chicago timezone")
    
    # Status distribution
    status_counts = df_status['status'].value_counts()
    print(f"\nStatus Distribution:")
    for status, count in status_counts.items():
        percentage = (count / len(df_status)) * 100
        print(f"  {status}: {count:,} ({percentage:.1f}%)")
    
    # Timezone distribution
    print(f"\nTimezone Distribution:")
    tz_counts = df_timezones['timezone_str'].value_counts().head(10)
    for tz, count in tz_counts.items():
        percentage = (count / len(df_timezones)) * 100
        print(f"  {tz}: {count:,} ({percentage:.1f}%)")
    
    return {
        'stores_missing_business': stores_missing_business,
        'stores_missing_timezone': stores_missing_timezone,
        'status_distribution': status_counts,
        'timezone_distribution': tz_counts
    }

# Run data quality analysis
quality_report = analyze_data_quality(df_status, df_business_hours, df_timezones)

# Create visualizations
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Status distribution pie chart
status_counts = quality_report['status_distribution']
axes[0,0].pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%')
axes[0,0].set_title('Status Distribution')

# Timezone distribution bar chart
tz_counts = quality_report['timezone_distribution'].head(8)
axes[0,1].bar(range(len(tz_counts)), tz_counts.values)
axes[0,1].set_xticks(range(len(tz_counts)))
axes[0,1].set_xticklabels(tz_counts.index, rotation=45, ha='right')
axes[0,1].set_title('Top Timezones')
axes[0,1].set_ylabel('Number of Stores')

# Data coverage heatmap
coverage_data = [
    ['Status Data', len(df_status['store_id'].unique()), '100%'],
    ['Business Hours', len(df_business_hours['store_id'].unique()), 
     f"{(len(df_business_hours['store_id'].unique()) / len(df_status['store_id'].unique())) * 100:.1f}%"],
    ['Timezone Data', len(df_timezones['store_id'].unique()),
     f"{(len(df_timezones['store_id'].unique()) / len(df_status['store_id'].unique())) * 100:.1f}%"]
]

axes[1,0].axis('tight')
axes[1,0].axis('off')
table = axes[1,0].table(cellText=coverage_data, 
                       colLabels=['Data Type', 'Store Count', 'Coverage'],
                       cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
axes[1,0].set_title('Data Coverage Summary')

# Status observations over time
daily_counts = df_status.groupby(df_status['timestamp_utc'].dt.date).size()
axes[1,1].plot(daily_counts.index, daily_counts.values)
axes[1,1].set_title('Daily Status Observations')
axes[1,1].set_xlabel('Date')
axes[1,1].set_ylabel('Observation Count')
axes[1,1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()

print("✅ Data quality analysis completed!")

# ============================================================================
# CELL 6: Apply Default Values for Missing Data
# ============================================================================

def apply_data_defaults(df_status, df_business_hours, df_timezones):
    """
    Apply default values for stores missing business hours or timezone data
    """
    print("🔧 APPLYING DEFAULT VALUES")
    print("="*50)
    
    # Get all unique stores from status data
    all_stores = set(df_status['store_id'].unique())
    stores_with_business = set(df_business_hours['store_id'].unique())
    stores_with_timezone = set(df_timezones['store_id'].unique())
    
    # Find stores needing defaults
    stores_missing_business = all_stores - stores_with_business
    stores_missing_timezone = all_stores - stores_with_timezone
    
    print(f"Stores needing business hour defaults: {len(stores_missing_business):,}")
    print(f"Stores needing timezone defaults: {len(stores_missing_timezone):,}")
    
    # Create default business hours (24×7 operation)
    default_business_rows = []
    for store_id in stores_missing_business:
        for day in range(7):  # Monday (0) to Sunday (6)
            default_business_rows.append({
                'store_id': store_id,
                'dayOfWeek': day,
                'start_time_local': time(0, 0, 0),    # 00:00:00
                'end_time_local': time(23, 59, 59)    # 23:59:59
            })
    
    # Create default timezone entries
    default_timezone_rows = []
    for store_id in stores_missing_timezone:
        default_timezone_rows.append({
            'store_id': store_id,
            'timezone_str': 'America/Chicago'  # Default timezone
        })
    
    # Add defaults to dataframes
    if default_business_rows:
        df_default_business = pd.DataFrame(default_business_rows)
        df_business_hours_complete = pd.concat([df_business_hours, df_default_business], ignore_index=True)
        print(f"✅ Added 24×7 business hours for {len(stores_missing_business):,} stores")
    else:
        df_business_hours_complete = df_business_hours.copy()
    
    if default_timezone_rows:
        df_default_timezone = pd.DataFrame(default_timezone_rows)
        df_timezones_complete = pd.concat([df_timezones, df_default_timezone], ignore_index=True)
        print(f"✅ Added America/Chicago timezone for {len(stores_missing_timezone):,} stores")
    else:
        df_timezones_complete = df_timezones.copy()
    
    # Verify completeness
    final_business_stores = set(df_business_hours_complete['store_id'].unique())
    final_timezone_stores = set(df_timezones_complete['store_id'].unique())
    
    print(f"\nVerification:")
    print(f"  All stores have business hours: {all_stores.issubset(final_business_stores)}")
    print(f"  All stores have timezone data: {all_stores.issubset(final_timezone_stores)}")
    
    return df_business_hours_complete, df_timezones_complete, {
        'stores_defaulted_business': stores_missing_business,
        'stores_defaulted_timezone': stores_missing_timezone
    }

# Apply defaults
df_business_complete, df_timezone_complete, default_info = apply_data_defaults(
    df_status, df_business_hours, df_timezones
)

# Save default application log
default_log = {
    'timestamp': datetime.now().isoformat(),
    'stores_defaulted_to_24_7': list(default_info['stores_defaulted_business']),
    'stores_defaulted_to_america_chicago': list(default_info['stores_defaulted_timezone']),
    'total_stores_processed': len(df_status['store_id'].unique())
}

# Display sample of complete data
print(f"\n📊 COMPLETE DATASET SUMMARY")
print(f"Business hours records: {len(df_business_complete):,}")
print(f"Timezone records: {len(df_timezone_complete):,}")
print(f"Status records: {len(df_status):,}")

# Show sample of default business hours
if default_info['stores_defaulted_business']:
    sample_store = list(default_info['stores_defaulted_business'])[0]
    sample_hours = df_business_complete[df_business_complete['store_id'] == sample_store]
    print(f"\nSample 24×7 default hours for store {sample_store}:")
    print(sample_hours[['dayOfWeek', 'start_time_local', 'end_time_local']].head(3))

# ============================================================================
# CELL 7: Timezone Conversion Functions
# ============================================================================

class TimezoneConverter:
    """Handle all timezone conversion operations"""
    
    def __init__(self):
        self.cache = {}  # Cache for performance
    
    def convert_business_hours_to_utc(self, store_id: str, day_of_week: int, 
                                    start_local: time, end_local: time, 
                                    timezone_str: str, reference_date: date) -> List[Tuple[datetime, datetime]]:
        """
        Convert local business hours to UTC, handling midnight crossing
        Returns list of (start_utc, end_utc) tuples
        """
        cache_key = f"{timezone_str}_{reference_date}_{start_local}_{end_local}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            local_tz = pytz.timezone(timezone_str)
            
            # Check if business hours cross midnight
            if start_local > end_local:
                # Crosses midnight - create two UTC windows
                # First window: start_local to 23:59:59
                start_dt1 = datetime.combine(reference_date, start_local)
                end_dt1 = datetime.combine(reference_date, time(23, 59, 59))
                
                # Second window: 00:00:00 to end_local (next day)
                next_date = reference_date + timedelta(days=1)
                start_dt2 = datetime.combine(next_date, time(0, 0, 0))
                end_dt2 = datetime.combine(next_date, end_local)
                
                # Convert to UTC
                start_utc1 = self.localize_and_convert(start_dt1, timezone_str)
                end_utc1 = self.localize_and_convert(end_dt1, timezone_str)
                start_utc2 = self.localize_and_convert(start_dt2, timezone_str)
                end_utc2 = self.localize_and_convert(end_dt2, timezone_str)
                
                result = [(start_utc1, end_utc1), (start_utc2, end_utc2)]
            else:
                # Normal business hours within same day
                start_dt = datetime.combine(reference_date, start_local)
                end_dt = datetime.combine(reference_date, end_local)
                
                start_utc = self.localize_and_convert(start_dt, timezone_str)
                end_utc = self.localize_and_convert(end_dt, timezone_str)
                
                result = [(start_utc, end_utc)]
            
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"Error converting business hours for store {store_id}: {e}")
            return []
    
    def localize_and_convert(self, local_datetime: datetime, timezone_str: str) -> datetime:
        """Handle DST transitions properly"""
        try:
            local_tz = pytz.timezone(timezone_str)
            # Use localize with is_dst=None to detect ambiguous times
            return local_tz.localize(local_datetime, is_dst=None)
        except pytz.AmbiguousTimeError:
            # During fall-back, choose the first occurrence
            return local_tz.localize(local_datetime, is_dst=False)
        except pytz.NonExistentTimeError:
            # During spring-forward, adjust forward
            return local_tz.localize(local_datetime, is_dst=True)

def create_business_hours_lookup():
    """Create optimized lookup structure for business hours"""
    
    print("🏗️ CREATING BUSINESS HOURS LOOKUP")
    print("="*50)
    
    # Merge business hours with timezone data
    df_merged = df_business_complete.merge(
        df_timezone_complete[['store_id', 'timezone_str']], 
        on='store_id', 
        how='left'
    )
    
    print(f"Merged {len(df_merged):,} business hour records with timezone data")
    
    # Create timezone converter
    converter = TimezoneConverter()
    
    # Create lookup dictionary
    business_lookup = defaultdict(lambda: defaultdict(list))
    conversion_errors = 0
    
    # Get date range from status data for conversion
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
        
        # Convert for each date in our range (to handle DST properly)
        current_date = min_date
        while current_date <= max_date:
            if current_date.weekday() == day_of_week:
                utc_windows = converter.convert_business_hours_to_utc(
                    store_id, day_of_week, start_local, end_local, 
                    timezone_str, current_date
                )
                
                if utc_windows:
                    business_lookup[store_id][current_date].extend(utc_windows)
                else:
                    conversion_errors += 1
            
            current_date += timedelta(days=1)
        
        # Progress indicator
        if (idx + 1) % 1000 == 0:
            print(f"Processed {idx + 1:,} business hour records...")
    
    print(f"✅ Business hours lookup created successfully!")
    print(f"   Stores processed: {len(business_lookup):,}")
    print(f"   Conversion errors: {conversion_errors:,}")
    
    return business_lookup

# Create business hours lookup
business_hours_lookup = create_business_hours_lookup()

print("✅ Part 2 completed successfully!")
print("Ready for Part 3: Status indexing and final validation") 