import copy
import json
import unittest

from rmtc_contestant.protocol import parse_perception
from rmtc_contestant.state import WorldState
from test_geometry import grid


def perception(tick=1, position=(4, 4), radius=1, entities=None, session='s'):
    return {'tick': tick, 'session_id': session, 'vision_radius': radius,
            'self': {'team': 'A', 'position': list(position)},
            'map': {'width': 10, 'height': 10},
            'visible_entities': [] if entities is None else entities,
            'missions': [{'id': 'm', 'type': 'reach', 'position': [9, 9]}],
            'score': {'resource_value': 10}, 'event_text': '资源已被拾取：仅原样保存'}


def entity(kind, dx=0, dy=0, **fields):
    return dict(type=kind, position=grid(dx, dy), **fields)


class StateTests(unittest.TestCase):
    def test_accepts_public_json_position_string(self):
        source = perception(entities=[entity('resource_normal', 1, 0, id='r')])
        source['visible_entities'][0]['position'] = '\n'.join(grid(1, 0))
        decoded = parse_perception(json.dumps(source, ensure_ascii=False))
        state = WorldState()
        self.assertTrue(state.update(decoded))
        self.assertIn((5, 4), state.resources)

    def test_restores_absolute_entities_and_blocks_enemy_not_ally(self):
        state = WorldState()
        source = perception(entities=[entity('resource_normal', 1, 0, id='r', value=10),
                                      entity('obstacle', -1, 0),
                                      entity('robot', 0, 1, id='enemy', team='B'),
                                      entity('robot', 1, 1, id='ally', team='A')])
        self.assertTrue(state.update(source))
        self.assertEqual(state.position, (4, 4))
        self.assertEqual(state.resources[(5, 4)]['id'], 'r')
        self.assertEqual(state.obstacles, {(3, 4)})
        self.assertEqual(set(state.enemies), {(4, 5)})
        self.assertEqual(state.blocked, {(3, 4), (4, 5)})
        self.assertEqual(state.missions, source['missions'])
        self.assertEqual(state.score, source['score'])
        self.assertEqual(state.event_text, source['event_text'])
        self.assertEqual(state.perception, source)
        source['missions'][0]['id'] = 'mutated'
        self.assertEqual(state.perception['missions'][0]['id'], 'm')
        source['visible_entities'][0]['value'] = -1
        self.assertEqual(state.missions[0]['id'], 'm')
        self.assertEqual(state.resources[(5, 4)]['value'], 10)

    def test_visible_missing_resources_deleted_but_unseen_remembered(self):
        state = WorldState()
        state.update(perception(entities=[entity('resource_high', 1, 0, id='h'),
                                          entity('resource_normal', -1, 0, id='n'),
                                          entity('obstacle', 0, 1),
                                          entity('robot', 0, -1, team='B')]))
        state.update(perception(2, position=(6, 4)))
        self.assertNotIn((5, 4), state.resources)
        self.assertIn((3, 4), state.resources)
        self.assertEqual(state.obstacles, {(4, 5)})
        self.assertEqual(state.enemies, {})
        self.assertEqual(state.blocked, {(4, 5)})

    def test_session_change_resets_all_memory_and_accepts_lower_tick(self):
        state = WorldState()
        state.update(perception(50, entities=[entity('resource_high', 1, 0)]))
        state.update(perception(0, position=(0, 0), radius=0, session='new'))
        self.assertEqual(state.resources, {})
        self.assertEqual(state.obstacles, set())
        self.assertEqual(state.known_cells, {(0, 0)})
        self.assertEqual(state.visit_counts, {(0, 0): 1})
        self.assertEqual(state.tick, 0)

    def test_duplicate_noop_and_stale_rejected(self):
        state = WorldState()
        state.update(perception(10))
        before = copy.deepcopy(state.__dict__)
        self.assertFalse(state.update(perception(10, position=(8, 8))))
        self.assertEqual(state.__dict__, before)
        with self.assertRaises(ValueError):
            state.update(perception(9))
        self.assertEqual(state.__dict__, before)

    def test_coverage_and_visit_counts_only_advance_once_per_new_tick(self):
        state = WorldState()
        state.update(perception(1, position=(0, 0), radius=1))
        self.assertEqual(state.known_cells, {(0, 0), (1, 0), (0, 1), (1, 1)})
        state.update(perception(2, position=(0, 0), radius=0))
        self.assertEqual(state.visit_counts[(0, 0)], 2)
        self.assertEqual(state.visible_cells, {(0, 0)})
        self.assertEqual(len(state.known_cells), 4)

    def test_invalid_entity_or_perception_is_rejected_atomically(self):
        state = WorldState()
        state.update(perception())
        bad = []
        for field, value in [('vision_radius', 5), ('vision_radius', True),
                             ('tick', True), ('session_id', ''),
                             ('visible_entities', {})]:
            source = perception(2)
            source[field] = value
            bad.append(source)
        for position in [[True, 1], [1.5, 1], [10, 1]]:
            source = perception(2)
            source['self']['position'] = position
            bad.append(source)
        for entities in [[entity('resource_normal', 2, 0)],
                         [entity('obstacle', 0, 0, extra='ok'), {'type': 'robot', 'position': []}]]:
            bad.append(perception(2, entities=entities))
        source = perception(2)
        source['map']['width'] = 0
        bad.append(source)
        before = copy.deepcopy(state.__dict__)
        for source in bad:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    state.update(source)
                self.assertEqual(state.__dict__, before)

    def test_out_of_bounds_entity_rejected_even_if_within_relative_radius(self):
        with self.assertRaises(ValueError):
            WorldState().update(perception(position=(0, 0), entities=[entity('obstacle', -1, 0)]))

    def test_radius_zero_accepts_overlapping_entity(self):
        state = WorldState()
        state.update(perception(radius=0, entities=[entity('resource_normal', id='overlap')]))
        self.assertIn((4, 4), state.resources)

    def test_dead_frame_preserves_memory_without_discovering_or_visiting(self):
        state = WorldState()
        state.update(perception(1, entities=[entity('resource_normal', 1, 0)]))
        known = set(state.known_cells)
        visits = dict(state.visit_counts)
        source = perception(2, position=(8, 8))
        source['self']['alive'] = False
        state.update(source)
        self.assertIn((5, 4), state.resources)
        self.assertEqual(state.known_cells, known)
        self.assertEqual(state.visit_counts, visits)
        self.assertEqual(state.visible_cells, set())
        source = perception(3)
        source['self']['alive'] = False
        state.update(source)
        self.assertIn((5, 4), state.resources)

    def test_same_session_map_resize_is_rejected(self):
        state = WorldState()
        state.update(perception())
        source = perception(2)
        source['map']['width'] = 11
        with self.assertRaises(ValueError):
            state.update(source)


if __name__ == '__main__':
    unittest.main()
