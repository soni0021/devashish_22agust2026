# Store Monitoring System - Complete Pipeline & API

> **⚠️ IMPORTANT: This repository contains the application code only. The required CSV data files are not included due to size limitations.**
> 
> **To run this application, you need to add these three CSV files to the project root:**
> - `store_status.csv` (~134MB) - Store status observations
> - `menu_hours.csv` (~1MB) - Business hours definitions  
> - `timezones.csv` (~100KB) - Store timezone mappings
> 
> **Download these files from your data source and place them in the project directory before running the application.**

A restaurant store monitoring system that processes real-time status data, calculates uptime/downtime metrics, and provides REST API endpoints for report generation. This system handles dynamic data updates and provides comprehensive business intelligence for store operations.

## 🎯 Problem Statement

Restaurant chains need to monitor store availability and performance across multiple locations. The system must:

- Process store status observations (active/inactive) with timestamps
- Handle business hours and timezone data for each store
- Calculate uptime/downtime during business hours for different time windows
- Provide API endpoints for asynchronous report generation
- Handle missing data gracefully with sensible defaults
- Support dynamic data updates (CSVs change hourly)

## 📊 Data Sources

The system processes three main data files:

### 1. Store Status Data (`store_status.csv`)
- **Records**: ~1.85M status observations
- **Stores**: 3,678 unique locations
- **Schema**: `store_id`, `timestamp_utc`, `status`
- **Status Values**: 'active' or 'inactive'
- **Time Range**: August 1 - October 14, 2024

### 2. Business Hours (`menu_hours.csv`)
- **Records**: ~35K business hour definitions
- **Schema**: `store_id`, `dayOfWeek`, `start_time_local`, `end_time_local`
- **Coverage**: 4,466 stores with defined hours
- **Missing Data**: 54 stores default to 24×7 operation

### 3. Timezone Data (`timezones.csv`)
- **Records**: ~4.5K timezone mappings
- **Schema**: `store_id`, `timezone_str`
- **Coverage**: 4,559 stores with timezone data
- **Missing Data**: 1 store defaults to America/Chicago

## 🏗️ System Architecture

### Core Components

1. **Data Processing Pipeline** (`run_pipeline.py`)
   - CSV loading and validation
   - Default value application
   - Timezone conversion and business hours processing
   - Status observation indexing

2. **Uptime Calculator** (`uptime_downtime_calculator.py`)
   - Business hours intersection logic
   - Status interpolation algorithms
   - Metric computation for multiple time windows

3. **REST API Server** (`api_server.py`)
   - FastAPI-based endpoints
   - Background job processing
   - SQLite job tracking
   - CSV report generation

## 🔧 Installation & Setup

### Prerequisites
- Python 3.7+
- 4GB+ RAM (for large dataset processing)
- Git

### Step 1: Clone and Setup
```bash
git clone https://github.com/soni0021/devashish_22agust2026.git
cd devashish_22agust2026
```

### Step 2: Add Required Data Files
**⚠️ CRITICAL: You must add these three CSV files to run the application:**

1. **Download the CSV files** from your data source:
   - `store_status.csv` (~134MB) - Store status observations
   - `menu_hours.csv` (~1MB) - Business hours definitions  
   - `timezones.csv` (~100KB) - Store timezone mappings

2. **Place all three files** in the project root directory (same level as `README.md`)

3. **Verify file structure:**
   ```
   store-monitoring-data/
   ├── store_status.csv          # ← Add this file
   ├── menu_hours.csv           # ← Add this file
   ├── timezones.csv            # ← Add this file
   ├── run_pipeline.py
   ├── uptime_downtime_calculator.py
   ├── api_server.py
   └── README.md
   ```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Key Libraries:**
- `pandas` - Data processing and CSV handling
- `pytz` - Timezone conversion and DST handling
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `requests` - HTTP client for testing

### Project Structure
```
store-monitoring-data/
├── store_status.csv          # ← REQUIRED: Add this file (not included in repo)
├── menu_hours.csv           # ← REQUIRED: Add this file (not included in repo)
├── timezones.csv            # ← REQUIRED: Add this file (not included in repo)
├── run_pipeline.py          # Data processing pipeline
├── uptime_downtime_calculator.py  # Uptime calculation logic
├── api_server.py            # FastAPI server
├── test_api_flow.py         # API testing client
├── requirements.txt         # Python dependencies
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🚀 Execution Pipeline

### Step 1: Data Processing Pipeline

The pipeline processes raw CSV data into optimized data structures:

```bash
python run_pipeline.py
```

**What happens:**
1. **Data Loading**: Reads all three CSV files with validation
2. **Default Application**: 
   - Missing business hours → 24×7 operation
   - Missing timezones → America/Chicago
3. **Timezone Conversion**: Converts local business hours to UTC
4. **Status Indexing**: Organizes observations for efficient querying

**Key Outputs:**
- `business_lookup`: UTC business hours per store per date
- `observations`: Indexed status observations per store
- `processing_summary.json`: Processing statistics and validation results

### Step 2: Uptime Calculation

Computes uptime/downtime metrics for each store:

```bash
python uptime_downtime_calculator.py
```

**Calculation Logic:**
1. **Time Windows**: last_hour, last_day, last_week (trailing from latest timestamp)
2. **Business Hours Intersection**: Only considers time within business hours
3. **Status Interpolation**: Seeds with last known status, processes observations
4. **Metric Accumulation**: Tracks uptime/downtime seconds per window

**Output Format:**
```csv
store_id,uptime_last_hour(in minutes),uptime_last_day(in hours),uptime_last_week(in hours),downtime_last_hour(in minutes),downtime_last_day(in hours),downtime_last_week(in hours)
```

### Step 3: API Server

Start the FastAPI server for report generation:

```bash
uvicorn api_server:app --host 0.0.0.0 --port 5000
```

**Server Features:**
- **Dynamic Processing**: Reloads data on every report request
- **Background Jobs**: Asynchronous report generation
- **Job Tracking**: SQLite database for job status
- **File Downloads**: CSV report delivery

## 🔌 API Endpoints

### 1. Health Check
```bash
curl http://localhost:5000/health
```
**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-19T15:50:32.347827"
}
```

