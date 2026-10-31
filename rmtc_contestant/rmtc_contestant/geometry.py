"""Validated geometry for the public 9x9 relative-position encoding.

Coordinates are (x, y): right increases x and down increases y.  The only
allowed 1 is the central self marker.  No 2 means an overlapping entity.
"""

from typing import List, Set, Tuple, Union

Position = Tuple[int, int]


def validate_position(value: object) -> Position:
    """Normalize a two-element integer list/tuple; reject booleans and floats."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('position must be a two-element integer list or tuple')
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise ValueError('position coordinates must be integers')
    return value[0], value[1]


def validate_map(width: int, height: int) -> None:
    """Require positive integer dimensions (booleans are not dimensions)."""
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (width, height)):
        raise ValueError('map dimensions must be positive integers')


def in_bounds(position: Position, width: int, height: int) -> bool:
    """Return whether a validated coordinate lies inside the map."""
    x, y = position
    return 0 <= x < width and 0 <= y < height


def decode_relative_grid(rows: Union[str, List[str], Tuple[str, ...]]) -> Position:
    """Decode the protocol's 89-char newline string or nine 9-char rows."""
    if isinstance(rows, str):
        rows = rows.split('\n')
    if not isinstance(rows, (list, tuple)) or len(rows) != 9:
        raise ValueError('relative grid must contain exactly nine rows')
    marker = None
    for y, row in enumerate(rows):
        if not isinstance(row, str) or len(row) != 9:
            raise ValueError('each relative grid row must contain nine characters')
        for x, character in enumerate(row):
            if character not in '012':
                raise ValueError('relative grid may contain only 0, 1 and 2')
            if (x, y) == (4, 4):
                if character != '1':
                    raise ValueError('relative grid center must be 1')
            elif character == '1':
                raise ValueError('only the relative grid center may be 1')
            if character == '2':
                if marker is not None:
                    raise ValueError('relative grid may contain at most one 2')
                marker = (x - 4, y - 4)
    return (0, 0) if marker is None else marker


def absolute_position(self_position: Position, rows: List[str]) -> Position:
    """Restore one entity's absolute position using current self.position."""
    x, y = validate_position(self_position)
    dx, dy = decode_relative_grid(rows)
    return x + dx, y + dy


def visible_cells(position: Position, width: int, height: int,
                  vision_radius: int) -> Set[Position]:
    """Return square/Chebyshev vision clipped to the map, for radius 0..4."""
    position = validate_position(position)
    validate_map(width, height)
    if not in_bounds(position, width, height):
        raise ValueError('self position is outside the map')
    if (isinstance(vision_radius, bool) or not isinstance(vision_radius, int)
            or not 0 <= vision_radius <= 4):
        raise ValueError('vision_radius must be an integer from 0 to 4')
    x, y = position
    return {(xx, yy)
            for yy in range(max(0, y - vision_radius), min(height, y + vision_radius + 1))
            for xx in range(max(0, x - vision_radius), min(width, x + vision_radius + 1))}
