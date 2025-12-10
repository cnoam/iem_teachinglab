# Quick Start: Cluster Polling Simulation

## One-Liner Setup

```bash
cd databricks && source venv/bin/activate && cd .. && \
python -m databricks.simulate_polling --data_dir cluster_data --output_dir sim_output
```

## What Happens

✅ Reads 7 JSON files from `cluster_data/` directory
✅ Processes them in chronological order (16:45 → 18:15)
✅ Simulates polling at each timestamp
✅ Tracks cluster uptime and quota enforcement
✅ Generates 3 output files in `sim_output/`

## View Results (3 commands)

### 1. See Summary
```bash
tail -30 databricks/sim_output/simulation.log
```

Expected output:
```
Total emails logged: 37
Simulation output directory: .../databricks/sim_output
SIMULATION COMPLETE
```

### 2. Check Final State
```bash
jq '.[] | {name: .cluster_name, total_min: .total_minutes, warned: .warning_sent, term: .force_terminated}' \
  databricks/sim_output/final_db_state.json | head -20
```

Expected output:
```json
{
  "name": "cluster_03",
  "total_min": 373,
  "warned": true,
  "term": true
}
```

### 3. View Emails That Would Be Sent
```bash
jq '.[] | {subject: .subject, recipients: .recipients}' \
  databricks/sim_output/emails_logged.json | head -30
```

## Common Variations

### Custom Thresholds
```bash
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --warn_threshold 120 \
  --term_threshold 180
```

### Custom Output Directory
```bash
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --output_dir /tmp/my_results
```

### Different Database File
```bash
python -m databricks.simulate_polling \
  --data_dir cluster_data \
  --db my_sim.db
```

## Understanding Output

### `simulation.log`
- Detailed execution log
- Shows each polling cycle
- Displays uptime calculations
- Lists all actions taken

### `final_db_state.json`
- Final state of all clusters
- Shows uptime_minutes, cumulative_minutes, total_minutes
- Shows which clusters triggered warnings/terminations

### `emails_logged.json`
- All emails that would have been sent
- Includes subject, body, recipients, timestamp
- Use to verify email content and recipients

## Quick Verification

### Count Terminations
```bash
jq '[.[] | select(.force_terminated == true)] | length' \
  databricks/sim_output/final_db_state.json
```

### Count Warnings
```bash
jq '[.[] | select(.warning_sent == true)] | length' \
  databricks/sim_output/final_db_state.json
```

### Count Termination Emails
```bash
jq '[.[] | select(.subject | contains("will be stopped"))] | length' \
  databricks/sim_output/emails_logged.json
```

### Count Warning Emails
```bash
jq '[.[] | select(.subject | contains("working for a long time"))] | length' \
  databricks/sim_output/emails_logged.json
```

## Clean Up

```bash
# Remove simulation database
rm databricks/sim_clusters.db

# Remove previous simulation results
rm -rf databricks/sim_output
```

## Troubleshooting

### "No cluster JSON files found"
- Check path: `ls cluster_data/ | head`
- Check names match: `clusters<DATE>_<TIME>.json`

### "ModuleNotFoundError"
- Install deps: `source databricks/venv/bin/activate && pip install -r databricks/requirements.txt`

### Different results than expected
- Check thresholds: `cat SIMULATION_SUMMARY.md` (Thresholds section)
- Check log: `less databricks/sim_output/simulation.log`

## Files Reference

| File | Purpose |
|------|---------|
| `databricks/simulate_polling.py` | The simulator (365 lines) |
| `databricks/SIMULATE_POLLING_README.md` | Full documentation |
| `SIMULATION_SUMMARY.md` | Overview and results |
| `cluster_data/` | Input: JSON cluster snapshots |
| `databricks/sim_output/` | Output: logs and reports |

## Next: More Details

Read `databricks/SIMULATE_POLLING_README.md` for:
- How it works in detail
- Verification checklist
- Troubleshooting guide
- Integration with CI/CD
- Understanding the mocking approach

Read `SIMULATION_SUMMARY.md` for:
- What was created
- Example results
- Architecture diagram
- Typical workflow