### 2. Trigger Report Generation
```bash
curl -X POST http://localhost:5000/trigger_report
```
**Response:**
```json
{
  "report_id": "48e14f91-6a54-4364-8b2c-cb037b71e562",
  "message": "Report generation started"
}
```

### 3. Get Report Status/Download
```bash
curl "http://localhost:5000/get_report?report_id=48e14f91-6a54-4364-8b2c-cb037b71e562"
```

**Status Response (while processing):**
```json
{
  "status": "Running",
  "created_at": "2025-08-19T15:50:41.138724",
  "completed_at": null
}
```

**CSV Download (when complete):**
- Returns CSV file with uptime/downtime metrics
- Content-Type: `text/csv`
- Filename: `uptime_report_{report_id}.csv`

### 4. List Recent Jobs
```bash
curl http://localhost:5000/reports/status
```
**Response:**
```json
{
  "reports": [
    {
      "report_id": "48e14f91-6a54-4364-8b2c-cb037b71e562",
      "status": "Complete",
      "created_at": "2025-08-19T15:50:41.138724",
      "completed_at": "2025-08-19T15:52:15.123456",
      "file_path": "reports/report_48e14f91-6a54-4364-8b2c-cb037b71e562.csv"
    }
  ]
}
```

## 🧪 API Testing

### Automated Testing
Run the complete API flow test:

```bash
python test_api_flow.py
```

**Test Flow:**
1. Health check verification
2. Report job triggering
3. Status polling until completion
4. CSV download and validation

### Manual Testing
```bash
# Start server
uvicorn api_server:app --host 127.0.0.1 --port 5055

# Trigger report
REPORT_ID=$(curl -s -X POST http://127.0.0.1:5055/trigger_report | python3 -c "import sys,json; print(json.load(sys.stdin)['report_id'])")

# Poll status
curl "http://127.0.0.1:5055/get_report?report_id=$REPORT_ID"

# Download when ready
curl "http://127.0.0.1:5055/get_report?report_id=$REPORT_ID" -o final_report.csv
```

## 📈 Output Analysis

### Report Structure
The final CSV contains 7 columns:
1. `store_id` - Unique store identifier
2. `uptime_last_hour(in minutes)` - Uptime in last hour (0-60 minutes)
3. `uptime_last_day(in hours)` - Uptime in last day (0-24 hours)
4. `uptime_last_week(in hours)` - Uptime in last week (0-168 hours)
5. `downtime_last_hour(in minutes)` - Downtime in last hour
6. `downtime_last_day(in hours)` - Downtime in last day
7. `downtime_last_week(in hours)` - Downtime in last week

### Sample Data
```csv
store_id,uptime_last_hour(in minutes),uptime_last_day(in hours),uptime_last_week(in hours),downtime_last_hour(in minutes),downtime_last_day(in hours),downtime_last_week(in hours)
00017c6a-7a77-4a95-bb2d-40647868aff6,60.0,8.53,58.77,0.0,1.97,16.73
000bba84-20af-4a8b-b68a-368922cc6ad1,0.0,0.0,0.0,60.0,24.0,168.0
003222af-0b64-4f8c-b5c3-d2dc24636f02,60.0,11.25,78.75,0.0,0.0,0.0
```

### Data Validation
- **Row Count**: 3,678 stores (matches input data)
- **Value Ranges**: All values non-negative, hours ≤ 24, minutes ≤ 60
- **Consistency**: Uptime + downtime = total business hours for each window
- **Coverage**: All stores included regardless of missing input data

## 🔄 Dynamic Data Handling

### Real-time Updates
The system handles dynamic data changes:

1. **Module Reloading**: Every report job reloads processing modules
2. **Fresh Data Loading**: CSVs are re-read on each report generation
3. **Updated Calculations**: Metrics reflect latest data state
4. **No Caching**: Ensures reports always use current data

### Default Handling
- **24×7 Business Hours**: Applied to 54 stores missing business hours
- **America/Chicago Timezone**: Applied to 1 store missing timezone
- **Graceful Degradation**: System continues with defaults

