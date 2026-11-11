#!/bin/bash -u
# Run one scheduled dbr_admin job and report its outcome (every error must be emailed).
#
#   run_job.sh <job-name> <timeout-seconds> <python-module>
#   e.g. run_job.sh periodic_poll 90 dbr_admin.poll_clusters
#
# Called from the server-only wrappers (~/periodic_poll.sh etc., see README.md), whose cron
# lines pipe output to `systemd-cat -t dbr_scripts`.
# Deliberately NOT `bash -e`: a failing or timed-out job must still reach job_status, which
# emails ADMIN_EMAIL on any non-zero exit (124 = killed by timeout) and counts the run for
# the daily report's health section.
JOB=$1
TIMEOUT=$2
MODULE=$3
REPO=${DBR_REPO:-/home/azureuser/iem_teachinglab}

logger -t dbr_scripts "$JOB starting"
cd "$REPO" || { logger -t dbr_scripts "$JOB: cannot cd $REPO"; exit 1; }
# shellcheck disable=SC1091
source dbr_admin/venv/bin/activate
export CLUSTER_UPTIMES_DB="$REPO/cluster_uptimes.db"

timeout -k 10 "$TIMEOUT" python -m "$MODULE"
rc=$?

# If even the reporter fails (DB or email broken), the journal line is all that's left --
# the daily report's health section / a missing daily report is the fallback alarm.
timeout 60 python -m dbr_admin.job_status "$JOB" "$rc" \
    || logger -t dbr_scripts "$JOB: job_status FAILED to report rc=$rc"
logger -t dbr_scripts "$JOB finished rc=$rc"
exit "$rc"
