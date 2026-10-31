import json
import unittest

from rmtc_contestant.protocol import (
    ProtocolError,
    build_action,
    build_registration,
    parse_perception,
    validate_team_name,
)


class ParsePerceptionTests(unittest.TestCase):
    def test_parses_perception_and_keeps_other_fields(self):
        source = {
            "tick": 148,
            "session_id": "example-match",
            "self": {"position": [8, 8]},
            "event_text": "",
        }

        perception = parse_perception(json.dumps(source))

        self.assertEqual(perception, source)

    def test_rejects_malformed_json_and_non_object_root(self):
        for source in ("{bad json", "[]", "null", '"text"'):
            with self.subTest(source=source):
                with self.assertRaises(ProtocolError):
                    parse_perception(source)

    def test_rejects_missing_or_non_integer_tick(self):
        for tick in (None, -1, False, True, 1.0, "1"):
            with self.subTest(tick=tick):
                with self.assertRaises(ProtocolError):
                    parse_perception(json.dumps({"tick": tick, "session_id": "s1"}))

        with self.assertRaises(ProtocolError):
            parse_perception(json.dumps({"session_id": "s1"}))

    def test_rejects_missing_or_invalid_session_id(self):
        for session_id in (None, 1, [], ""):
            with self.subTest(session_id=session_id):
                with self.assertRaises(ProtocolError):
                    parse_perception(json.dumps({"tick": 1, "session_id": session_id}))

        with self.assertRaises(ProtocolError):
            parse_perception(json.dumps({"tick": 1}))


class ActionSerializationTests(unittest.TestCase):
    def setUp(self):
        self.perception = parse_perception(
            '{"tick":148,"session_id":"example-match","self":{}}'
        )

    def test_serializes_lowercase_move_and_preserves_current_identity(self):
        payload = build_action(self.perception, "move", direction="right")

        self.assertEqual(
            json.loads(payload),
            {
                "tick": 148,
                "session_id": "example-match",
                "action": "move",
                "direction": "right",
            },
        )

    def test_serializes_lowercase_attack_and_preserves_current_identity(self):
        payload = build_action(self.perception, "attack", direction="up")

        self.assertEqual(
            json.loads(payload),
            {
                "tick": 148,
                "session_id": "example-match",
                "action": "attack",
                "direction": "up",
            },
        )

    def test_serializes_defend_and_wait_without_direction(self):
        for action in ("defend", "wait"):
            with self.subTest(action=action):
                payload = build_action(self.perception, action)
                self.assertEqual(
                    json.loads(payload),
                    {
                        "tick": 148,
                        "session_id": "example-match",
                        "action": action,
                    },
                )

    def test_rejects_invalid_action_or_direction_shape(self):
        for action, direction in (
            ("jump", None),
            ("MOVE", "right"),
            ("move", "RIGHT"),
            ("attack", "UP"),
            ("move", None),
            ("attack", "north"),
            ("defend", "up"),
            ("wait", "left"),
        ):
            with self.subTest(action=action, direction=direction):
                with self.assertRaises(ProtocolError):
                    build_action(self.perception, action, direction=direction)

    def test_rejects_unvalidated_or_invalid_perception_identity(self):
        with self.assertRaises(ProtocolError):
            build_action({"tick": True, "session_id": "s1"}, "wait")
        with self.assertRaises(ProtocolError):
            build_action({"tick": 1, "session_id": ""}, "wait")


class TeamNameValidationTests(unittest.TestCase):
    def test_accepts_utf8_name_within_byte_limit(self):
        names = ("x", "x" * 96, "队" * 32)  # 1, 96, and 96 UTF-8 bytes
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(validate_team_name(name), name)

        self.assertEqual(
            json.loads(build_registration("A", names[-1])),
            {"team": "A", "name": names[-1]},
        )

    def test_rejects_empty_oversized_or_line_broken_name(self):
        invalid_names = (
            "",
            "x" * 97,  # exactly 97 ASCII bytes
            "队" * 33,  # 99 UTF-8 bytes
            "name\nnext",
            "name\rnext",
            "\ud800",  # lone surrogate cannot be UTF-8 encoded
        )
        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ProtocolError):
                    validate_team_name(name)

    def test_accepts_registration_for_each_remaining_seat(self):
        for team in ("B", "C", "D"):
            with self.subTest(team=team):
                self.assertEqual(
                    json.loads(build_registration(team, "team")),
                    {"team": team, "name": "team"},
                )

    def test_rejects_invalid_registration_team(self):
        for team in ("a", "E", "", None, 1):
            with self.subTest(team=team):
                with self.assertRaises(ProtocolError):
                    build_registration(team, "team")

    def test_rejects_non_string_name(self):
        with self.assertRaises(ProtocolError):
            validate_team_name(None)


if __name__ == "__main__":
    unittest.main()
