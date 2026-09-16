"""
Core, pure aggregation/decision logic for the serverless quota backend.

Deliberately dependency-free (no DB, no API client) so it can be unit-tested
against concrete scenarios without a workspace, and reused as-is once Step 2
wires it to real query-history ingest and the group-removal enforcement
lever. See databricks/serverless_quota_plan.md, sections 2.2 and 2.3a, for
the full design and the reasoning behind union-of-intervals over
sum-of-durations.
"""
from typing import Iterable, Tuple


def union_seconds(intervals: Iterable[Tuple[float, float]]) -> float:
    """
    Total wall-clock time covered by the union of [start, end) intervals
    (seconds, any consistent epoch), merging overlaps so concurrent
    execution across a group's members is not double-counted (plan
    section 2.3a: decided over SUM-of-durations for exactly this reason).
    """
    ivs = sorted((s, e) for s, e in intervals if e > s)
    if not ivs:
        return 0.0
    total = 0.0
    cur_start, cur_end = ivs[0]
    for s, e in ivs[1:]:
        if s <= cur_end:  # overlapping or touching -- merge
            cur_end = max(cur_end, e)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = s, e
    total += cur_end - cur_start
    return total


def is_over_quota(usage_seconds: float, threshold_seconds: float) -> bool:
    """True once cumulative usage reaches or exceeds the quota threshold."""
    return usage_seconds >= threshold_seconds
