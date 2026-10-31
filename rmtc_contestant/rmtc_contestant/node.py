"""ROS-free controller and lazy ROS 2 executable for an RMTC contestant.

Only main() imports ROS. AI submit/poll must be nonblocking; no network request
or future.wait occurs on the perception callback. Event topics are diagnostic
only: authoritative AI text always comes from the current perception.
"""
import json
import math
import os
from collections.abc import Mapping

from .protocol import build_action, build_registration, parse_perception


def _redact(value):
    """Never echo credentials even if a referee receipt contains extra fields."""
    if isinstance(value, Mapping):
        return {str(k): _redact(v) for k, v in value.items()
                if not any(word in str(k).lower() for word in
                           ('token', 'secret', 'authorization', 'password', 'api_key'))}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


class Controller:
    """Accept JSON perceptions and return a current JSON action, or None.

    Inject strategy.decide(world), world.update(dict), and optional nonblocking
    AI client. strategy_factory enables clean per-session strategy instances.
    Retired sessions are never accepted again during this process lifetime.
    """
    def __init__(self, strategy, world=None, stage=1, ai=None, log=None,
                 strategy_factory=None):
        if isinstance(stage, bool) or stage not in (1, 2):
            raise ValueError('RMTC_STAGE must be 1 or 2')
        if world is None:
            from .state import WorldState
            world = WorldState()
        self.strategy, self.world = strategy, world
        self.stage, self.ai = stage, ai
        self.log = log or (lambda message: None)
        self.strategy_factory = strategy_factory
        self.session_id = None
        self.tick = None
        self.cached_action = None
        self.retired_sessions = set()
        self.ai_texts = set()
        self.first_frame = True
        self.last_ai_tick = -1

    def _record(self, perception, action, status):
        own = perception.get('self', {})
        if not isinstance(own, Mapping):
            own = {}
        summary = {key: perception.get(key) for key in ('session_id', 'tick')}
        summary.update({key: own.get(key) for key in ('position', 'alive', 'protected')})
        record = {'status': status, 'perception': summary,
                  'action': json.loads(action) if action else None,
                  'receipt': own.get('last_action', perception.get('action_result',
                              perception.get('last_action_result', perception.get('receipt'))))}
        self.log(json.dumps(_redact(record), ensure_ascii=False, separators=(',', ':')))

    def handle_event(self, raw):
        """Intentionally do not consume latched text as session-authoritative AI input."""
        return None

    def handle_perception(self, raw):
        try:
            perception = parse_perception(raw)
        except (ValueError, TypeError):
            self.log('{"status":"invalid_perception"}')
            return None
        session, tick = perception['session_id'], perception['tick']
        if session in self.retired_sessions:
            self._record(perception, None, 'retired_session')
            return None
        if session == self.session_id and self.tick is not None:
            if tick < self.tick:
                self._record(perception, None, 'stale')
                return None
            if tick == self.tick:
                self._record(perception, self.cached_action, 'replay')
                return self.cached_action
        try:
            accepted = self.world.update(perception)
        except (ValueError, TypeError, KeyError):
            self._record(perception, None, 'invalid_state')
            return None
        if not accepted:
            return None
        if session != self.session_id:
            if self.session_id is not None:
                self.retired_sessions.add(self.session_id)
                if self.strategy_factory is not None:
                    self.strategy = self.strategy_factory()
            self.session_id = session
            self.cached_action = None
            self.ai_texts.clear()
            self.first_frame = True
            self.last_ai_tick = -1
        self.tick = tick
        # All available AI results are from earlier asynchronous requests.
        self._poll_ai(perception)
        status = 'action'
        try:
            decision = self.strategy.decide(self.world)
            action = self._safe_action(perception, decision)
        except Exception:
            # Exception text may contain gateway credentials; never log it.
            action = build_action(perception, 'wait')
            status = 'strategy_error_wait'
        self.cached_action = action
        self._record(perception, action, status)
        # Action is fixed before scheduling AI; submit is nonblocking by contract.
        self._submit_ai(perception)
        self.first_frame = False
        return action

    def _safe_action(self, perception, decision):
        own = perception.get('self', {})
        if not isinstance(decision, Mapping) or not isinstance(own, Mapping):
            return build_action(perception, 'wait')
        action, direction = decision.get('action'), decision.get('direction')
        if (own.get('alive') is False or own.get('hp', 1) == 0
                or self.stage == 1 and action in ('attack', 'defend')
                or own.get('protected', False) and action == 'attack'):
            return build_action(perception, 'wait')
        try:
            return build_action(perception, action, direction)
        except (ValueError, TypeError):
            return build_action(perception, 'wait')

    def _submit_ai(self, perception):
        if self.stage != 2 or self.ai is None:
            return
        event = perception.get('event_text', '')
        mission = perception.get('mission_text', '')
        if not isinstance(event, str) or not isinstance(mission, str):
            return
        text = event if event.strip() else (mission if self.first_frame else '')
        if not text.strip() or text in self.ai_texts:
            return
        try:
            accepted = self.ai.submit(self.session_id, self.tick, text,
                                       perception['map']['width'], perception['map']['height'],
                                       perception['self']['position'], mission_text=mission)
            if accepted:
                self.ai_texts.add(text)
        except Exception:
            pass  # A failed optional AI request must never suppress an action.

    def _poll_ai(self, perception):
        if self.stage != 2 or self.ai is None:
            return
        try:
            results = self.ai.poll(self.session_id)
            for item in results:
                if not isinstance(item, Mapping):
                    continue
                if item.get('session_id') != self.session_id:
                    continue
                tick = item.get('tick')
                if (isinstance(tick, bool) or not isinstance(tick, int)
                        or tick > self.tick or tick < self.last_ai_tick):
                    continue
                result = item if 'events' in item else item.get('result')
                if 'events' in item and item.get('status') != 'ok':
                    continue
                if not self._valid_ai(result, perception):
                    continue
                apply = getattr(self.strategy, 'apply_ai', None)
                if callable(apply):
                    apply(dict(result))
                    self.last_ai_tick = tick
        except Exception:
            pass

    @staticmethod
    def _valid_ai(result, perception):
        """Defense in depth; AI client owns its full model schema validation."""
        if not isinstance(result, Mapping) or not result:
            return False
        def finite(value):
            if isinstance(value, float):
                return math.isfinite(value)
            if isinstance(value, Mapping):
                return all(finite(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return all(finite(v) for v in value)
            return value is None or isinstance(value, (str, bool, int))
        if not finite(result):
            return False
        if 'events' in result:
            events = result['events']
            kinds = {'explosion', 'illusion', 'angel', 'unrivaled', 'world_split',
                     'pepper', 'purity', 'pan', 'fortress'}
            fields = {'id', 'kind', 'start_tick', 'end_tick', 'rect', 'point',
                      'damage', 'duration'}
            if not isinstance(events, list) or len(events) > 256:
                return False
            ids = set()
            for event in events:
                if (not isinstance(event, dict) or not fields.issubset(event)
                        or not set(event).issubset(fields | {'effect'})):
                    return False
                identity = event['id']
                if (not isinstance(identity, str) or not identity.strip()
                        or len(identity) > 256 or identity in ids):
                    return False
                ids.add(identity)
                if not isinstance(event['kind'], str) or event['kind'] not in kinds:
                    return False
                start, end = event['start_tick'], event['end_tick']
                if type(start) is not int or type(end) is not int or not 0 <= start <= end:
                    return False
                duration, damage = event['duration'], event['damage']
                if duration is not None and (type(duration) is not int or duration < 0):
                    return False
                if damage is not None and (type(damage) not in (int, float) or damage < 0):
                    return False
                for key, count in (('point', 2), ('rect', 4)):
                    coords = event[key]
                    if coords is None:
                        continue
                    if (not isinstance(coords, list) or len(coords) != count
                            or any(type(v) is not int or not 0 <= v <
                                   perception['map']['width' if i % 2 == 0 else 'height']
                                   for i, v in enumerate(coords))):
                        return False
                    if count == 4 and (coords[0] > coords[2] or coords[1] > coords[3]):
                        return False
                if 'effect' in event:
                    effect = event['effect']
                    if not isinstance(effect, dict) or not set(effect).issubset({
                            'movement_multiplier', 'damage_multiplier',
                            'invulnerable', 'blocks_movement'}):
                        return False
                    for name, value in effect.items():
                        if value is None:
                            continue
                        if name in ('invulnerable', 'blocks_movement'):
                            if type(value) is not bool:
                                return False
                        elif type(value) not in (int, float) or value < 0:
                            return False
        for key in ('target', 'position', 'target_position'):
            position = result.get(key)
            if position is None:
                continue
            if (not isinstance(position, (list, tuple)) or len(position) != 2
                    or any(isinstance(v, bool) or not isinstance(v, int) for v in position)):
                return False
            if not (0 <= position[0] < perception['map']['width']
                    and 0 <= position[1] < perception['map']['height']):
                return False
        return True

    def close(self):
        if self.ai is not None:
            self.ai.close()


def main(args=None):
    """Run via python3 -m rmtc_contestant.node or ros2 run."""
    stage_text = os.environ.get('RMTC_STAGE', '1')
    if stage_text not in ('1', '2'):
        raise ValueError('RMTC_STAGE must be 1 or 2')
    stage = int(stage_text)
    team = os.environ.get('TEAM', 'A')
    registration = build_registration(team, os.environ.get('TEAM_NAME', 'RMTC contestant'))
    from .strategy import Strategy
    from .state import WorldState
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from std_msgs.msg import String

    def qos(depth, transient=False):
        return QoSProfile(depth=depth, reliability=ReliabilityPolicy.RELIABLE,
                          durability=(DurabilityPolicy.TRANSIENT_LOCAL if transient
                                      else DurabilityPolicy.VOLATILE))

    class ContestantNode(Node):
        def __init__(self):
            super().__init__('rmtc_contestant_' + team.lower())
            ai = None
            if stage == 2:
                gateway = os.environ.get('AI_GATEWAY', '')
                token = os.environ.get('RMTC_TEAM_TOKEN', '')
                model = os.environ.get('AI_MODEL', '')
                if gateway and token and model:
                    from .ai_client import AiClient
                    ai = AiClient(gateway, token, model, timeout=10.0)
                else:
                    self.get_logger().warning('AI disabled: configure AI_GATEWAY, RMTC_TEAM_TOKEN, AI_MODEL')
            self.controller = Controller(Strategy(stage=stage), WorldState(), stage, ai,
                                         self.get_logger().info,
                                         strategy_factory=lambda: Strategy(stage=stage))
            prefix = '/team_' + team
            self.action_publisher = self.create_publisher(
                String, os.environ.get('RMTC_ACTION_TOPIC', prefix + '/action'), qos(1))
            # Keep publisher alive: TRANSIENT_LOCAL registration must survive discovery.
            self.registration_publisher = self.create_publisher(
                String, os.environ.get('RMTC_REGISTRATION_TOPIC', prefix + '/registration'), qos(1, True))
            self.perception_subscription = self.create_subscription(
                String, os.environ.get('RMTC_PERCEPTION_TOPIC', prefix + '/perception'),
                self.on_perception, qos(1))
            self.event_subscription = self.create_subscription(
                String, os.environ.get('RMTC_EVENTS_TOPIC', '/referee/event_text'),
                lambda msg: self.controller.handle_event(msg.data), qos(128, True))
            self.mission_subscription = self.create_subscription(
                String, os.environ.get('RMTC_MISSION_TOPIC', '/referee/mission'),
                lambda msg: None, qos(1, True))
            self.roster_subscription = self.create_subscription(
                String, os.environ.get('RMTC_ROSTER_TOPIC', '/referee/team_registry'),
                lambda msg: None, qos(1, True))
            self.registration_publisher.publish(String(data=registration))

        def on_perception(self, message):
            action = self.controller.handle_perception(message.data)
            if action is not None:
                self.action_publisher.publish(String(data=action))

    rclpy.init(args=args)
    node = None
    try:
        node = ContestantNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.controller.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
