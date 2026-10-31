"""Behavioral strategy contracts; Python 3.9 standard-library unittest."""
import copy
import unittest

from rmtc_contestant.state import WorldState
try:
    from rmtc_contestant.strategy import Strategy
except ImportError:
    Strategy = None

DELTAS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


def world(position=(2, 2), width=7, height=5, tick=1, session='s'):
    value = WorldState()
    value.session_id, value.tick = session, tick
    value.position, value.width, value.height = position, width, height
    value.vision_radius = 1
    value.self_info = {'hp': 100, 'alive': True, 'protected': False, 'team': 'A'}
    value.known_cells = {(x, y) for x in range(max(0, position[0]-1), min(width, position[0]+2))
                         for y in range(max(0, position[1]-1), min(height, position[1]+2))}
    value.visit_counts = {position: 1}
    return value


def resource(value=10, kind='resource_normal'):
    return {'type': kind, 'value': value}


def event(kind='explosion', start=1, end=5, rect=None, point=None):
    return {'kind': kind, 'start_tick': start, 'end_tick': end,
            'rect': rect, 'point': point, 'damage': None, 'duration': None}


def ai(events, session='s', tick=1, **extra):
    result = dict(session_id=session, tick=tick, events=events,
                  http_success=True, status='ok', error=None)
    result.update(extra)
    return result


def step(position, action):
    if action['action'] != 'move':
        return position
    dx, dy = DELTAS[action['direction']]
    return position[0]+dx, position[1]+dy


