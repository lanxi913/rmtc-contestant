"""Controller contract tests: deliberately independent of ROS and strategy."""
import json
import unittest
import os
import sys
import types
from unittest.mock import patch

try:
    from rmtc_contestant import node
except ImportError:
    from types import SimpleNamespace
    node = SimpleNamespace()


def frame(tick=1, session='s1', **extra):
    value = {'session_id': session, 'tick': tick,
             'map': {'width': 10, 'height': 10},
             'self': {'position': [2, 3], 'alive': True},
             'vision_radius': 2, 'visible_entities': [],
             'event_text': '', 'mission_text': ''}
    value.update(extra)
    return json.dumps(value)


class FakeWorld:
    def __init__(self):
        self.calls = []
    def update(self, perception):
        self.calls.append(perception)
        self.session_id = perception['session_id']
        self.tick = perception['tick']
        return True


class FakeStrategy:
    def __init__(self, action=None):
        self.action = action or {'action': 'move', 'direction': 'right'}
        self.calls = 0
        self.applied = []
    def decide(self, world):
        self.calls += 1
        return self.action
    def apply_ai(self, result):
        self.applied.append(result)


class FakeAI:
    def __init__(self):
        self.submissions = []
        self.results = []
        self.closed = False
    def submit(self, *args, **kwargs):
        self.submissions.append((args, kwargs))
        return True
    def poll(self, session_id):
        values, self.results = self.results, []
        return values
    def close(self):
        self.closed = True


class ControllerTests(unittest.TestCase):
    def make(self, stage=1, action=None, ai=None):
        strategy, world = FakeStrategy(action), FakeWorld()
        self.logs = []
        controller = node.Controller(strategy=strategy, world=world, stage=stage,
                                     ai=ai, log=self.logs.append)
        return controller, strategy, world

    def test_controller_exists_without_ros_import(self):
        self.assertTrue(callable(getattr(node, 'Controller', None)))

    def test_current_identity_and_duplicate_cached_replay(self):
        c, s, w = self.make()
        first = c.handle_perception(frame())
        self.assertEqual(json.loads(first), {'session_id': 's1', 'tick': 1,
                                           'action': 'move', 'direction': 'right'})
        self.assertEqual(c.handle_perception(frame()), first)
        self.assertEqual(s.calls, 1)
        self.assertEqual(len(w.calls), 1)
        self.assertIsNone(c.handle_perception(frame(0)))
        self.assertEqual(s.calls, 1)
        self.assertEqual(json.loads(self.logs[-1])['status'], 'stale')

    def test_new_session_does_not_reaccept_retired_session(self):
        c, s, w = self.make()
        c.handle_perception(frame(9))
        self.assertEqual(json.loads(c.handle_perception(frame(0, 's2')))['session_id'], 's2')
        self.assertIsNone(c.handle_perception(frame(10, 's1')))
        self.assertEqual(s.calls, 2)

    def test_safety_guards(self):
        for stage, action, self_info in [
            (1, {'action': 'attack', 'direction': 'up'}, {'alive': True}),
            (1, {'action': 'defend'}, {'alive': True}),
            (2, {'action': 'attack', 'direction': 'up'}, {'alive': True, 'protected': True}),
            (2, {'action': 'move', 'direction': 'up'}, {'alive': False}),
            (2, {'action': 'move', 'direction': 'diagonal'}, {'alive': True}),
            (2, {'action': 'teleport'}, {'alive': True}),
        ]:
            with self.subTest(stage=stage, action=action, self_info=self_info):
                c, _, _ = self.make(stage, action)
                self.assertEqual(json.loads(c.handle_perception(frame(**{'self': self_info})))['action'], 'wait')

    def test_strategy_exception_produces_current_wait(self):
        c, s, _ = self.make()
        def broken(world):
            raise RuntimeError('secret token must never be logged')
        s.decide = broken
        result = json.loads(c.handle_perception(frame()))
        self.assertEqual(result['action'], 'wait')
        self.assertNotIn('secret', ''.join(self.logs))

    def test_ai_uses_full_event_text_once_not_event_topic(self):
        ai = FakeAI()
        c, _, _ = self.make(2, ai=ai)
        c.handle_event(json.dumps({'session_id': 'old', 'text': 'latched old'}))
        c.handle_perception(frame(event_text='完整公告\n第二行', mission_text='任务'))
        c.handle_perception(frame(2, event_text='完整公告\n第二行'))
        self.assertEqual(len(ai.submissions), 1)
        self.assertEqual(ai.submissions[0][0][2], '完整公告\n第二行')

    def test_stage2_mission_fallback_once_and_session_reset(self):
        ai = FakeAI()
        c, s, _ = self.make(2, ai=ai)
        c.handle_perception(frame(mission_text='首帧任务'))
        c.handle_perception(frame(2, mission_text='其他任务'))
        self.assertEqual(len(ai.submissions), 1)
        c.handle_perception(frame(0, 's2', mission_text='新任务'))
        self.assertEqual(len(ai.submissions), 2)
        self.assertEqual(ai.submissions[-1][0][2], '新任务')
        c.close()
        self.assertTrue(ai.closed)

    def test_stage1_never_submits_ai(self):
        ai = FakeAI()
        c, _, _ = self.make(ai=ai)
        c.handle_perception(frame(event_text='公告'))
        self.assertEqual(ai.submissions, [])

    def test_ai_rejects_cross_session_future_and_invalid_result(self):
        ai = FakeAI()
        c, s, _ = self.make(2, ai=ai)
        c.handle_perception(frame())
        ai.results = [
            {'session_id': 'old', 'tick': 1, 'result': {'target': [1, 1]}},
            {'session_id': 's1', 'tick': 99, 'result': {'target': [1, 1]}},
            {'session_id': 's1', 'tick': 1, 'result': {'target': [99, 1]}},
            {'session_id': 's1', 'tick': 1, 'result': {'target': [1, 1]}},
        ]
        c.handle_perception(frame(2))
        self.assertEqual(s.applied, [{'target': [1, 1]}])

    def test_json_tick_log_contains_receipt_and_no_raw_sensitive_fields(self):
        c, _, _ = self.make()
        c.handle_perception(frame(action_result={'status': 'ok'}, token='do-not-log'))
        record = json.loads(self.logs[-1])
        self.assertEqual(record['perception']['tick'], 1)
        self.assertEqual(record['action']['action'], 'move')
        self.assertEqual(record['receipt'], {'status': 'ok'})
        self.assertNotIn('do-not-log', self.logs[-1])

    def test_actual_ai_poll_contract_and_last_action_receipt(self):
        ai = FakeAI()
        c, s, _ = self.make(2, ai=ai)
        c.handle_perception(frame())
        event = {'id': 'e1', 'kind': 'explosion', 'start_tick': 3,
                 'end_tick': 5, 'rect': [1, 1, 3, 3], 'point': None,
                 'damage': 20, 'duration': 2}
        result = {'session_id': 's1', 'tick': 1, 'status': 'ok',
                  'http_success': 1, 'error': None, 'events': [event]}
        ai.results = [result]
        c.handle_perception(frame(2, **{'self': {'position': [2, 3], 'alive': True,
                                                'last_action': {'tick': 1, 'moved': True}}}))
        self.assertEqual(s.applied, [result])
        self.assertEqual(json.loads(self.logs[-1])['receipt'], {'tick': 1, 'moved': True})

    def test_invalid_structured_events_are_not_applied(self):
        ai = FakeAI()
        c, s, _ = self.make(2, ai=ai)
        c.handle_perception(frame())
        ai.results = [{'session_id': 's1', 'tick': 1, 'status': 'ok',
                       'events': [{'id': 'bad', 'kind': 'explosion',
                                   'start_tick': 5, 'end_tick': 3,
                                   'rect': [0, 0, 99, 99], 'point': None,
                                   'damage': -1, 'duration': 0}]}]
        c.handle_perception(frame(2))
        self.assertEqual(s.applied, [])

    def test_invalid_stage_rejected(self):
        with self.assertRaises(ValueError):
            self.make(3)


