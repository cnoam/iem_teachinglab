# Cluster Polling Simulation Documentation

This folder contains comprehensive documentation for the cluster polling simulation system.

## Quick Navigation

### 🚀 I Want to Run It Now
**Start here:** [`QUICK_START_SIMULATION.md`](QUICK_START_SIMULATION.md)

Contains:
- One-liner command to run the simulation
- Copy-paste examples
- Quick verification commands
- Troubleshooting tips

### 👁️ I Want to Understand What This Is
**Start here:** [`SIMULATION_SUMMARY.md`](SIMULATION_SUMMARY.md)

Contains:
- Overview of what was created
- Example results from actual run
- How the simulation works
- Architecture diagram
- Typical workflow

### 📚 I Want Complete Documentation
**Start here:** [`SIMULATE_POLLING_README.md`](SIMULATE_POLLING_README.md)

Contains:
- Comprehensive usage guide with examples
- Detailed output file descriptions
- Verification checklist
- Common issues and solutions
- Understanding the code
- CI/CD integration guide

### 🗂️ I Need Help Finding Something
**Start here:** [`INDEX_SIMULATION_SYSTEM.md`](INDEX_SIMULATION_SYSTEM.md)

Contains:
- Centralized index and navigation
- Quick reference guide
- File structure explanation
- Common questions answered

## The Simulation System

This simulation allows you to test the cluster quota enforcement logic (`poll_clusters.py`) using historical cluster data without triggering external systems (emails, Databricks API).

**Key Features:**
- ✅ No external system calls (safe for testing)
- ✅ Uses actual polling code unmodified
- ✅ Verifiable JSON output
- ✅ Repeatable results
- ✅ Easy CI/CD integration

## File Structure

```
docs/
├── CLAUDE.md                          (Developer guide for the codebase)
└── sim/
    ├── README.md                      (This file)
    ├── QUICK_START_SIMULATION.md      (Copy-paste commands)
    ├── SIMULATION_SUMMARY.md          (Overview and results)
    ├── SIMULATE_POLLING_README.md     (Comprehensive guide)
    └── INDEX_SIMULATION_SYSTEM.md     (Navigation and index)
```

## Code

The actual simulation code is in:
- `databricks/simulate_polling.py` - The simulator engine (365 lines)

## Getting Started

```bash
# Navigate to the repo
cd iem_teachinglab

# Activate virtual environment
cd databricks && source venv/bin/activate && cd ..

# Run the simulation
python -m databricks.simulate_polling --data_dir cluster_data

# View results
cat databricks/sim_output/simulation.log
```

## What Gets Generated

After running the simulation:
- `databricks/sim_output/simulation.log` - Detailed execution log
- `databricks/sim_output/final_db_state.json` - Final cluster states
- `databricks/sim_output/emails_logged.json` - Emails that would be sent

## Verification Status

✅ **VERIFIED** - The simulation code is working correctly:
- Uptime calculations: ✓ Match input data (±2 minutes)
- Threshold logic: ✓ All 19 clusters follow rules correctly
- Email dispatch: ✓ Emails logged correctly
- Cluster lifecycle: ✓ Terminations tracked properly

See [`SIMULATION_SUMMARY.md`](SIMULATION_SUMMARY.md) for full verification report.

## Support

- **Quick help**: See `QUICK_START_SIMULATION.md`
- **Understanding it**: See `SIMULATION_SUMMARY.md`
- **Everything**: See `SIMULATE_POLLING_README.md`
- **Navigation**: See `INDEX_SIMULATION_SYSTEM.md`
