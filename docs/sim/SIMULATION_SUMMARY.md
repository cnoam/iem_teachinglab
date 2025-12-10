# Cluster Polling Simulation - Summary

## What Was Created

A complete simulation system for the cluster polling process that:

1. **Reads historical cluster data** from JSON files in chronological order
2. **Simulates time progression** by treating each file as a polling cycle at its timestamped moment
3. **Runs the actual polling logic** (from `poll_clusters.py`) with mocked external systems
4. **Produces verifiable output** showing what actions would be taken in production

## Files Created

### Main Simulator
- **`databricks/simulate_polling.py`** (365 lines)
  - Simulation engine that processes JSON data files
  - Mocks Databricks client, email system, and datetime
  - Generates detailed logs and reports

### Documentation
- **`databricks/SIMULATE_POLLING_README.md`** (comprehensive guide)
  - How to use the simulator
  - Understanding output files
  - Verification checklist
  - Troubleshooting guide

## How to Use

### Quick Start
```bash
cd databricks
source venv/bin/activate
cd ..
python -m databricks.simulate_polling --data_dir cluster_data
```

### With Custom Thresholds
```bash
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --warn_threshold 180 \
  --term_threshold 210 \
  --output_dir my_results
```

## Example: Simulation Run

The simulator processed 7 JSON files (spanning ~1.5 hours from 16:45 to 18:15):

```
clusters2025-12-10_16:45:02.json
clusters2025-12-10_17:00:02.json
clusters2025-12-10_17:15:01.json
clusters2025-12-10_17:30:01.json
clusters2025-12-10_17:45:02.json
clusters2025-12-10_18:00:02.json
clusters2025-12-10_18:15:01.json
```

### Results

- **Total clusters monitored**: 19
- **Clusters that triggered warnings**: 18
- **Clusters that triggered terminations**: 17
- **Emails that would be sent**: 37
- **Database changes tracked**: 19 cluster uptime records

### Final State (sample)

| Cluster | Uptime | Cumulative | Total | Warning | Terminated |
|---------|--------|------------|-------|---------|------------|
| cluster_03 | 373m | 0m | 373m | ✓ | ✓ |
| cluster_06 | 287m | 0m | 287m | ✓ | ✓ |
| cluster_07 | 439m | 0m | 439m | ✓ | ✓ |
| cluster_32 | 191m | 0m | 191m | ✓ | ✗ |

## Output Files

Three files are generated in `sim_output/` (or custom `--output_dir`):

### 1. `simulation.log` (27 KB)
Detailed execution log showing:
- Files loaded and processed
- Each polling cycle with timestamp
- Cluster uptime calculations
- Actions taken (terminations, warnings)
- Database state after each poll

Example log entry:
```
2025-12-10 21:16:22,265  SIMULATION  INFO  --- POLL 1/7 at 2025-12-10 16:45:02 ---
2025-12-10 21:16:22,378  CLUSTER_POLL  INFO  cluster cluster_03 will be terminated NOW. It is up for 6:13:30.553064
2025-12-10 21:16:22,378  SIMULATION  INFO  [EMAIL] To: ['user@example.com']
2025-12-10 21:16:22,378  SIMULATION  INFO  [EMAIL] Subject: 'cluster_03' will be stopped now.
2025-12-10 21:16:22,378  SIMULATION  INFO  [MOCK] Deleted cluster: cluster_03
2025-12-10 21:16:22,378  SIMULATION  INFO  [MOCK] Set permission for cluster 1106-065734-oyax7uo0
```

### 2. `emails_logged.json` (12 KB)
All emails that would have been sent in JSON format:

```json
[
  {
    "subject": "'cluster_03' will be stopped now.",
    "body": "Your cluster is used for too long during the last day.(6h13m , quota is 210.0 minutes)...",
    "recipients": ["user@example.com"],
    "timestamp": "2025-12-10T21:16:22.378530"
  },
  ...
]
```

### 3. `final_db_state.json` (4.2 KB)
Final database state showing all clusters:

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

## How It Works

### 1. Timestamp-Based Simulation

Each JSON file name includes a timestamp:
```
clusters2025-12-10_16:45:02.json  → Simulated time: 2025-12-10 16:45:02
clusters2025-12-10_17:00:02.json  → Simulated time: 2025-12-10 17:00:02
```

When processing each file, `datetime.now()` is mocked to return that timestamp.

### 2. Mocked External Systems

