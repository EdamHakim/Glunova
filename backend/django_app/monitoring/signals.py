"""Monitoring app signal hooks (reserved for future use).

The care coordination agent is no longer invoked on new CRITICAL ``HealthAlert``
rows; triggers are nutrition skip, psychology events, and cron/manual batch runs.
"""


def register() -> None:
    return
