"""Real local-HTTP tests; no external gateway, credentials or polling sleeps."""
import contextlib
import importlib
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    AiClient = importlib.import_module('rmtc_contestant.ai_client').AiClient
except ModuleNotFoundError:
    AiClient = None


def event(**changes):
    value = dict(id='e1', kind='explosion', start_tick=120, end_tick=125,
                 rect=[1, 2, 4, 5], point=None, damage=20, duration=5)
    value.update(changes)
    return value


def completion(content):
    return json.dumps({'choices': [{'message': {'content': content}}]}).encode()


class MockGateway:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.entered = threading.Event()
        self.release = threading.Event()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                outer.requests.append((self.path, dict(self.headers), json.loads(raw)))
                index = len(outer.requests) - 1
                reply = outer.replies[min(index, len(outer.replies) - 1)]
                outer.entered.set()
                if reply.get('block'):
                    outer.release.wait(3)
                body = reply.get('body', completion(json.dumps({'events': [event()]})))
                try:
                    self.send_response(reply.get('code', 200))
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.01}, daemon=True)
        self.url = 'http://127.0.0.1:%d/v1' % self.server.server_port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class AiClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(AiClient, 'AiClient implementation is missing')

    @contextlib.contextmanager
    def client(self, server, **options):
        client = AiClient(server.url, 'secret-token', 'official-model',
                          timeout=options.pop('timeout', 0.5), **options)
        try:
            yield client
        finally:
            client.close(timeout=2)

    def submit(self, client, session='s1', text='完整公告\n第二段', **kw):
        return client.submit(session, 100, text, 10, 10, (2, 3), **kw)

    def finish(self, client, session='s1'):
        self.assertTrue(client.wait_idle(3), 'worker did not finish')
        return client.poll(session)

    def test_http_contract_and_structured_result(self):
        with MockGateway([{}]) as server, self.client(server) as client:
            self.assertTrue(self.submit(client, mission_text='任务原文'))
            rows = self.finish(client)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['status'], 'ok')
            self.assertEqual(row['session_id'], 's1')
            self.assertEqual(row['tick'], 100)
            self.assertEqual(row['events'], [event()])
            self.assertEqual(row['http_success'], 1)
            self.assertEqual(client.stats['http_success'], 1)
            path, headers, body = server.requests[0]
            self.assertEqual(path, '/v1/chat/completions')
            self.assertEqual(headers['Authorization'], 'Bearer secret-token')
            self.assertEqual(body.get('max_tokens'), 512)
            self.assertFalse(body['stream'])
            self.assertEqual(body['model'], 'official-model')
            context = json.loads(body['messages'][1]['content'])
            self.assertEqual(context['text'], '完整公告\n第二段')
            self.assertEqual(context['mission_text'], '任务原文')
            self.assertIn('absolute', body['messages'][0]['content'])
            self.assertEqual(client.poll('s1'), [])

    def test_submit_nonblocking_bound_and_full_text_dedup(self):
        with MockGateway([{'block': True}]) as server, self.client(server, max_pending=2) as client:
            before = time.monotonic()
            self.assertTrue(self.submit(client))
            self.assertLess(time.monotonic() - before, 0.15)
            self.assertTrue(server.entered.wait(1))
            self.assertFalse(self.submit(client))
            self.assertTrue(self.submit(client, text='完整公告\n另一段'))
            self.assertFalse(self.submit(client, text='第三个'))
            server.release.set()
            self.assertEqual(len(self.finish(client)), 2)
            self.assertEqual(len(server.requests), 2)
            self.assertFalse(self.submit(client))

    def test_session_switch_filters_inflight_and_cached_results(self):
        with MockGateway([{'block': True}, {}]) as server, self.client(server, max_pending=3) as client:
            self.assertTrue(self.submit(client, session='old'))
            self.assertTrue(server.entered.wait(1))
            self.assertTrue(self.submit(client, session='new'))
            server.release.set()
            self.assertTrue(client.wait_idle(3))
            self.assertEqual(client.poll('old'), [])
            self.assertEqual(len(client.poll('new')), 1)
            self.assertTrue(self.submit(client, session='old'))
            self.assertEqual(len(self.finish(client, 'old')), 1)

    def test_http_success_counted_even_for_bad_response(self):
        bad = [b'not json', completion('```json\n{"events":[]}\n```'),
               completion('{"events":[],"action":"move"}'),
               completion('{"events": [NaN]}'),
               completion('{"events": [], "events": []}'),
               completion('{"events":[]} trailing')]
        for body in bad:
            with self.subTest(body=body), MockGateway([{'body': body}]) as server, self.client(server) as client:
                self.assertTrue(self.submit(client))
                row = self.finish(client)[0]
                self.assertEqual(row['status'], 'invalid_response')
                self.assertEqual(row['events'], [])
                self.assertEqual(client.stats['http_success'], 1)
                self.assertEqual(len(server.requests), 1)

    def test_strict_schema_rejects_types_bounds_unknown_fields(self):
        bad_events = [event(start_tick=True), event(start_tick=-1), event(end_tick=119),
                      event(rect=[0, 0, 10, 2]), event(rect=[4, 2, 1, 5]),
                      event(point=[1.5, 2]), event(point=[False, 2]), event(damage=float('inf')),
                      event(damage=-1), event(duration=-1), event(kind='move'),
                      event(id=''), event(action='move'), event(effect={'execute': 'move'})]
        for item in bad_events:
            with self.subTest(item=item), MockGateway([{'body': completion(json.dumps({'events': [item]}))}]) as server, self.client(server) as client:
                self.submit(client)
                self.assertEqual(self.finish(client)[0]['status'], 'invalid_response')

    def test_empty_and_extended_effects(self):
        effect = dict(kind='illusion', rect=[0, 0, 2, 3], point=None,
                      damage=None, duration=5, id='illusion1', start_tick=120,
                      end_tick=125, effect={'movement_multiplier': 0.5,
                      'damage_multiplier': None, 'invulnerable': False,
                      'blocks_movement': True})
        for events in [[], [effect], [event(kind='fortress')]]:
            with self.subTest(events=events), MockGateway([{'body': completion(json.dumps({'events': events}))}]) as server, self.client(server) as client:
                self.submit(client)
                self.assertEqual(self.finish(client)[0]['events'], events)

    def test_auth_and_rate_errors(self):
        for code, body, status, disabled in [
            (401, b'{"error":{"code":"invalid_api_key"}}', 'http_error', True),
            (429, b'{"error":{"code":"quota_exceeded"}}', 'quota_exceeded', True),
            (429, b'{"error":{"code":"rate_limit_exceeded"}}', 'http_error', False)]:
            with self.subTest(code=code, body=body), MockGateway([{'code': code, 'body': body}]) as server, self.client(server, max_retries=0) as client:
                self.submit(client)
                row = self.finish(client)[0]
                self.assertEqual(row['status'], status)
                self.assertEqual(row['http_status'], code)
                self.assertEqual(client.stats['http_success'], 0)
                self.assertEqual(client.disabled, disabled)
                if disabled:
                    self.assertFalse(self.submit(client, text='another'))

    def test_transient_retry_is_bounded(self):
        with MockGateway([{'code': 503, 'body': b'{}'}, {}]) as server, self.client(server, max_retries=1, retry_delay=0) as client:
            self.submit(client)
            row = self.finish(client)[0]
            self.assertEqual(row['status'], 'ok')
            self.assertEqual(row['attempts'], 2)
            self.assertEqual(client.stats['http_success'], 1)
        with MockGateway([{'code': 503, 'body': b'{}'}]) as server, self.client(server, max_retries=1, retry_delay=0) as client:
            self.submit(client)
            self.assertEqual(self.finish(client)[0]['attempts'], 2)
            self.assertEqual(len(server.requests), 2)

    def test_timeout_and_close(self):
        with MockGateway([{'block': True}]) as server, self.client(server, timeout=0.05, max_retries=0) as client:
            self.submit(client)
            row = self.finish(client)[0]
            self.assertEqual(row['status'], 'network_error')
            self.assertEqual(row['events'], [])
            client.close(timeout=1)
            client.close(timeout=1)
            self.assertFalse(self.submit(client, text='closed'))

    def test_mission_only_request_and_invalid_inputs(self):
        with MockGateway([{}]) as server, self.client(server) as client:
            self.assertTrue(self.submit(client, text='', mission_text='任务公告'))
            self.finish(client)
            for values in [(True, 10, 10, (1, 2)), (100, 0, 10, (1, 2)),
                           (100, 10, 10, (10, 1))]:
                with self.assertRaises(ValueError):
                    client.submit('s', values[0], 'x', values[1], values[2], values[3])


if __name__ == '__main__':
    unittest.main()
