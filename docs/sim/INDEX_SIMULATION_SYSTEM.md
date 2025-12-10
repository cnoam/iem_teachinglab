# Cluster Polling Simulation System - Index

This document provides a centralized guide to the newly created cluster polling simulation system.

## Overview

**What**: A system to simulate and test the cluster quota enforcement logic (`poll_clusters.py`)

**Why**: Test without external system calls (no emails, no Databricks API calls, no modifications to production)

**How**: Read JSON cluster snapshots from `cluster_data/` directory, process them in chronological order, simulate time progression, run actual polling logic with mocked dependencies, generate verifiable reports

## Start Here

### 🚀 I want to run it NOW
👉 Read: **QUICK_START_SIMULATION.md**

Contains:
- One-liner command to run the simulation
- Copy-paste commands for common variations
- Quick verification commands
- Fast troubleshooting tips

### 👁️ I want to understand what was created
👉 Read: **SIMULATION_SUMMARY.md**

Contains:
- Overview of files created
- Example results from actual simulation run
- How the simulation works (detailed)
- Architecture diagram
- Typical workflow

### 📚 I want comprehensive documentation
👉 Read: **databricks/SIMULATE_POLLING_README.md**

Contains:
- Detailed usage guide with examples
- Complete description of output files
- Verification checklist
- Common issues and solutions
- Understanding the code
- Integration with CI/CD pipelines
- Troubleshooting guide

## Files at a Glance

### Code
- **databricks/simulate_polling.py** - Main simulation engine (365 lines)
  - Reads JSON files in chronological order
  - Mocks datetime, email, Databricks client
  - Runs actual `poll_clusters.main()` unmodified
  - Generates logs and reports

### Documentation
- **QUICK_START_SIMULATION.md** - Quick reference (4 KB)
- **SIMULATION_SUMMARY.md** - Overview & results (9.5 KB)
- **databricks/SIMULATE_POLLING_README.md** - Complete guide (16+ KB)
- **INDEX_SIMULATION_SYSTEM.md** - This file

