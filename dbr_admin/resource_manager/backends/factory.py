"""
Selects a UsageBackend based on the QUOTA_MODE environment variable.

Not used by the classic path inside poll_clusters.py / end_of_day_operations.py's
own __main__ blocks (see classic.py's docstring for why) -- this is for any
other caller (future shared scripts, tests) that wants "the current mode's
backend" without hardcoding which module implements it.
"""
import os


def get_backend():
    """Returns the UsageBackend selected by QUOTA_MODE ('classic' if unset)."""
    mode = os.getenv('QUOTA_MODE', 'classic').strip().lower()
    if mode == 'classic':
        from .classic import ClassicBackend
        return ClassicBackend()
    if mode == 'serverless':
        from .serverless import ServerlessBackend
        return ServerlessBackend()
    raise ValueError(f"Unknown QUOTA_MODE: {mode!r}. Expected 'classic' or 'serverless'.")
