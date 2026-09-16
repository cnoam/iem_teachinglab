# test_serverless_quota_scenario.py
#
# Acceptance scenario: a student runs a 5-cell notebook, each cell well
# under the execution timeout so the timeout never fires. The daily quota is
# set to 1.5x one full run. They run the notebook a second time; it should
# halt partway through that second run once cumulative usage crosses quota.
#
# This exercises resource_manager.serverless_quota's core aggregation/
# decision logic (union_seconds, is_over_quota) against that concrete
# scenario, ahead of Step 2 wiring it to real query-history ingest and the
# group-removal enforcement lever (databricks/serverless_quota_plan.md,
# section 2.5). The enforcement lever's confirmed behavior -- it blocks a
# *new* command, never one already running -- is exactly what
# simulate_two_runs() models: the quota is checked before each cell
# dispatch, never mid-cell.

from databricks.resource_manager.serverless_quota import union_seconds, is_over_quota

NUM_CELLS = 5
CELL_SECONDS = 120  # 2 minutes/cell -- comfortably under any execution timeout
ONE_RUN_SECONDS = NUM_CELLS * CELL_SECONDS  # 600s = 10 min
QUOTA_SECONDS = 1.5 * ONE_RUN_SECONDS  # 900s = 15 min ("1.5 runs")


def simulate_two_runs(cell_seconds=CELL_SECONDS, num_cells=NUM_CELLS,
                       quota_seconds=QUOTA_SECONDS, num_runs=2):
    """
    Simulates running `num_cells` sequential cells, `num_runs` times, with a
    quota check -- based only on already-completed cells -- before each cell
    dispatch. Mirrors the real enforcement lever: it can refuse the next
    cell, but never interrupts a cell already in flight.

    Returns (completed_intervals, blocked_at), where blocked_at is the
    (run_index, cell_index) of the first refused cell (1-based), or None if
    every cell across every run completed.
    """
    completed = []
    clock = 0.0
    for run in range(1, num_runs + 1):
        for cell in range(1, num_cells + 1):
            usage_so_far = union_seconds(completed)
            if is_over_quota(usage_so_far, quota_seconds):
                return completed, (run, cell)
            start = clock
            end = clock + cell_seconds
            completed.append((start, end))
            clock = end
    return completed, None


def test_notebook_halts_partway_through_second_run():
    completed, blocked_at = simulate_two_runs()

    # Run 1 (5 cells) completes in full: 1.0 run of usage, under the 1.5x
    # quota. Run 2: cells 1-2 push cumulative usage to 1.2 -> 1.4 runs
    # (both still under 1.5, so both are allowed to start); cell 3's
    # pre-check (1.4 < 1.5) also allows it to start, and it finishes at
    # 1.6 runs, crossing quota -- so cell 4's pre-check refuses it.
    assert blocked_at == (2, 4), f"expected block at run 2, cell 4; got {blocked_at}"
    assert len(completed) == NUM_CELLS + 3  # all of run 1, first 3 of run 2

    total_seconds = union_seconds(completed)
    assert total_seconds == 8 * CELL_SECONDS  # 960s = 16 min
    assert is_over_quota(total_seconds, QUOTA_SECONDS)  # 16 min > 15 min quota


def test_single_run_never_blocks_under_a_generous_quota():
    # Sanity check: with quota == one full run, a single complete run never
    # blocks (the pre-check for the last cell sees usage still under quota).
    completed, blocked_at = simulate_two_runs(num_runs=1, quota_seconds=ONE_RUN_SECONDS)
    assert blocked_at is None
    assert len(completed) == NUM_CELLS


def test_union_seconds_matches_sum_for_non_overlapping_cells():
    # For this scenario (one user, strictly sequential cells) union and sum
    # coincide -- union-of-intervals only differs from sum when a group's
    # members run concurrently (plan section 2.3a). Confirms no double- or
    # under-counting artifact sneaks in for the simple, non-overlapping case.
    completed, _ = simulate_two_runs(num_runs=2, quota_seconds=float('inf'))
    assert union_seconds(completed) == sum(e - s for s, e in completed)
    assert len(completed) == 2 * NUM_CELLS


def test_union_seconds_merges_concurrent_group_members():
    # Two group members running overlapping cells shouldn't double-count --
    # this is the actual reason union was chosen over SUM (plan 2.3a).
    member_a = (0.0, 100.0)
    member_b = (50.0, 200.0)  # overlaps member_a from 50-100
    assert union_seconds([member_a, member_b]) == 200.0  # not 100+150=250
