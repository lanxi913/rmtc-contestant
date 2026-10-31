import unittest

from rmtc_contestant.geometry import (
    absolute_position, decode_relative_grid, visible_cells,
)


def grid(dx=0, dy=0):
    rows = [list('000000000') for _ in range(9)]
    rows[4][4] = '1'
    if (dx, dy) != (0, 0):
        rows[4 + dy][4 + dx] = '2'
    return [''.join(row) for row in rows]


class GeometryTests(unittest.TestCase):
    def test_offsets_and_absolute_coordinates(self):
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                with self.subTest(dx=dx, dy=dy):
                    self.assertEqual(decode_relative_grid(grid(dx, dy)), (dx, dy))
                    self.assertEqual(absolute_position((8, 9), grid(dx, dy)), (8 + dx, 9 + dy))

    def test_accepts_protocol_newline_string(self):
        encoded = '\n'.join(grid(2, -3))
        self.assertEqual(decode_relative_grid(encoded), (2, -3))
        self.assertEqual(absolute_position((8, 9), encoded), (10, 6))

    def test_rejects_invalid_grid_shapes_and_symbols(self):
        invalid = [[], grid()[:8], ['00000000'] * 9, ['0000000000'] * 9,
                   '\n'.join(grid()) + '\n', [list(row) for row in grid()]]
        for row, text in [(0, 'x00000000'), (4, '000000000'),
                          (0, '100000000'), (0, '220000000')]:
            value = grid()
            value[row] = text
            invalid.append(value)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode_relative_grid(value)

    def test_rejects_non_integer_absolute_coordinates(self):
        for value in [(True, 2), (1.0, 2), [1], '12', {'x': 1, 'y': 2}]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    absolute_position(value, grid())

    def test_visibility_clips_square_to_map(self):
        self.assertEqual(visible_cells((0, 0), 3, 2, 1),
                         {(0, 0), (1, 0), (0, 1), (1, 1)})
        self.assertEqual(visible_cells((1, 1), 3, 3, 0), {(1, 1)})
        for radius in [-1, 5, True, 1.5]:
            with self.assertRaises(ValueError):
                visible_cells((0, 0), 3, 3, radius)


if __name__ == '__main__':
    unittest.main()
