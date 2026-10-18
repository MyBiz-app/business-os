"""Shared constants of the background jobs."""

LOCK_PREFIX = "bos-job:"  # advisory-lock key of a job: one run of each at a time
HORIZON_DAYS = 12 * 7  # open-ended series always have this much schedule ahead
