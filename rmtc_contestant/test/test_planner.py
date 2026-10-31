import unittest

from rmtc_contestant.planner import bfs_paths, shortest_path


class PlannerTests(unittest.TestCase):
    def test_all_paths_include_start_and_are_shortest_cardinal_steps(self):
        paths = bfs_paths((0, 0), 4, 3, blocked={(1, 0), (1, 1)})
        self.assertEqual(paths[(0, 0)], [])
        self.assertEqual(paths[(2, 0)], ['down', 'down', 'right', 'right', 'up', 'up'])
        self.assertEqual(len(paths), 10)
        deltas = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
        for target, path in paths.items():
            position = (0, 0)
            for direction in path:
                dx, dy = deltas[direction]
                position = (position[0] + dx, position[1] + dy)
                self.assertTrue(0 <= position[0] < 4 and 0 <= position[1] < 3)
                self.assertNotIn(position, {(1, 0), (1, 1)})
            self.assertEqual(position, target)

    def test_unreachable_and_out_of_bounds_targets_return_none(self):
        self.assertIsNone(shortest_path((0, 0), (2, 0), 3, 1, {(1, 0)}))
        self.assertIsNone(shortest_path((0, 0), (-1, 0), 3, 1))
        self.assertEqual(shortest_path((0, 0), (0, 0), 1, 1), [])

    def test_blocked_includes_enemy_and_blocked_start_can_leave(self):
        self.assertEqual(bfs_paths((0, 0), 2, 1, {(1, 0)}), {(0, 0): []})
        self.assertEqual(shortest_path((0, 0), (1, 0), 2, 1, {(0, 0), (99, 99)}), ['right'])

    def test_invalid_map_and_start_rejected(self):
        for start, width, height in [((-1, 0), 3, 3), ((3, 0), 3, 3),
                                     ((0, 0), 0, 3), ((0, 0), True, 3),
                                     ((0.0, 0), 3, 3)]:
            with self.assertRaises(ValueError):
                bfs_paths(start, width, height)


if __name__ == '__main__':
    unittest.main()
