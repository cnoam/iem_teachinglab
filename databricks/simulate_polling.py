"""
Simulation script for cluster polling based on JSON data dumps.

Reads cluster data from JSON files in ascending order (by timestamp in filename),
simulates time progression, and runs the actual polling logic without triggering
external systems (email, Databricks API).

Uses unittest.mock to patch external dependencies like datetime and email sending.

Usage:
    python -m databricks.simulate_polling [--data_dir ../cluster_data] [--db sim_clusters.db]
"""

import json
import logging
import os
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from unittest import mock
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import databricks as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the actual polling module
from databricks import poll_clusters
from databricks.database.db_operations import SqliteDatabase, create_tables, ClusterUptime, ClusterInfo


# ============================================================================
# CONFIGURATION AND LOGGING
# ============================================================================

class SimulationConfig:
    """Configuration for the simulation."""

    def __init__(self,
                 data_dir: Path,
                 db_file: Path,
                 warn_threshold_minutes: float = 180,
                 terminate_threshold_minutes: float = 210,
                 output_dir: Path = Path('sim_output')):
        self.data_dir = Path(data_dir)
        self.db_file = Path(db_file)
        self.warn_threshold_minutes = warn_threshold_minutes
        self.terminate_threshold_minutes = terminate_threshold_minutes
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)


class EmailLog:
    """Track emails that would be sent."""

    emails_sent: List[Dict] = []

    @classmethod
    def reset(cls):
        cls.emails_sent = []

    @classmethod
    def log_email(cls, subject: str, body: str, recipients: List[str]):
        """Log an email instead of sending it."""
        cls.emails_sent.append({
            'subject': subject,
            'body': body,
            'recipients': recipients,
            'timestamp': datetime.now().isoformat()
        })


# ============================================================================
# SIMULATION ENGINE
# ============================================================================

