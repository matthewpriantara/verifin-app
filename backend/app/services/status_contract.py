"""Shared status vocabulary for probes and evidence."""

NOT_PROVIDED = "NOT_PROVIDED"
COMPLETED = "COMPLETED"
FOUND = "FOUND"
NO_RESULTS = "NO_RESULTS"
NO_RELEVANT_RESULTS = "NO_RELEVANT_RESULTS"
UNAVAILABLE = "UNAVAILABLE"
PARSE_FAILED = "PARSE_FAILED"
INVALID_INPUT = "INVALID_INPUT"
LOGIN_REQUIRED = "LOGIN_REQUIRED"


def is_completed(status: str | None) -> bool:
    return status == COMPLETED


def is_unavailable(status: str | None) -> bool:
    return status in {UNAVAILABLE, PARSE_FAILED, INVALID_INPUT}