The simulator uses `unittest.mock.patch` to intercept:

- **`datetime.now()`** → Returns simulated timestamp
- **`DataBricksClusterOps`** → Mocked client (doesn't call Databricks API)
- **`DataBricksGroups`** → Mocked groups API
- **`send_emails()`** → Logs to JSON instead of sending

### 3. Real Polling Logic

The actual `poll_clusters.main()` function executes unchanged:
- Reads cluster data (from mock)
- Calculates uptime
- Checks thresholds
- Makes decisions about warnings/terminations
- Calls mocked APIs

## Verification Examples

### Check Thresholds

Verify that warning threshold (180 minutes) works correctly:

```bash
# All clusters with >180m total should have warning_sent=true
jq '.[] | select(.total_minutes > 180) | {name: .cluster_name, total: .total_minutes, warned: .warning_sent}' \
  databricks/sim_output/final_db_state.json
```

### Check Terminations

Verify that termination threshold (210 minutes) works correctly:

```bash
# All clusters with >210m total should have force_terminated=true
jq '.[] | select(.total_minutes > 210) | {name: .cluster_name, total: .total_minutes, term: .force_terminated}' \
  databricks/sim_output/final_db_state.json
```

### Count Actions

```bash
# Count warning emails
jq '[.[] | select(.subject | contains("working for a long time"))] | length' \
  databricks/sim_output/emails_logged.json

# Count termination emails
jq '[.[] | select(.subject | contains("will be stopped now"))] | length' \
  databricks/sim_output/emails_logged.json
```

## Key Advantages

✅ **No External Calls** - No emails sent, no Databricks API calls
✅ **Repeatable** - Run multiple times, same results
✅ **Verifiable** - Compare outputs against JSON inputs
✅ **Debuggable** - Detailed logs show all decisions
✅ **Testable** - Easy to use in CI/CD pipelines
✅ **Real Logic** - Executes actual polling code, not a mock

## Typical Workflow

1. **Capture cluster data** from production or test environment
   ```bash
   python -m databricks.main --print_cluster_status > cluster_data/clusters2025-12-10_17:00:00.json
   ```

2. **Run simulation** on the captured data
   ```bash
   python -m databricks.simulate_polling --data_dir cluster_data
   ```

3. **Verify results** match expectations
   ```bash
   jq '.[] | {name: .cluster_name, total: .total_minutes}' \
     databricks/sim_output/final_db_state.json
   ```

4. **Review logs** for any unexpected behavior
   ```bash
   less databricks/sim_output/simulation.log
   ```

## Next Steps

### For Testing
- Create synthetic JSON data with specific cluster states
- Test edge cases (restart scenarios, quota boundaries)
- Verify email content and recipients

### For Debugging
- Compare simulation output against actual production behavior
- Identify discrepancies in uptime calculations
- Check threshold values are correct

### For CI/CD
- Automate the simulation in your build pipeline
- Assert expected terminations/warnings occur
- Catch regressions in polling logic

## Files to Review

- **`databricks/simulate_polling.py`** - The implementation
- **`databricks/SIMULATE_POLLING_README.md`** - Detailed documentation
- **`databricks/poll_clusters.py`** - The logic being simulated
- **`cluster_data/`** - Example JSON data files

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│  JSON Data Files (cluster_data/)         │
│  clusters2025-12-10_HH:MM:SS.json       │
└────────────┬────────────────────────────┘
             │
             ├─ Parse timestamp from filename
             ├─ Load cluster data
             │
┌────────────▼────────────────────────────┐
│  PollingSimulator                        │
│                                          │
│  Mock datetime.now() → HH:MM:SS         │
│  Mock DataBricksClusterOps              │
│  Mock send_emails()                     │
│                                          │
└────────────┬────────────────────────────┘
             │
             └─ Call poll_clusters.main()

             ▼
┌─────────────────────────────────────────┐
│  Actual Polling Logic (unmodified)       │
│  - Calculate uptime                      │
│  - Check thresholds                      │
│  - Decide: warn/terminate/ok            │
│  - Call mocked APIs                     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Output Files (sim_output/)              │
│  - simulation.log                       │
│  - emails_logged.json                   │
│  - final_db_state.json                  │
└─────────────────────────────────────────┘
```

## Questions?

See `databricks/SIMULATE_POLLING_README.md` for:
- Detailed usage examples
- Verification checklist
- Troubleshooting guide
- Understanding the code
- Integration with CI/CD