### Data
- **cluster_data/** - Input JSON cluster snapshots (7 files)
  - `clusters2025-12-10_16:45:02.json`
  - `clusters2025-12-10_17:00:02.json`
  - ... (7 files spanning 1.5 hours)

### Output (generated after running)
- **databricks/sim_output/simulation.log** - Detailed execution log (27 KB)
- **databricks/sim_output/final_db_state.json** - Final cluster states (4.2 KB)
- **databricks/sim_output/emails_logged.json** - Emails that would be sent (12 KB)

## Quick Reference

### Run Simulation
```bash
cd databricks && source venv/bin/activate && cd ..
python -m databricks.simulate_polling --data_dir cluster_data
```

### View Results
```bash
# Detailed log
tail -50 databricks/sim_output/simulation.log

# Final state of all clusters
jq . databricks/sim_output/final_db_state.json

# Emails that would be sent
jq . databricks/sim_output/emails_logged.json
```

### Quick Verification
```bash
# How many clusters would be terminated?
jq '[.[] | select(.force_terminated == true)] | length' \
  databricks/sim_output/final_db_state.json

# How many would get warnings?
jq '[.[] | select(.warning_sent == true)] | length' \
  databricks/sim_output/final_db_state.json

# How many emails would be sent?
jq '[.[] | length]' databricks/sim_output/emails_logged.json
```

## Key Concepts

### Timestamp Simulation
- JSON filename contains timestamp: `clusters2025-12-10_17:00:02.json`
- Simulator extracts: `2025-12-10 17:00:02`
- When processing that file, `datetime.now()` is mocked to return that time
- Allows simulating multiple polling cycles across a time period

### Dependency Mocking
- `unittest.mock.patch` is used to replace external dependencies
- **Mocked**: `datetime.now()`, `DataBricksClusterOps`, `DataBricksGroups`, `send_emails()`
- **Real**: All polling logic from `poll_clusters.py`
- **Result**: Real decisions with mocked side effects

### Output Files
1. **simulation.log** - Detailed log showing every decision and action
2. **final_db_state.json** - Summary of each cluster's final state
3. **emails_logged.json** - All emails that would have been sent

## Example Results

From running the simulator on 7 cluster snapshots (1.5 hour window):

- **19 clusters** monitored
- **18 clusters** exceeded termination threshold (210 minutes) and would be terminated
- **19 clusters** exceeded warning threshold (180 minutes) and would get warning emails
- **37 emails** would be sent (17 termination + 20 warning)

### Sample: cluster_03
- Current uptime: 373 minutes (6h13m)
- Cumulative uptime: 0 minutes
- Total uptime: 373 minutes
- Warning threshold: 180 minutes
- Termination threshold: 210 minutes
- **Action**: Would send warning email AND terminate cluster (both thresholds exceeded)

## Verification Workflow

1. **Compare with input**: Check that uptime calculations match the time difference in JSON files
2. **Verify thresholds**: Ensure all clusters > threshold have corresponding actions
3. **Review logs**: Inspect `simulation.log` for any unexpected decisions
4. **Audit emails**: Check `emails_logged.json` for correct subjects and recipients

## Common Questions

**Q: Does this send real emails?**
A: No. Emails are logged to JSON file instead of being sent.

**Q: Does this call the Databricks API?**
A: No. Cluster data comes from JSON files, API calls are mocked.

**Q: Does this modify production systems?**
A: No. The database is a separate simulation database, no changes to production.

**Q: Does this run the real polling logic?**
A: Yes. The actual `poll_clusters.main()` function executes unmodified, only dependencies are mocked.

**Q: Can I test with different thresholds?**
A: Yes. Use `--warn_threshold` and `--term_threshold` parameters.

**Q: Can I test with different cluster data?**
A: Yes. Place JSON files in `--data_dir` and they'll be processed.

## Troubleshooting

### "No cluster JSON files found"
- Ensure directory exists: `ls cluster_data/`
- Ensure filenames match pattern: `clusters<DATE>_<TIME>.json`

### "ModuleNotFoundError"
- Activate venv: `source databricks/venv/bin/activate`
- Install deps: `pip install -r databricks/requirements.txt`

### Different results than expected
- Check thresholds: `--warn_threshold` and `--term_threshold` defaults are 180 and 210 minutes
- Review log: `cat databricks/sim_output/simulation.log`
- Compare with input: `jq . cluster_data/clusters*.json | head -50`

See **databricks/SIMULATE_POLLING_README.md** for more troubleshooting.

## Integration Examples

### Use in Testing
```bash
#!/bin/bash
python -m databricks.simulate_polling --data_dir cluster_data --output_dir /tmp/test_results
TERMINATIONS=$(jq '[.[] | select(.force_terminated == true)] | length' /tmp/test_results/final_db_state.json)
if [ "$TERMINATIONS" -lt 10 ]; then
  echo "ERROR: Expected at least 10 terminations"
  exit 1
fi
echo "✓ Simulation passed"
```

### Use in CI/CD
```yaml
- name: Run polling simulation
  run: python -m databricks.simulate_polling --data_dir cluster_data

- name: Verify results
  run: |
    WARNINGS=$(jq '[.[] | select(.warning_sent == true)] | length' sim_output/final_db_state.json)
    echo "Warnings triggered: $WARNINGS"
```

## Next Steps

1. **Run the simulation**: Follow QUICK_START_SIMULATION.md
2. **Review the output**: Check the three generated JSON/log files
3. **Understand how it works**: Read SIMULATION_SUMMARY.md
4. **Learn the details**: Read databricks/SIMULATE_POLLING_README.md
5. **Integrate into your workflow**: Use in CI/CD, testing, debugging

## Related Files

- **poll_clusters.py** - The polling logic being simulated
- **databricks/database/db_operations.py** - Database models
- **databricks/resource_manager/cluster_uptime.py** - Uptime calculation logic
- **databricks/resource_manager/user_mail.py** - Email utilities (mocked)

## Architecture Summary

```
JSON Data Files (cluster_data/)
         ↓
   Extract Timestamps
         ↓
   Mock Dependencies (datetime, APIs, email)
         ↓
   Run actual poll_clusters.main()
         ↓
   Generate Output Files
   ├─ simulation.log
   ├─ final_db_state.json
   └─ emails_logged.json
```

## Support

- **Quick help**: See QUICK_START_SIMULATION.md
- **Understanding**: See SIMULATION_SUMMARY.md
- **Complete guide**: See databricks/SIMULATE_POLLING_README.md
- **Questions about code**: See code comments in simulate_polling.py

---

**Created**: 2025-12-10
**Status**: ✅ Fully functional and tested
**Last Run**: 7 polling cycles processed, 37 simulated emails, 18 terminations triggered