class PollingSimulator:
    """Simulates the polling process using JSON data files."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.data_files: List[Path] = []
        self.simulation_time: Optional[datetime] = None
        self.mock_get_clusters_responses: List[List[dict]] = []
        self.deleted_clusters: set = set()
        self.permission_changes: List[Dict] = []

        # Initialize database
        self.db = SqliteDatabase(str(config.db_file))
        ClusterUptime.bind(self.db)
        ClusterInfo.bind(self.db)
        with self.db.connection_context():
            create_tables(self.db)

    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the simulation."""
        logger = logging.getLogger('SIMULATION')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Clear existing handlers
        logger.handlers.clear()

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # File handler
        log_file = self.config.output_dir / 'simulation.log'
        fh = logging.FileHandler(log_file, mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        return logger

    def load_data_files(self) -> bool:
        """Load and sort JSON data files by timestamp in filename."""
        pattern = re.compile(r'clusters(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})\.json')

        for file in sorted(self.config.data_dir.glob('clusters*.json')):
            match = pattern.search(file.name)
            if match:
                self.data_files.append(file)
                self.logger.info(f"Loaded data file: {file.name}")

        if not self.data_files:
            self.logger.error(f"No cluster JSON files found in {self.config.data_dir}")
            return False

        self.logger.info(f"Total files to process: {len(self.data_files)}")
        return True

    def _extract_timestamp(self, filename: str) -> datetime:
        """Extract timestamp from filename like 'clusters2025-12-10_17:00:02.json'."""
        pattern = r'clusters(\d{4}-\d{2}-\d{2})_(\d{2}):(\d{2}):(\d{2})\.json'
        match = re.search(pattern, filename)
        if not match:
            raise ValueError(f"Cannot parse timestamp from {filename}")

        date_str, hour, minute, second = match.groups()
        timestamp_str = f"{date_str} {hour}:{minute}:{second}"
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

    def _create_mock_client(self, clusters_data: List[dict]):
        """Create a mock Databricks client that returns the provided clusters."""
        mock_client = MagicMock()

        def mock_get_clusters():
            return [c for c in clusters_data if c['cluster_id'] not in self.deleted_clusters]

        def mock_delete_cluster(cluster_name: str):
            for c in clusters_data:
                if c['cluster_name'] == cluster_name:
                    self.deleted_clusters.add(c['cluster_id'])
                    self.logger.info(f"[MOCK] Deleted cluster: {cluster_name}")
                    return
            self.logger.warning(f"[MOCK] Cluster {cluster_name} not found for deletion")

        def mock_set_cluster_permission(cluster_id: str, group_name=None, permission=None):
            self.permission_changes.append({
                'cluster_id': cluster_id,
                'group_name': group_name,
                'permission': permission
            })
            self.logger.info(f"[MOCK] Set permission for cluster {cluster_id}")

        mock_client.get_clusters = mock_get_clusters
        mock_client.delete_cluster = mock_delete_cluster
        mock_client.set_cluster_permission = mock_set_cluster_permission
        mock_client.ClusterPermission.ATTACH = "ATTACH"

        return mock_client

    def _create_mock_groups(self):
        """Create a mock Databricks groups API."""
        mock_groups = MagicMock()

        def mock_get_group_members(group_name: str):
            return [{'user_name': f'user@example.com'}]

        mock_groups.get_group_members = mock_get_group_members
        return mock_groups

    def run_simulation(self) -> bool:
        """Run the complete simulation."""
        self.logger.info("=" * 80)
        self.logger.info("CLUSTER POLLING SIMULATION START")
        self.logger.info("=" * 80)

        if not self.load_data_files():
            return False

        EmailLog.reset()

        with self.db.connection_context():
            for file_idx, data_file in enumerate(self.data_files, 1):
                self.simulation_time = self._extract_timestamp(data_file.name)
                self.logger.info("")
                self.logger.info(f"--- POLL {file_idx}/{len(self.data_files)} at {self.simulation_time} ---")

                # Load cluster data from JSON
                with open(data_file) as f:
                    clusters_data = json.load(f)

                # Run polling with mocked dependencies
                self._run_poll_with_mocks(clusters_data)

                # Log database state after this poll
                self._log_db_state()

            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("SIMULATION COMPLETE")
            self.logger.info("=" * 80)

        # Generate reports
        self._generate_reports()

        return True

    def _run_poll_with_mocks(self, clusters_data: List[dict]):
        """Run the actual poll_clusters.main() with mocked dependencies."""
        mock_client = self._create_mock_client(clusters_data)
        mock_groups = self._create_mock_groups()

        # Mock send_emails to log instead of sending
        def mock_send_emails(subject, body, recipients, logger=None):
            self.logger.info(f"[EMAIL] To: {recipients}")
            self.logger.info(f"[EMAIL] Subject: {subject}")
            EmailLog.log_email(subject, body, recipients)

        # Patch datetime.now() to return simulated time
        # We need to patch it in all modules that import it
        from datetime import datetime as real_datetime

        def mock_datetime_now():
            return self.simulation_time

        # Determine the correct module path for patching
        poll_module = 'databricks.poll_clusters' if 'databricks' in sys.modules else 'poll_clusters'

        with patch(f'{poll_module}.DataBricksClusterOps', return_value=mock_client), \
             patch(f'{poll_module}.DataBricksGroups', return_value=mock_groups), \
             patch(f'{poll_module}.send_emails', side_effect=mock_send_emails), \
             patch('databricks.resource_manager.cluster_uptime.datetime') as mock_dt_uptime, \
             patch('databricks.poll_clusters.datetime') as mock_dt_poll, \
             patch.dict(os.environ, {
                 'DATABRICKS_HOST': 'adb-mock.azuredatabricks.net',
                 'DATABRICKS_TOKEN': 'mock-token',
                 'DATABRICKS_MAX_UPTIME': str(self.config.terminate_threshold_minutes),
                 'DATABRICKS_WARN_UPTIME': str(self.config.warn_threshold_minutes),
                 'ADMIN_EMAIL': 'admin@example.com'
             }):
            # Setup datetime mocks - return simulated time from now() but keep other methods
            mock_dt_uptime.now = mock_datetime_now
            mock_dt_uptime.fromtimestamp = real_datetime.fromtimestamp
            mock_dt_uptime.timedelta = timedelta

            mock_dt_poll.now = mock_datetime_now
            mock_dt_poll.fromtimestamp = real_datetime.fromtimestamp
            mock_dt_poll.timedelta = timedelta

            # Call the actual polling main function
            try:
                poll_clusters.main()
            except Exception as e:
                self.logger.error(f"Error in poll_clusters.main(): {e}")
                import traceback
                self.logger.error(traceback.format_exc())

    def _log_db_state(self):
        """Log the current state of the database."""
        self.logger.debug("Database state after poll:")
        for record in ClusterUptime.select():
            info = ClusterInfo.get(ClusterInfo.cluster_id == record.id)
            total_sec = record.uptime_seconds + record.cumulative_seconds
            total_min = int(total_sec / 60)
            self.logger.debug(
                f"  {info.cluster_name}: {total_min}m total "
                f"(uptime={int(record.uptime_seconds//60)}m, "
                f"cumulative={int(record.cumulative_seconds//60)}m, "
                f"warn={record.warning_sent}, "
                f"term={record.force_terminated})"
            )

    def _generate_reports(self):
        """Generate simulation reports."""
        # Email log
        email_log_file = self.config.output_dir / 'emails_logged.json'
        with open(email_log_file, 'w') as f:
            json.dump(EmailLog.emails_sent, f, indent=2)
        self.logger.info(f"\nEmail log written to: {email_log_file}")

        # Database state at end
        db_state_file = self.config.output_dir / 'final_db_state.json'
        final_state = []
        with self.db.connection_context():
            for record in ClusterUptime.select():
                try:
                    info = ClusterInfo.get(ClusterInfo.cluster_id == record.id)
                    cluster_name = info.cluster_name
                except:
                    cluster_name = 'unknown'

                final_state.append({
                    'cluster_id': record.id,
                    'cluster_name': cluster_name,
                    'uptime_minutes': int(record.uptime_seconds / 60),
                    'cumulative_minutes': int(record.cumulative_seconds / 60),
                    'total_minutes': int((record.uptime_seconds + record.cumulative_seconds) / 60),
                    'warning_sent': record.warning_sent,
                    'force_terminated': record.force_terminated
                })

        with open(db_state_file, 'w') as f:
            json.dump(final_state, f, indent=2)
        self.logger.info(f"Final DB state written to: {db_state_file}")

        # Summary
        self.logger.info(f"\nSimulation output directory: {self.config.output_dir.absolute()}")
        self.logger.info(f"Total emails logged: {len(EmailLog.emails_sent)}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point for the simulation."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Simulate cluster polling with JSON data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m databricks.simulate_polling --data_dir cluster_data
  python -m databricks.simulate_polling --data_dir cluster_data --db sim.db --output_dir results
        """
    )
    parser.add_argument('--data_dir', type=Path, default=Path('cluster_data'),
                        help='Directory containing cluster JSON files')
    parser.add_argument('--db', type=Path, default=Path('sim_clusters.db'),
                        help='Simulation database file (default: sim_clusters.db)')
    parser.add_argument('--warn_threshold', type=float, default=180,
                        help='Warning threshold in minutes (default: 180)')
    parser.add_argument('--term_threshold', type=float, default=210,
                        help='Termination threshold in minutes (default: 210)')
    parser.add_argument('--output_dir', type=Path, default=Path('sim_output'),
                        help='Output directory for reports (default: sim_output)')

    args = parser.parse_args()

    # Resolve data_dir relative to current working directory if not absolute
    if not args.data_dir.is_absolute():
        args.data_dir = Path.cwd() / args.data_dir

    config = SimulationConfig(
        data_dir=args.data_dir,
        db_file=args.db,
        warn_threshold_minutes=args.warn_threshold,
        terminate_threshold_minutes=args.term_threshold,
        output_dir=args.output_dir
    )

    simulator = PollingSimulator(config)
    success = simulator.run_simulation()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
