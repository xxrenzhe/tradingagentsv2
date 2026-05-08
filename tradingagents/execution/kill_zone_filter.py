"""
Kill Zone Time Filter for Trading Strategies

This module provides utilities to filter out Kill Zone trading sessions
based on ICT (Inner Circle Trader) theory.

Kill Zones are high-volatility institutional trading periods that may not
be suitable for certain reversal strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def is_kill_zone(timestamp: datetime) -> bool:
    """
    Check if a timestamp falls within a Kill Zone period.

    Kill Zones (EST/EDT):
    - NY AM Kill Zone: 8:30 - 11:30
    - NY PM Kill Zone: 13:30 - 16:00

    Args:
        timestamp: datetime object (should be timezone-aware)

    Returns:
        True if timestamp is in a Kill Zone, False otherwise

    Example:
        >>> from datetime import datetime, timezone
        >>> import pytz
        >>>
        >>> # NY AM Kill Zone
        >>> ny_tz = pytz.timezone('America/New_York')
        >>> ts = ny_tz.localize(datetime(2026, 5, 8, 10, 0))
        >>> is_kill_zone(ts)
        True
        >>>
        >>> # Asian session (not Kill Zone)
        >>> ts = ny_tz.localize(datetime(2026, 5, 8, 20, 0))
        >>> is_kill_zone(ts)
        False
    """
    # Convert to NY time
    try:
        import pytz
        ny_tz = pytz.timezone('America/New_York')
        ny_time = timestamp.astimezone(ny_tz)
    except Exception:
        # Fallback: assume timestamp is already in correct timezone
        ny_time = timestamp

    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM Kill Zone: 8:30 - 11:30
    ny_am = (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30)

    # NY PM Kill Zone: 13:30 - 16:00
    ny_pm = (hour == 13 and minute >= 30) or (14 <= hour < 16)

    return ny_am or ny_pm


def get_session_name(timestamp: datetime) -> str:
    """
    Get the trading session name for a given timestamp.

    Sessions (EST/EDT):
    - Asian: 18:00 - 02:00
    - London: 02:00 - 08:30
    - NY AM Kill Zone: 08:30 - 11:30
    - Lunch: 11:30 - 13:30
    - NY PM Kill Zone: 13:30 - 16:00
    - After Hours: 16:00 - 18:00

    Args:
        timestamp: datetime object (should be timezone-aware)

    Returns:
        Session name as string

    Example:
        >>> from datetime import datetime
        >>> import pytz
        >>>
        >>> ny_tz = pytz.timezone('America/New_York')
        >>> ts = ny_tz.localize(datetime(2026, 5, 8, 10, 0))
        >>> get_session_name(ts)
        'NY_AM_Kill_Zone'
    """
    # Convert to NY time
    try:
        import pytz
        ny_tz = pytz.timezone('America/New_York')
        ny_time = timestamp.astimezone(ny_tz)
    except Exception:
        ny_time = timestamp

    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM Kill Zone: 8:30 - 11:30
    if (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30):
        return 'NY_AM_Kill_Zone'

    # NY PM Kill Zone: 13:30 - 16:00
    if (hour == 13 and minute >= 30) or (14 <= hour < 16):
        return 'NY_PM_Kill_Zone'

    # Asian Session: 18:00 - 02:00
    if hour >= 18 or hour < 2:
        return 'Asian'

    # London Session: 02:00 - 08:30
    if 2 <= hour < 8 or (hour == 8 and minute < 30):
        return 'London'

    # Lunch: 11:30 - 13:30
    if (hour == 11 and minute > 30) or (hour == 12) or (hour == 13 and minute < 30):
        return 'Lunch'

    # After Hours: 16:00 - 18:00
    if 16 <= hour < 18:
        return 'After_Hours'

    return 'Unknown'


def should_trade(timestamp: datetime, *, allow_kill_zone: bool = False) -> bool:
    """
    Determine if trading should be allowed at the given timestamp.

    Args:
        timestamp: datetime object (should be timezone-aware)
        allow_kill_zone: If True, allow trading in Kill Zones (default: False)

    Returns:
        True if trading is allowed, False otherwise

    Example:
        >>> from datetime import datetime
        >>> import pytz
        >>>
        >>> ny_tz = pytz.timezone('America/New_York')
        >>>
        >>> # Kill Zone - not allowed by default
        >>> ts = ny_tz.localize(datetime(2026, 5, 8, 10, 0))
        >>> should_trade(ts)
        False
        >>>
        >>> # Kill Zone - allowed if explicitly enabled
        >>> should_trade(ts, allow_kill_zone=True)
        True
        >>>
        >>> # Asian session - always allowed
        >>> ts = ny_tz.localize(datetime(2026, 5, 8, 20, 0))
        >>> should_trade(ts)
        True
    """
    if allow_kill_zone:
        return True

    return not is_kill_zone(timestamp)


def get_kill_zone_stats(timestamps: list[datetime]) -> dict[str, Any]:
    """
    Calculate Kill Zone statistics for a list of timestamps.

    Args:
        timestamps: List of datetime objects

    Returns:
        Dictionary with statistics:
        - total: Total number of timestamps
        - kill_zone_count: Number in Kill Zone
        - non_kill_zone_count: Number not in Kill Zone
        - kill_zone_pct: Percentage in Kill Zone
        - session_breakdown: Count by session

    Example:
        >>> from datetime import datetime, timedelta
        >>> import pytz
        >>>
        >>> ny_tz = pytz.timezone('America/New_York')
        >>> base = ny_tz.localize(datetime(2026, 5, 8, 0, 0))
        >>> timestamps = [base + timedelta(hours=i) for i in range(24)]
        >>> stats = get_kill_zone_stats(timestamps)
        >>> stats['kill_zone_pct']
        20.833333333333336
    """
    if not timestamps:
        return {
            'total': 0,
            'kill_zone_count': 0,
            'non_kill_zone_count': 0,
            'kill_zone_pct': 0.0,
            'session_breakdown': {},
        }

    kill_zone_count = sum(1 for ts in timestamps if is_kill_zone(ts))
    non_kill_zone_count = len(timestamps) - kill_zone_count

    # Session breakdown
    session_counts: dict[str, int] = {}
    for ts in timestamps:
        session = get_session_name(ts)
        session_counts[session] = session_counts.get(session, 0) + 1

    return {
        'total': len(timestamps),
        'kill_zone_count': kill_zone_count,
        'non_kill_zone_count': non_kill_zone_count,
        'kill_zone_pct': (kill_zone_count / len(timestamps)) * 100,
        'session_breakdown': session_counts,
    }


# Example usage and testing
if __name__ == '__main__':
    import pytz
    from datetime import timedelta

    print("Kill Zone Filter - Example Usage")
    print("=" * 60)
    print()

    ny_tz = pytz.timezone('America/New_York')
    base = ny_tz.localize(datetime(2026, 5, 8, 0, 0))

    print("Testing different times:")
    print()

    test_times = [
        (0, 0, "Midnight"),
        (2, 0, "London Open"),
        (8, 30, "NY AM Kill Zone Start"),
        (10, 0, "NY AM Kill Zone"),
        (11, 30, "NY AM Kill Zone End"),
        (12, 0, "Lunch"),
        (13, 30, "NY PM Kill Zone Start"),
        (15, 0, "NY PM Kill Zone"),
        (16, 0, "After Hours"),
        (20, 0, "Asian Session"),
    ]

    for hour, minute, label in test_times:
        ts = ny_tz.localize(datetime(2026, 5, 8, hour, minute))
        in_kz = is_kill_zone(ts)
        session = get_session_name(ts)
        can_trade = should_trade(ts)

        status = "❌ BLOCKED" if in_kz else "✅ ALLOWED"
        print(f"{hour:02d}:{minute:02d} - {label:25s} - {session:20s} - {status}")

    print()
    print("=" * 60)
    print()

    # Calculate 24-hour stats
    timestamps = [base + timedelta(hours=i) for i in range(24)]
    stats = get_kill_zone_stats(timestamps)

    print("24-Hour Statistics:")
    print(f"  Total hours: {stats['total']}")
    print(f"  Kill Zone hours: {stats['kill_zone_count']} ({stats['kill_zone_pct']:.1f}%)")
    print(f"  Non-Kill Zone hours: {stats['non_kill_zone_count']} ({100-stats['kill_zone_pct']:.1f}%)")
    print()

    print("Session Breakdown:")
    for session, count in sorted(stats['session_breakdown'].items()):
        pct = (count / stats['total']) * 100
        print(f"  {session:20s}: {count:2d} hours ({pct:5.1f}%)")
