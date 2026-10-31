"""Deterministic four-direction shortest paths; no strategy or ROS dependency."""

from collections import deque
from typing import Dict, Iterable, List, Optional

from .geometry import Position, in_bounds, validate_map, validate_position

# Fixed ordering resolves equal-length paths reproducibly.
DIRECTIONS = (('up', (0, -1)), ('down', (0, 1)),
              ('left', (-1, 0)), ('right', (1, 0)))


def bfs_paths(start: Position, width: int, height: int,
              blocked: Iterable[Position] = ()) -> Dict[Position, List[str]]:
    """Compute all reachable shortest direction lists in a single BFS.

    Include obstacles AND current visible enemy coordinates in blocked.  A
    blocked start can still leave (e.g. an overlapping entity).  Out-of-map
    blocked coordinates are harmless.  The start maps to an empty path.
    """
    start = validate_position(start)
    validate_map(width, height)
    if not in_bounds(start, width, height):
        raise ValueError('start is outside the map')
    blocked_set = {validate_position(value) for value in blocked}
    paths = {start: []}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for direction, (dx, dy) in DIRECTIONS:
            neighbor = (current[0] + dx, current[1] + dy)
            if (not in_bounds(neighbor, width, height)
                    or neighbor in blocked_set or neighbor in paths):
                continue
            paths[neighbor] = paths[current] + [direction]
            queue.append(neighbor)
    return paths


def shortest_path(start: Position, target: Position, width: int, height: int,
                  blocked: Iterable[Position] = ()) -> Optional[List[str]]:
    """Return shortest direction list, [] at start, or None when unreachable."""
    target = validate_position(target)
    return bfs_paths(start, width, height, blocked).get(target)
