"""RMTC contestant package.

The protocol core deliberately has no ROS imports so it can be unit tested with
only Python's standard library.
"""

from .protocol import (
    ProtocolError,
    build_action,
    build_registration,
    parse_perception,
    validate_team_name,
)

__all__ = [
    "ProtocolError",
    "build_action",
    "build_registration",
    "parse_perception",
    "validate_team_name",
]
