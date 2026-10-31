"""Session-local memory built only from validated public perceptions.

WorldState.update is atomic: invalid frames leave the previous state untouched.
Vision is the clipped square (Chebyshev radius 0..4).  Missing visible resources
are deleted; obstacles persist, while enemies never persist across frames.
No referee files, event-language interpretation, action inference or ROS imports.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Dict, Optional, Set

from .geometry import (Position, absolute_position, validate_map,
                       validate_position, visible_cells)


class WorldState:
    """Mutable per-session memory.  Create one instance per controlled robot.

    Resources/enemies map absolute (x,y) to copied entity records whose position
    is normalized to (x,y); obstacles/known_cells/visible_cells are coordinate
    sets.  visit_counts counts accepted frames spent at each self position, not
    traversed paths inferred from events.  Consumers must treat exposed memory
    as read-only.  missions, score, mission_text and event_text are copied as-is.
    """

    def __init__(self) -> None:
        self.session_id: Optional[str] = None
        self.tick: Optional[int] = None
        self.position: Optional[Position] = None
        self.width = 0
        self.height = 0
        self.vision_radius = 0
        self.self_info: Dict[str, Any] = {}
        self.perception: Dict[str, Any] = {}
        self.resources: Dict[Position, Dict[str, Any]] = {}
        self.obstacles: Set[Position] = set()
        self.enemies: Dict[Position, Dict[str, Any]] = {}
        self.visible_cells: Set[Position] = set()
        self.known_cells: Set[Position] = set()
        self.visit_counts: Dict[Position, int] = {}
        self.missions = []
        self.score = {}
        self.mission_text = ''
        self.event_text = ''

    @property
    def blocked(self) -> Set[Position]:
        """Fresh obstacle + current visible enemy set for planner.bfs_paths."""
        return self.obstacles | set(self.enemies)

    def update(self, perception: Mapping) -> bool:
        """Accept a newer public frame; return True, or False on duplicate tick.

        A different session resets all memory, even with a smaller tick.  Old
        ticks within a session raise ValueError.  Duplicate frames are ignored
        in full, so neither visits nor mission/event data advance.  Require
        map.width/height, self.position, vision_radius and visible_entities.
        Malformed or out-of-map/out-of-vision entities raise ValueError; memory
        is changed only after validation and copying of the entire frame.
        """
        if not isinstance(perception, Mapping):
            raise ValueError('perception must be a mapping')
        session = perception.get('session_id')
        tick = perception.get('tick')
        if not isinstance(session, str) or not session:
            raise ValueError('session_id must be a nonempty string')
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise ValueError('tick must be a nonnegative integer')
        same_session = session == self.session_id
        if same_session and self.tick is not None:
            if tick < self.tick:
                raise ValueError('stale perception tick')
            if tick == self.tick:
                return False

        map_info = perception.get('map')
        self_info = perception.get('self')
        if not isinstance(map_info, Mapping) or not isinstance(self_info, Mapping):
            raise ValueError('map and self must be mappings')
        width, height = map_info.get('width'), map_info.get('height')
        validate_map(width, height)
        if same_session and (width, height) != (self.width, self.height):
            raise ValueError('map dimensions changed within a session')
        position = validate_position(self_info.get('position'))
        radius = perception.get('vision_radius')
        visible = visible_cells(position, width, height, radius)
        alive = self_info.get('alive', True)
        if not isinstance(alive, bool):
            raise ValueError('self.alive must be a boolean')
        if not alive:
            # A dead robot receives no observations, not an empty observed map.
            visible = set()
        entities = perception.get('visible_entities')
        if not isinstance(entities, (list, tuple)):
            raise ValueError('visible_entities must be a list')

        current_resources = {}
        current_obstacles = set()
        enemies = {}
        for entity in entities:
            if not isinstance(entity, Mapping) or not isinstance(entity.get('type'), str):
                raise ValueError('each visible entity must have a string type')
            entity_position = absolute_position(position, entity.get('position'))
            if entity_position not in visible:
                raise ValueError('entity is outside the map or current vision')
            record = deepcopy(dict(entity))
            record['position'] = entity_position
            kind = entity['type']
            if kind in ('resource_normal', 'resource_high'):
                current_resources[entity_position] = record
            elif kind == 'obstacle':
                current_obstacles.add(entity_position)
            elif (kind == 'robot' and entity.get('team') != self_info.get('team')
                  and entity.get('alive', True)):
                enemies[entity_position] = record

        resources = ({p: value for p, value in self.resources.items() if p not in visible}
                     if same_session else {})
        resources.update(current_resources)
        obstacles = (self.obstacles if same_session else set()) | current_obstacles
        known = (self.known_cells if same_session else set()) | visible
        visits = dict(self.visit_counts) if same_session else {}
        if alive:
            visits[position] = visits.get(position, 0) + 1
        # Do all potentially failing copies before committing any state.
        copied_self = deepcopy(dict(self_info))
        copied_perception = deepcopy(dict(perception))
        missions = deepcopy(perception.get('missions', []))
        score = deepcopy(perception.get('score', {}))
        mission_text = deepcopy(perception.get('mission_text', ''))
        event_text = deepcopy(perception.get('event_text', ''))
        self.session_id, self.tick = session, tick
        self.width, self.height = width, height
        self.position, self.vision_radius = position, radius
        self.self_info = copied_self
        self.perception = copied_perception
        self.resources, self.obstacles, self.enemies = resources, obstacles, enemies
        self.visible_cells, self.known_cells, self.visit_counts = visible, known, visits
        self.missions, self.score = missions, score
        self.mission_text, self.event_text = mission_text, event_text
        return True