class StrategyTests(unittest.TestCase):
    def make(self, stage=1):
        self.assertIsNotNone(Strategy, 'Strategy implementation is required')
        return Strategy(stage)

    def test_resource_value_per_distance(self):
        s, w = self.make(), world()
        w.resources = {(1, 2): resource(10), (4, 2): resource(40)}
        self.assertEqual(s.decide(w), {'action': 'move', 'direction': 'right'})

    def test_resource_vanish_drops_old_target(self):
        s, w = self.make(), world()
        w.resources = {(4, 2): resource(30)}
        self.assertEqual(s.decide(w)['direction'], 'right')
        w.tick += 1
        w.resources = {(1, 2): resource(10)}
        self.assertEqual(s.decide(w)['direction'], 'left')

    def test_unknown_exploration_discovers_map_without_two_cell_loop(self):
        s, w = self.make(), world((0, 0), 9, 6)
        positions = []
        for tick in range(1, 75):
            w.tick = tick
            action = s.decide(w)
            self.assertEqual(action['action'], 'move')
            w.position = step(w.position, action)
            self.assertTrue(0 <= w.position[0] < w.width and 0 <= w.position[1] < w.height)
            w.visit_counts[w.position] = w.visit_counts.get(w.position, 0)+1
            for x in range(max(0, w.position[0]-1), min(w.width, w.position[0]+2)):
                for y in range(max(0, w.position[1]-1), min(w.height, w.position[1]+2)):
                    w.known_cells.add((x, y))
            positions.append(w.position)
        self.assertEqual(len(w.known_cells), 54)
        self.assertGreater(len(set(positions[-20:])), 2)

    def test_reach_task_before_resource_then_completed_task_is_ignored(self):
        s, w = self.make(2), world()
        w.resources = {(1, 2): resource(100)}
        w.missions = [{'id': 'reach', 'type': 'reach', 'position': [4, 2]}]
        self.assertEqual(s.decide(w)['direction'], 'right')
        w.score = {'mission_completed_ids': ['reach']}
        w.tick += 1
        self.assertEqual(s.decide(w)['direction'], 'left')

    def test_reach_already_at_target_does_not_wait_forever(self):
        s, w = self.make(2), world()
        w.missions = [{'id': 'r', 'type': 'reach', 'position': list(w.position)}]
        w.resources = {(1, 2): resource()}
        self.assertEqual(s.decide(w)['direction'], 'left')

    def test_death_wait_and_protection_forbids_attack(self):
        s, w = self.make(2), world()
        w.enemies = {(3, 2): {'hp': 100, 'team': 'B'}}
        self.assertEqual(s.decide(w), {'action': 'attack', 'direction': 'right'})
        w.self_info['protected'] = True
        w.tick += 1
        self.assertNotEqual(s.decide(w)['action'], 'attack')
        w.self_info['alive'] = False
        self.assertEqual(s.decide(w), {'action': 'wait'})

    def test_low_health_flees_threat_but_does_not_defend_without_threat(self):
        s, w = self.make(2), world()
        w.self_info['hp'] = 5
        w.enemies = {(3, 2): {'hp': 100}}
        action = s.decide(w)
        self.assertIn(action['action'], ('move', 'defend'))
        if action['action'] == 'move':
            p = step(w.position, action)
            self.assertGreater(abs(p[0]-3)+abs(p[1]-2), 1)
        w.enemies.clear()
        w.tick += 1
        self.assertEqual(s.decide(w)['action'], 'move')

    def test_protected_enemy_blocks_attack_at_enemy_behind(self):
        s, w = self.make(2), world()
        w.enemies = {(3, 2): {'protected': True}, (4, 2): {'hp': 1}}
        self.assertNotEqual(s.decide(w)['action'], 'attack')

    def test_stage1_never_attacks_or_defends(self):
        s, w = self.make(), world()
        w.enemies = {(3, 2): {'hp': 1}}
        self.assertEqual(s.decide(w)['action'], 'move')

    def test_explosion_escape_and_future_explosion_avoidance(self):
        s, w = self.make(2), world()
        s.decide(w)
        s.apply_ai(ai([event(rect=[2, 1, 4, 3])]))
        self.assertEqual(s.decide(w), {'action': 'move', 'direction': 'left'})
        w.position, w.tick = (1, 2), 2
        w.resources = {(3, 2): resource(100)}
        action = s.decide(w)
        self.assertNotEqual(step(w.position, action), (2, 2))

    def test_expired_explosion_and_failed_or_cross_session_ai_ignored(self):
        s, w = self.make(2), world()
        w.resources = {(3, 2): resource()}
        s.decide(w)
        for result in [ai([event(rect=[3, 2, 3, 2])], session='old'),
                       ai([event(rect=[3, 2, 3, 2])], http_success=False),
                       ai([event(rect=[3, 2, 3, 2])], tick=999)]:
            s.apply_ai(result)
            self.assertEqual(s.decide(w)['direction'], 'right')
        s.apply_ai(ai([event(rect=[3, 2, 3, 2])]))
        w.tick = 6
        self.assertEqual(s.decide(w)['direction'], 'right')

    def test_purity_avoids_defender_and_does_not_persist_defending(self):
        s, w = self.make(2), world()
        w.enemies = {(3, 2): {'hp': 20, 'defending': True}}
        s.decide(w)
        s.apply_ai(ai([event('purity')]))
        self.assertNotEqual(s.decide(w)['action'], 'attack')
        w.tick += 1
        w.enemies[(3, 2)] = {'hp': 20}
        self.assertEqual(s.decide(w)['action'], 'attack')

    def test_illusion_uncertain_never_reverses_command_and_inside_can_exit(self):
        s, w = self.make(2), world()
        w.resources = {(3, 2): resource()}
        s.decide(w)
        s.apply_ai(ai([event('illusion')]))
        self.assertEqual(s.decide(w)['direction'], 'right')
        s.apply_ai(ai([event('illusion', rect=[2, 2, 2, 2])]))
        self.assertEqual(s.decide(w)['direction'], 'right')

    def test_temporary_wall_expiry_filters_without_mutating_world(self):
        s, w = self.make(2), world((0, 0), 3, 1)
        w.resources = {(2, 0): resource()}
        s.decide(w)
        s.apply_ai(ai([event('world_split', rect=[1, 0, 1, 0])]))
        self.assertEqual(s.decide(w)['action'], 'wait')
        w.tick = 6
        before = copy.deepcopy(w.__dict__)
        self.assertEqual(s.decide(w), {'action': 'move', 'direction': 'right'})
        self.assertEqual(w.__dict__, before)

    def test_static_obstacle_survives_temporary_wall_expiry(self):
        s, w = self.make(2), world((0, 0), 3, 1)
        w.obstacles = {(1, 0)}
        w.resources = {(2, 0): resource()}
        s.decide(w)
        s.apply_ai(ai([event('world_split', rect=[1, 0, 1, 0])]))
        w.tick = 6
        self.assertEqual(s.decide(w), {'action': 'wait'})

    def test_session_change_clears_events_and_navigation(self):
        s, w = self.make(2), world()
        s.decide(w)
        s.apply_ai(ai([event(rect=[3, 2, 3, 2])]))
        w.session_id, w.tick = 'new', 1
        w.resources = {(3, 2): resource()}
        self.assertEqual(s.decide(w)['direction'], 'right')
        s.apply_ai(ai([event(rect=[3, 2, 3, 2])]))
        self.assertEqual(s.decide(w)['direction'], 'right')

    def test_resource_beyond_remaining_budget_not_selected(self):
        s, w = self.make(), world((2, 2), tick=99)
        w.resources = {(6, 2): resource(100), (1, 2): resource(1)}
        self.assertEqual(s.decide(w)['direction'], 'left')

    def test_range_two_attack_ignores_obstacle(self):
        s, w = self.make(2), world()
        w.obstacles = {(3, 2)}
        w.enemies = {(4, 2): {'hp': 100}}
        self.assertEqual(s.decide(w), {'action': 'attack', 'direction': 'right'})

    def test_collect_task_prefers_requested_resource_kind(self):
        s, w = self.make(2), world()
        w.missions = [{'id': 'c', 'type': 'collect', 'resource_type': 'resource_normal', 'count': 2}]
        w.resources = {(1, 2): resource(1), (3, 2): resource(100, 'resource_high')}
        self.assertEqual(s.decide(w)['direction'], 'left')
        w.score = {'mission_completed_ids': ['c']}
        w.tick += 1
        self.assertEqual(s.decide(w)['direction'], 'right')

    def test_real_ai_success_count_is_accepted(self):
        s, w = self.make(2), world()
        s.decide(w)
        s.apply_ai(ai([event(rect=[3, 2, 3, 2])], http_success=1))
        self.assertNotEqual(s.decide(w)['direction'], 'right')

    def test_stage2_keeps_five_hundred_tick_budget(self):
        s, w = self.make(2), world((2, 2), tick=100)
        w.resources = {(3, 2): resource(100)}
        self.assertEqual(s.decide(w), {'action': 'move', 'direction': 'right'})

    def test_official_resource_missions_are_prioritized(self):
        s, w = self.make(2), world()
        w.missions = [{'id': 'n', 'type': 'normal_resources', 'target': 2}]
        w.resources = {(1, 2): resource(1), (3, 2): resource(100, 'resource_high')}
        self.assertEqual(s.decide(w)['direction'], 'left')

    def test_event_end_tick_is_exclusive(self):
        s, w = self.make(2), world(tick=5)
        w.resources = {(3, 2): resource(100)}
        s.decide(w)
        s.apply_ai(ai([event(rect=[3, 2, 3, 2], start=1, end=5)]))
        self.assertEqual(s.decide(w)['direction'], 'right')

    def test_default_state_safe_wait_and_invalid_stage(self):
        self.assertEqual(self.make().decide(WorldState()), {'action': 'wait'})
        with self.assertRaises(ValueError):
            Strategy(3)


if __name__ == '__main__':
    unittest.main()