class RosAdapterTests(unittest.TestCase):
    def test_main_topics_qos_registration_and_current_callback(self):
        publishers, subscriptions = {}, {}
        class Logger:
            def info(self, message):
                json.loads(message)
            def warning(self, message):
                pass
        class Publisher:
            def __init__(self, profile):
                self.profile, self.messages = profile, []
            def publish(self, message):
                self.messages.append(message.data)
        class FakeNode:
            def __init__(self, name):
                pass
            def create_publisher(self, kind, topic, profile):
                publishers[topic] = Publisher(profile)
                return publishers[topic]
            def create_subscription(self, kind, topic, callback, profile):
                subscriptions[topic] = (callback, profile)
                return callback
            def get_logger(self):
                return Logger()
            def destroy_node(self):
                pass
        class Message:
            def __init__(self, data):
                self.data = data
        def spin(instance):
            subscriptions['/team_B/perception'][0](Message(frame()))
            self.assertEqual(json.loads(publishers['/team_B/action'].messages[-1])['tick'], 1)
        def module(name, **values):
            result = types.ModuleType(name)
            result.__dict__.update(values)
            return result
        modules = {
            'rclpy': module('rclpy', init=lambda **kw: None, spin=spin,
                            ok=lambda: True, shutdown=lambda: None),
            'rclpy.node': module('rclpy.node', Node=FakeNode),
            'rclpy.qos': module('rclpy.qos', QoSProfile=lambda **kw: kw,
                ReliabilityPolicy=types.SimpleNamespace(RELIABLE='reliable'),
                DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL='transient', VOLATILE='volatile')),
            'std_msgs': module('std_msgs'),
            'std_msgs.msg': module('std_msgs.msg', String=Message),
            'rmtc_contestant.strategy': module('rmtc_contestant.strategy', Strategy=lambda **kw: FakeStrategy()),
            'rmtc_contestant.state': module('rmtc_contestant.state', WorldState=FakeWorld),
        }
        with patch.dict(sys.modules, modules), patch.dict(os.environ,
                {'TEAM': 'B', 'TEAM_NAME': '测试队', 'RMTC_STAGE': '1'}, clear=True):
            node.main()
        self.assertEqual(set(publishers), {'/team_B/action', '/team_B/registration'})
        self.assertEqual(json.loads(publishers['/team_B/registration'].messages[0])['name'], '测试队')
        self.assertEqual(publishers['/team_B/registration'].profile,
                         {'depth': 1, 'reliability': 'reliable', 'durability': 'transient'})
        self.assertEqual(subscriptions['/referee/event_text'][1]['depth'], 128)
        self.assertEqual(subscriptions['/team_B/perception'][1]['durability'], 'volatile')
        self.assertEqual(subscriptions['/referee/mission'][1]['depth'], 1)
        self.assertEqual(subscriptions['/referee/team_registry'][1]['depth'], 1)


if __name__ == '__main__':
    unittest.main()
