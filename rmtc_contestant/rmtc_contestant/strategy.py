"""Deterministic public-perception-only policy (Python 3.9, no ROS).

API: Strategy(stage=1).decide(world) -> action dict; apply_ai(result) -> None.
Only structured AI events are consumed. Explosion zones are conservatively
avoided through end_tick (inclusive), illusion entry is avoided without guessing
inversion state, world_split walls expire in a private obstacle view, and purity
avoids attacking a currently reported defender. Angel/unrivaled/pepper/pan buffs
are NOT modelled: neither hidden enemy effects nor text are interpreted.
"""

from copy import deepcopy
from math import isfinite

from .geometry import visible_cells
from .planner import DIRECTIONS, bfs_paths


def _number(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else default


def _contains(event, position):
    rect = event.get('rect')
    if rect is not None:
        return rect[0] <= position[0] <= rect[2] and rect[1] <= position[1] <= rect[3]
    point = event.get('point')
    return point is not None and tuple(point) == position


class Strategy:
    """Stable greedy collection with exploration and conservative combat.

    Structured missions supported: reach(position), collect(resource_type), with
    id and optional completed flag; score.mission_completed_ids is authoritative.
    The policy assumes the public 100-tick match budget, not a hidden game clock.
    Unknown cells are traversable hypotheses; only observed obstacles/enemies or
    explicitly confirmed AI hazards block a plan. Every frame replans resources.
    """

    def __init__(self, stage=1):
        if isinstance(stage, bool) or stage not in (1, 2):
            raise ValueError('stage must be 1 or 2')
        self.stage = stage
        self._session = None
        self._tick = None
        self._events = []
        self._walls = []
        self._previous = None
        self._last_frame = None
        self._pending = []

    def apply_ai(self, result):
        """Merge validated event records, never prose or direct model actions.

        Results from another session, future requests or failed HTTP calls are
        ignored. Pre-first-perception results are held until their session binds.
        Malformed records are ignored defensively even though upstream validates.
        """
        if not isinstance(result, dict) or result.get('status') != 'ok':
            return
        http_success = result.get('http_success')
        if not ((type(http_success) is bool and http_success)
                or (type(http_success) is int and http_success > 0)):
            return
        tick = result.get('tick')
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            return
        if self._session is None:
            self._pending.append(deepcopy(result))
            return
        if result.get('session_id') != self._session or tick > self._tick:
            return
        events = result.get('events')
        if not isinstance(events, list):
            return
        for item in events:
            if not isinstance(item, dict):
                continue
            start, end = item.get('start_tick'), item.get('end_tick')
            if (any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end))
                    or start < 0 or end < start):
                continue
            rect, point = item.get('rect'), item.get('point')
            valid = True
            for value, length in ((rect, 4), (point, 2)):
                if value is not None and (not isinstance(value, (list, tuple)) or len(value) != length
                        or any(isinstance(v, bool) or not isinstance(v, int) for v in value)):
                    valid = False
            if not valid or (rect is not None and (rect[0] > rect[2] or rect[1] > rect[3])):
                continue
            copied = deepcopy(item)
            if copied.get('kind') == 'world_split':
                if copied not in self._walls:
                    self._walls.append(copied)
            elif end > self._tick and copied not in self._events:
                self._events.append(copied)

    def decide(self, world):
        """Return move/attack + direction, or wait/defend without direction.

        Does not modify world, read referee truth, or retain enemy defending.
        A low-HP threatened vehicle first retreats; if trapped it can defend.
        Escape cannot undo an explosion already resolved before this action.
        """
        if world.session_id != self._session:
            pending, self._pending = self._pending, []
            self._session, self._tick = world.session_id, world.tick
            self._events, self._walls = [], []
            self._previous, self._last_frame = None, None
            for result in pending:
                self.apply_ai(result)
        self._tick = world.tick
        if (world.position is None or world.tick is None or world.width <= 0 or world.height <= 0
                or not world.self_info.get('alive', True) or world.self_info.get('hp', 100) <= 0):
            return {'action': 'wait'}
        if self._last_frame != world.tick:
            old_position = getattr(self, '_position', None)
            if self._last_frame is not None and old_position != world.position:
                self._previous = old_position
            self._position, self._last_frame = world.position, world.tick
        self._events = [e for e in self._events if e['end_tick'] > world.tick]
        self._walls = [e for e in self._walls if e['end_tick'] > world.tick]
        active = [e for e in self._events if e['start_tick'] <= world.tick < e['end_tick']]
        cells = {(x, y) for x in range(world.width) for y in range(world.height)}
        obstacles = set(world.obstacles)
        for e in self._walls:
            if e['start_tick'] <= world.tick < e['end_tick']:
                obstacles.update(p for p in cells if _contains(e, p))
        solid = obstacles | set(world.enemies)
        explosion = {p for p in cells for e in self._events
                     if e.get('kind') == 'explosion' and _contains(e, p)}
        # Entering an illusion region triggers it. Already inside may exit;
        # uncertain announcements never cause a blind reverse-direction guess.
        illusion = {p for p in cells for e in active if e.get('kind') == 'illusion'
                    and not _contains(e, world.position) and _contains(e, p)}
        paths = bfs_paths(world.position, world.width, world.height, solid | explosion | illusion)
        if world.position in explosion:
            # Start may leave a blocked danger square; search through its region
            # for the nearest exit when a one-step escape is impossible.
            exits = [(len(path), p, path) for p, path in paths.items() if path and p not in explosion]
            if not exits:
                escape_paths = bfs_paths(world.position, world.width, world.height, solid | illusion)
                exits = [(len(path), p, path) for p, path in escape_paths.items() if path and p not in explosion]
            if exits:
                return self._move(min(exits)[2])
            return {'action': 'wait'}
        threats = self._targets(world.position, world.enemies)
        vulnerable = not world.self_info.get('protected', False)
        if self.stage == 2 and vulnerable and threats and world.self_info.get('hp', 100) <= 20:
            options = [(len(self._targets(p, world.enemies)),
                        -min(abs(p[0]-q[0])+abs(p[1]-q[1]) for q in world.enemies), path)
                       for p, path in paths.items() if len(path) == 1]
            if options:
                choice = min(options)
                if choice[0] < len(threats):
                    return self._move(choice[2])
            return {'action': 'defend'}
        horizon = 100 if self.stage == 1 else 500
        budget = max(0, horizon-world.tick)
        viable = {p: path for p, path in paths.items() if path and len(path) <= budget}
        if self.stage == 2:
            task_path = self._mission_path(world, viable)
            if task_path:
                return self._move(task_path)
        if self.stage == 2 and vulnerable and self._damage_mission_due(world):
            attack = self._attack_action(threats, active)
            if attack:
                return attack
        resource_path = self._resource_path(world, viable)
        if resource_path:
            return self._move(resource_path)
        if self.stage == 2 and vulnerable:
            attack = self._attack_action(threats, active)
            if attack:
                return attack
        return self._explore(world, paths)

    @staticmethod
    def _attack_action(threats, active):
        purity = any(e.get('kind') == 'purity' for e in active)
        attacks = [(min(20, max(0, _number(enemy.get('hp'), 100))), direction)
                   for direction, enemy in threats
                   if not enemy.get('protected', False)
                   and not (purity and enemy.get('defending', False))]
        if not attacks:
            return None
        return {'action': 'attack', 'direction': max(attacks)[1]}

    @staticmethod
    def _move(path):
        return {'action': 'move', 'direction': path[0]}

    @staticmethod
    def _targets(position, enemies):
        """Nearest living enemy on each 1..2 ray; obstacles do not stop shots."""
        result = []
        for direction, (dx, dy) in DIRECTIONS:
            for distance in (1, 2):
                enemy = enemies.get((position[0]+dx*distance, position[1]+dy*distance))
                if enemy is not None and enemy.get('alive', True) and enemy.get('hp', 100) > 0:
                    result.append((direction, enemy))
                    break
        return result

    @staticmethod
    def _resource_path(world, paths, kind=None):
        options = []
        for p, entity in world.resources.items():
            if p not in paths or (kind is not None and entity.get('type') != kind):
                continue
            default = 30 if entity.get('type') == 'resource_high' else 10
            value = _number(entity.get('value'), default)
            if value > 0:
                path = paths[p]
                options.append((-value/len(path), len(path), p, path))
        return min(options)[3] if options else None

    def _damage_mission_due(self, world):
        completed = world.score.get('mission_completed_ids', [])
        damage = _number(world.score.get('effective_damage'), 0)
        for mission in world.missions:
            if not isinstance(mission, dict) or mission.get('completed') \
                    or mission.get('id') in completed:
                continue
            if mission.get('type') == 'effective_damage':
                target = _number(mission.get('target'), 0)
                if damage < target:
                    return True
        return False

    def _mission_path(self, world, paths):
        completed = world.score.get('mission_completed_ids', [])
        reach, kinds = [], []
        for mission in world.missions:
            if (not isinstance(mission, dict) or mission.get('completed')
                    or mission.get('id') in completed):
                continue
            mission_type = mission.get('type')
            if mission_type == 'reach':
                position = mission.get('position')
                if isinstance(position, (list, tuple)) and len(position) == 2:
                    p = tuple(position)
                    if p in paths:
                        reach.append((len(paths[p]), p, paths[p]))
            elif mission_type in ('normal_resources', 'high_resources'):
                kinds.append('resource_normal' if mission_type == 'normal_resources'
                             else 'resource_high')
            elif mission_type == 'resource_value':
                target = _number(mission.get('target'), 0)
                if _number(world.score.get('resource_value'), 0) < target:
                    kinds.append(None)
            elif mission_type == 'collect':
                # Retain compatibility with the local strategy fixtures.
                kind = mission.get('resource_type')
                if kind in ('resource_normal', 'resource_high'):
                    kinds.append(kind)
        if reach:
            return min(reach)[2]
        # Official resource missions use their declared type; resource_value
        # uses any visible resource. Each frame replans from public perception.
        for kind in kinds:
            path = self._resource_path(world, paths, kind)
            if path:
                return path
        return None

    def _explore(self, world, paths):
        options = []
        for p, path in paths.items():
            if not path:
                continue
            gain = len(visible_cells(p, world.width, world.height, world.vision_radius) - world.known_cells)
            visits = world.visit_counts.get(p, 0)
            if gain:
                options.append((-gain, len(path), visits, p == self._previous, p, path))
        if options:
            return self._move(min(options)[5])
        # Fully surveyed or disconnected map: patrol least-visited reachable
        # cells rather than permanently waiting or switching two neighbors.
        patrol = [(world.visit_counts.get(p, 0), p == self._previous, len(path), p, path)
                  for p, path in paths.items() if path]
        return self._move(min(patrol)[4]) if patrol else {'action': 'wait'}