## 🚨 Error Handling

### Data Validation
- UUID format validation for store IDs
- Timezone string validation
- Time format validation (HH:MM:SS)
- Status value validation (active/inactive only)

### Processing Errors
- DST transition handling in timezone conversion
- Missing data detection and default application
- Invalid business hours handling (midnight crossings)
- Memory management for large datasets

### API Errors
- Invalid report_id handling
- File not found responses
- Background job failure tracking
- Timeout handling for long-running jobs

## 📊 Performance Characteristics

### Processing Times
- **Data Loading**: ~30 seconds for 1.85M records
- **Business Hours Conversion**: ~2 minutes for all stores
- **Report Generation**: ~3-5 minutes for 3,678 stores
- **API Response**: <100ms for status checks

### Memory Usage
- **Peak Memory**: ~2GB during processing
- **Runtime Memory**: ~500MB for server operation
- **Optimization**: Lazy loading of heavy modules

### Scalability
- **Current Capacity**: 3,678 stores
- **Theoretical Limit**: 10K+ stores with current architecture
- **Bottlenecks**: Memory usage, not CPU

## 🔧 Configuration

### Environment Variables
```bash
# Optional: Customize server settings
export API_HOST=0.0.0.0
export API_PORT=5000
export DB_PATH=reports.db
export REPORTS_DIR=reports
```

### Default Values
- **Missing Business Hours**: 24×7 operation
- **Missing Timezone**: America/Chicago
- **Time Windows**: last_hour, last_day, last_week
- **Reference Time**: Latest timestamp in status data

## 🐛 Troubleshooting

### Common Issues

**Server Won't Start:**
```bash
# Check port availability
lsof -i :5000
# Use different port
uvicorn api_server:app --port 5055
```

**Report Generation Fails:**
```bash
# Check server logs
tail -f /tmp/api_server.log
# Verify CSV files exist
ls -la *.csv
```

**Memory Errors:**
```bash
# Increase system memory
# Or process in smaller batches
```

**Timezone Errors:**
```bash
# Verify pytz installation
pip install pytz --upgrade
# Check timezone strings in timezones.csv
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn api_server:app --log-level debug
```

## 📝 Development Notes

### Code Quality
- Type hints throughout codebase
- Comprehensive error handling
- Modular design for easy testing
- Clear separation of concerns

### Testing Strategy
- Unit tests for calculation logic
- Integration tests for API endpoints
- End-to-end tests for complete pipeline
- Performance benchmarks

### Future Enhancements
- Real-time data streaming
- Custom time window support
- Advanced analytics and trends
- Multi-tenant architecture
- Database backend (PostgreSQL)
- Caching layer (Redis)

## 🚀 Improvement Ideas

### Performance Optimizations
- **Parallel Processing**: Use multiprocessing to calculate uptime/downtime for multiple stores simultaneously
- **Database Indexing**: Implement proper database indexes for faster queries on large datasets
- **Memory Optimization**: Use generators and streaming for processing large CSV files without loading everything into memory
- **Caching Strategy**: Implement Redis caching for frequently accessed business hours and timezone data

### Scalability Enhancements
- **Microservices Architecture**: Split the system into separate services (data processing, calculation engine, API server)
- **Load Balancing**: Implement horizontal scaling with multiple API server instances
- **Queue System**: Use message queues (RabbitMQ/Apache Kafka) for handling report generation requests
- **Database Sharding**: Partition data by store regions or time periods for better performance

### Feature Additions
- **Real-time Monitoring**: WebSocket connections for live store status updates
- **Alert System**: Notify managers when stores go down or have low uptime
- **Custom Time Windows**: Allow users to specify custom time ranges for reports
- **Trend Analysis**: Historical uptime trends and predictive analytics
- **Geographic Analysis**: Map-based visualization of store performance by region
- **Export Formats**: Support for Excel, PDF, and other report formats

### Data Quality Improvements
- **Data Validation**: More robust validation for business hours and timezone data
- **Anomaly Detection**: Identify and flag unusual uptime patterns
- **Data Reconciliation**: Cross-reference with other data sources for accuracy
- **Audit Trail**: Track changes to business hours and timezone configurations

### User Experience Enhancements
- **Web Dashboard**: Interactive web interface for viewing reports and metrics
- **Mobile App**: Native mobile application for store managers
- **Email Reports**: Automated email delivery of uptime reports
- **API Rate Limiting**: Implement proper rate limiting for API endpoints
- **Authentication**: Add user authentication and authorization

### Technical Debt Reduction
- **Code Refactoring**: Break down large functions into smaller, more testable units
- **Configuration Management**: Move hardcoded values to configuration files
- **Logging Framework**: Implement structured logging with different log levels
- **Monitoring**: Add application performance monitoring (APM) tools
- **Documentation**: Generate API documentation using OpenAPI/Swagger

## 📄 License

This project is part of a store monitoring system implementation. Please refer to the assignment guidelines for usage terms and conditions.

---

**Last Updated**: August 19, 2025  
**Version**: 1.0.0  
**Status**: Production Ready # devashish_22agust2026
