"""Pure-standard-library helpers for the public RMTC JSON protocol.

This module intentionally has no ROS imports.  A ROS node can pass a received
``std_msgs/msg/String.data`` value to :func:`parse_perception`, then serialize
one action for that exact perception with :func:`build_action`.
"""

import json
from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple, Union


class ProtocolError(ValueError):
    """Raised when a public RMTC protocol value is malformed or unsafe to use."""


_ACTIONS = frozenset(("move", "attack", "defend", "wait"))
_DIRECTIONAL_ACTIONS = frozenset(("move", "attack"))
_DIRECTIONS = frozenset(("up", "down", "left", "right"))
_TEAMS = frozenset(("A", "B", "C", "D"))


JsonText = Union[str, bytes, bytearray]


def parse_perception(raw_perception: JsonText) -> Dict[str, Any]:
    """Parse and minimally validate a perception JSON object.

    The returned mapping retains every public field from the source JSON.  This
    core only requires a usable current ``tick`` and ``session_id``; later
    strategy layers can validate the fields they need.
    """

    if not isinstance(raw_perception, (str, bytes, bytearray)):
        raise ProtocolError("perception must be JSON text")

    try:
        perception = json.loads(raw_perception)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise ProtocolError("perception is not valid JSON") from error

    if not isinstance(perception, dict):
        raise ProtocolError("perception JSON root must be an object")

    _perception_identity(perception)
    return perception


def build_action(
    perception: Mapping[str, Any], action: str, direction: Optional[str] = None
) -> str:
    """Serialize one legal action bound to ``perception``'s tick and session.

    ``move`` and ``attack`` require a cardinal direction.  ``defend`` and
    ``wait`` must not carry one.  Action names and directions are accepted only
    in their protocol-required lowercase spelling.
    """

    tick, session_id = _perception_identity(perception)

    if not isinstance(action, str) or action not in _ACTIONS:
        raise ProtocolError("action must be move, attack, defend, or wait")

    payload: Dict[str, Any] = {
        "tick": tick,
        "session_id": session_id,
        "action": action,
    }

    if action in _DIRECTIONAL_ACTIONS:
        if not isinstance(direction, str) or direction not in _DIRECTIONS:
            raise ProtocolError("move and attack require a valid direction")
        payload["direction"] = direction
    elif direction is not None:
        raise ProtocolError("defend and wait must not include a direction")

    return _dump_json(payload)


def validate_team_name(name: str) -> str:
    """Return a legal display name or raise :class:`ProtocolError`.

    RMTC registration names must occupy 1--96 bytes after UTF-8 encoding and
    cannot contain line feed or carriage return characters.
    """

    if not isinstance(name, str):
        raise ProtocolError("team name must be a string")
    if "\n" in name or "\r" in name:
        raise ProtocolError("team name must not contain a newline")

    try:
        byte_length = len(name.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ProtocolError("team name must be UTF-8 encodable") from error

    if not 1 <= byte_length <= 96:
        raise ProtocolError("team name must contain 1 to 96 UTF-8 bytes")
    return name


def build_registration(team: str, name: str) -> str:
    """Serialize a registration JSON object after validating its display name."""

    if not isinstance(team, str) or team not in _TEAMS:
        raise ProtocolError("team must be one of A, B, C, or D")

    return _dump_json({"team": team, "name": validate_team_name(name)})


def _perception_identity(perception: Mapping[str, Any]) -> Tuple[int, str]:
    """Extract protocol-safe current action identity from a perception mapping."""

    if not isinstance(perception, Mapping):
        raise ProtocolError("perception must be an object")

    if "tick" not in perception:
        raise ProtocolError("perception is missing tick")
    tick = perception["tick"]
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise ProtocolError("perception tick must be a non-negative integer")

    if "session_id" not in perception:
        raise ProtocolError("perception is missing session_id")
    session_id = perception["session_id"]
    if not isinstance(session_id, str) or not session_id:
        raise ProtocolError("perception session_id must be a non-empty string")

    return tick, session_id


def _dump_json(payload: Dict[str, Any]) -> str:
    """Create compact JSON while retaining non-ASCII team names as UTF-8 text."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
