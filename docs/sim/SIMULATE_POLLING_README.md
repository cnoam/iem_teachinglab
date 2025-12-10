# Cluster Polling Simulation

This document describes the polling simulation system that allows you to test and verify the cluster quota enforcement logic using historical cluster data.

## Overview

The `simulate_polling.py` script simulates the cluster polling process by:

1. **Reading JSON data files** from a directory (e.g., `cluster_data/`) that contain cluster state snapshots
2. **Simulating time progression** by processing files in chronological order
3. **Running the actual polling logic** from `poll_clusters.py` with mocked external dependencies
4. **Logging actions** without triggering external systems (emails, Databricks API calls)
5. **Generating reports** showing what would have happened in production

## Why Use This?

This simulator allows you to:
- **Verify correctness** of quota enforcement logic without running live systems
- **Test edge cases** by using historical or synthetic data
- **Debug issues** by examining detailed logs of decision-making
- **Validate configuration** by checking if thresholds are working as expected
- **Audit behavior** by comparing simulation output against JSON data files

## How It Works

### Input: JSON Data Files

JSON files in `cluster_data/` directory must follow this naming pattern:
```
clusters2025-12-10_16:45:02.json
clusters2025-12-10_17:00:02.json
clusters2025-12-10_17:15:01.json
```

Format: `clusters<YYYY-MM-DD_HH:MM:SS>.json`

Each file contains an array of cluster objects returned by the Databricks API. Running clusters must have a `driver` field with `start_timestamp`.

### Processing Flow

For each JSON file in chronological order:

1. Extract the timestamp from the filename
2. Load cluster data from the JSON file
3. Simulate `datetime.now()` returning that timestamp
4. Call the actual `poll_clusters.main()` function with mocked dependencies
5. Log database state changes
6. Repeat for next file

### Mocked Dependencies

The simulator uses `unittest.mock.patch` to mock:

- **`datetime.now()`** - Returns the simulated timestamp from the filename
- **`DataBricksClusterOps`** - Mocked client that:
  - Returns clusters from the JSON file
  - Logs cluster deletions instead of actually deleting
  - Logs permission changes instead of applying them
- **`DataBricksGroups`** - Mocked groups API
- **`send_emails()`** - Logs emails to JSON file instead of sending

This ensures the polling logic runs unmodified while avoiding external system calls.

## Usage

### Basic Usage

```bash
cd databricks
source venv/bin/activate
cd ..
python -m databricks.simulate_polling --data_dir cluster_data
```

### With Custom Parameters

```bash
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --db simulation.db \
  --warn_threshold 180 \
  --term_threshold 210 \
  --output_dir results
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--data_dir` | `cluster_data` | Directory containing cluster JSON files |
| `--db` | `sim_clusters.db` | SQLite database file for simulation state |
| `--warn_threshold` | 180 | Warning threshold in minutes (soft quota) |
| `--term_threshold` | 210 | Termination threshold in minutes (hard quota) |
| `--output_dir` | `sim_output` | Directory for output reports |

## Output

The simulator generates three output files in `--output_dir`:

### 1. `simulation.log`

Detailed log of the entire simulation showing:
- Files loaded
- Timestamp of each polling cycle
- Cluster uptime calculations
- Actions taken (termination, warning emails)
- Database state after each poll

Example excerpt:
```
2025-12-10 21:16:22,265  SIMULATION  INFO  --- POLL 1/7 at 2025-12-10 16:45:02 ---
2025-12-10 21:16:22,378  CLUSTER_POLL  INFO  cluster cluster_03 will be terminated NOW. It is up for 6:13:30.553064
2025-12-10 21:16:22,378  SIMULATION  INFO  [EMAIL] To: ['user@example.com']
2025-12-10 21:16:22,378  SIMULATION  INFO  [EMAIL] Subject: 'cluster_03' will be stopped now.
2025-12-10 21:16:22,378  SIMULATION  INFO  [MOCK] Deleted cluster: cluster_03
```

### 2. `emails_logged.json`

JSON file containing all emails that would have been sent:

```json
[
  {
    "subject": "'cluster_03' will be stopped now.",
    "body": "Your cluster is used for too long...",
    "recipients": ["user@example.com"],
    "timestamp": "2025-12-10T21:16:22.378530"
  },
  ...
]
```

Use this to verify email triggers and content.

### 3. `final_db_state.json`

Final state of all clusters after all polling cycles:

```json
[
  {
    "cluster_id": "1106-065734-oyax7uo0",
    "cluster_name": "cluster_03",
    "uptime_minutes": 373,
    "cumulative_minutes": 0,
    "total_minutes": 373,
    "warning_sent": true,
    "force_terminated": true
  },
  ...
]
```

Use this to verify:
- Which clusters were terminated
- Which clusters triggered warnings
- Total accumulated uptime
- Cumulative uptime from previous cycles

## Verification Checklist

After running the simulation, verify:

### 1. Compare with JSON Data

```bash
# Check cluster uptime calculations
# For each cluster in final_db_state.json:
# - Verify total_minutes matches the time difference between first and last
#   poll where the cluster had a driver (was running)
```

### 2. Verify Thresholds

```bash
# All clusters with total_minutes > warn_threshold should have warning_sent=true
# All clusters with total_minutes > term_threshold should have force_terminated=true
```

Example check:
```bash
jq '.[] | select(.total_minutes > 180) | {name: .cluster_name, total: .total_minutes, warned: .warning_sent}' final_db_state.json
```

### 3. Check Email Logs

```bash
# Count termination emails
jq '[.[] | select(.subject | contains("will be stopped now")) ] | length' emails_logged.json

# Count warning emails
jq '[.[] | select(.subject | contains("working for a long time")) ] | length' emails_logged.json
```

### 4. Review Cluster Restarts

In `simulation.log`, look for:
```
INFO:root:Cluster <id> is turned on again or started anew.
```

This indicates the cluster was restarted and cumulative uptime was advanced.

## Example: Full Verification Workflow

```bash
# 1. Run simulation
python -m databricks.simulate_polling --data_dir cluster_data --output_dir my_results

# 2. Check summary
tail -20 my_results/simulation.log

# 3. Verify terminations
jq '[.[] | select(.force_terminated == true)] | length' my_results/final_db_state.json

# 4. Verify warnings
jq '[.[] | select(.warning_sent == true)] | length' my_results/final_db_state.json

# 5. Check emails
wc -l my_results/emails_logged.json
jq '.[] | .subject' my_results/emails_logged.json | head -20

# 6. Manual inspection
# Open final_db_state.json in editor/JSON viewer
# Verify each cluster's minutes and flags match expectations
```

## Common Issues and Solutions

### Issue: Simulation doesn't run

**Error:** `ModuleNotFoundError: No module named 'databricks_cli'`

**Solution:** Install dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: No data files found

**Error:** `ERROR  No cluster JSON files found in cluster_data`

**Solution:** Ensure:
1. `cluster_data/` directory exists
2. Files match pattern: `clusters<timestamp>.json`
3. Timestamp format is `YYYY-MM-DD_HH:MM:SS`

### Issue: Database errors

**Error:** `database is locked` or similar

**Solution:** Delete the simulation database and try again:
```bash
rm sim_clusters.db
python -m databricks.simulate_polling ...
```

### Issue: Thresholds don't match production

**Problem:** Simulation results differ from production behavior

**Solution:** Check environment variables and parameters:
```bash
# Default thresholds (in minutes):
# - Warning: 180 (3 hours)
# - Termination: 210 (3.5 hours)

# Production uses env vars DATABRICKS_WARN_UPTIME and DATABRICKS_MAX_UPTIME
# If production values differ, use --warn_threshold and --term_threshold
python -m databricks.simulate_polling \
  --warn_threshold <YOUR_VALUE> \
  --term_threshold <YOUR_VALUE>
```

## Understanding the Code

### Key Classes

- **`SimulationConfig`** - Configuration container
- **`PollingSimulator`** - Main simulation engine
- **`EmailLog`** - Tracks logged emails instead of sending them

### Key Methods

- `load_data_files()` - Load and sort JSON files
- `_extract_timestamp()` - Parse timestamp from filename
- `_create_mock_client()` - Create mocked Databricks client
- `_run_poll_with_mocks()` - Call actual poll logic with mocks
- `_generate_reports()` - Write output files

### How Mocking Works

The simulator uses context managers (`with` statements) to temporarily replace:

```python
with patch('poll_clusters.DataBricksClusterOps', return_value=mock_client), \
     patch('poll_clusters.datetime') as mock_dt, \
     patch('poll_clusters.send_emails', side_effect=mock_send_emails):
    # Call real poll_clusters.main()
    poll_clusters.main()
    # Mocks are active only inside this context
```

This ensures the real polling logic executes with mocked external dependencies.

## Integration with CI/CD

To use the simulator in automated testing:

```bash
#!/bin/bash
set -e

# Run simulation
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --output_dir test_results

# Verify results
TERMINATED=$(jq '[.[] | select(.force_terminated == true)] | length' test_results/final_db_state.json)
if [ "$TERMINATED" -lt 5 ]; then
    echo "ERROR: Expected at least 5 terminations, got $TERMINATED"
    exit 1
fi

echo "✓ Simulation passed verification"
```

## Troubleshooting Tips

1. **Enable verbose logging**: Edit `simulate_polling.py` and set logger to `DEBUG` level
2. **Check raw JSON**: Inspect the cluster data files directly:
   ```bash
   jq '.[] | {id: .cluster_id, name: .cluster_name, has_driver: (.driver != null)}' cluster_data/clusters*.json
   ```
3. **Compare uptime calculations**: Manually calculate from JSON timestamps and compare to simulation output
4. **Isolate issues**: Run simulation with just 2 data files to debug specific polls

## See Also

- `poll_clusters.py` - The actual polling logic being simulated
- `databricks/database/db_operations.py` - Database models (ClusterUptime, ClusterInfo)
- `databricks/resource_manager/cluster_uptime.py` - Uptime calculation logic
