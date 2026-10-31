"""Progress reporting for the AmneziaWG plugin updater.

The UI has to answer two questions while an update runs: "which step is it
on?" and "is it still moving?"  A DKMS build can take minutes, so the bar must
keep creeping inside the current stage instead of looking frozen.

These tests are deterministic: no SSH, no network, no real update.  The only
sleep is a short poll while the background task started by the endpoint
finishes with an in-memory fake updater.
"""

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as panel
from managers.awg_plugin_updater import (
    KERNEL_MODULE,
    STAGE_STEPS,
    TOTAL_STEPS,
    USERSPACE,
    stage_step,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates' / 'server.html'
TRANSLATIONS = ROOT / 'translations'


class ProgressUpdater:
    """Fake updater that only plays log lines through the real callback."""

    def __init__(self, stages):
        self.stages = stages
        # (step, total, percent) observed right after each log() call.
        self.snapshots = []

    def latest_versions(self):
        return {KERNEL_MODULE: '3.1.20260906', USERSPACE: '3.1.20260828'}

    def update(self, component, target, allow_interrupt=False, log=None, should_cancel=None):
        for stage, message in self.stages:
            log(stage, message)
            running = [
                op for op in panel._awg_plugin_ops.values()
                if op.get('state') == 'running' and op.get('component') == component
            ]
            if running:
                op = running[-1]
                self.snapshots.append((op['step'], op['total'], op['percent']))
        return {
            'component': component,
            'previous': '3.1.20260812',
            'installed': target,
            'state': 'updated',
            'rolled_back': False,
        }


class AwgPluginProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._data_file = panel.DATA_FILE
        panel.DATA_FILE = str(Path(self.tmp.name) / 'data.json')
        self.addCleanup(setattr, panel, 'DATA_FILE', self._data_file)

        panel._awg_plugin_ops.clear()
        panel._awg_plugin_active.clear()
        panel._awg_plugin_loaded['done'] = False
        self.addCleanup(panel._awg_plugin_ops.clear)
        self.addCleanup(panel._awg_plugin_active.clear)

        seed = {
            'servers': [{
                'name': 's', 'host': '127.0.0.1', 'ssh_port': 1,
                'username': 'root', 'password': 'x', 'private_key': '',
                'server_info': {}, 'uid': 'u0', 'protocols': {},
            }],
            'users': [], 'user_connections': [],
        }
        Path(panel.DATA_FILE).write_text(json.dumps(seed), encoding='utf-8')

        self.updater = ProgressUpdater([
            ('preflight', 'kernel 6.1.0, blockers: none'),
            ('build', 'dkms build in progress'),
        ])
        patcher = patch.object(panel, '_awg_plugin_updater', lambda server_id: self.updater)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = TestClient(panel.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        login = self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin', 'captcha': None},
        )
        self.assertEqual(login.status_code, 200, login.text)

    # ------------------------------------------------------------------ helpers

    def _start_update(self, component=KERNEL_MODULE):
        response = self.client.post(
            '/api/servers/0/awg-plugin/update',
            json={'component': component},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['operation_id']

    def _wait_until_finished(self, op_id, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            op = panel._awg_plugin_ops.get(op_id)
            if op and op.get('state') != 'running':
                return op
            time.sleep(0.01)
        self.fail('operation %s did not finish' % op_id)

    # --------------------------------------------------------------- stage map

    def test_stage_map_is_ordered_and_complete(self):
        self.assertEqual(stage_step(KERNEL_MODULE, 'build'), (6, 10))
        self.assertEqual(stage_step(KERNEL_MODULE, 'preflight'), (2, 10))
        self.assertEqual(stage_step(USERSPACE, 'build'), (4, 10))
        self.assertIsNone(stage_step(KERNEL_MODULE, 'not-a-stage'))
        self.assertIsNone(stage_step('not-a-component', 'build'))
        self.assertEqual(TOTAL_STEPS, 10)

        # The two terminal aliases (cleanup/done) both mean "finished" and
        # intentionally share step 10, so strict increase is required for
        # every other adjacent pair in the documented order.
        documented = {
            KERNEL_MODULE: [
                'start', 'preflight', 'backup', 'download', 'dkms-add',
                'build', 'install', 'verify', 'activate', 'done', 'cleanup',
            ],
            USERSPACE: [
                'start', 'prepare', 'backup', 'build', 'switch', 'network',
                'restore', 'verify', 'finalize', 'cleanup', 'done',
            ],
        }
        terminal_aliases = {'done', 'cleanup'}
        for component, order in documented.items():
            with self.subTest(component=component):
                mapping = STAGE_STEPS[component]
                self.assertEqual(set(mapping), set(order))
                steps = [mapping[name] for name in order]
                self.assertTrue(
                    all(1 <= step <= TOTAL_STEPS for step in steps),
                    '%s has a step outside 1..%d: %r' % (component, TOTAL_STEPS, steps),
                )
                for name_before, name_after, previous, current in zip(
                    order, order[1:], steps, steps[1:]
                ):
                    self.assertGreaterEqual(current, previous)
                    if current == previous:
                        self.assertIn(name_before, terminal_aliases)
                        self.assertIn(name_after, terminal_aliases)
                self.assertEqual(sorted(set(steps)), list(range(1, TOTAL_STEPS + 1)))

    # -------------------------------------------------------------------- API

    def test_api_exposes_consistent_progress(self):
        op_id = self._start_update()
        self._wait_until_finished(op_id)

        response = self.client.get('/api/servers/0/awg-plugin/update/%s' % op_id)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        for key in ('step', 'total', 'percent'):
            self.assertIn(key, body)
        self.assertEqual(body['total'], TOTAL_STEPS)
        self.assertEqual(body['percent'], int(round(body['step'] * 100.0 / body['total'])))
        # The worker logged 'done', so the final operation is at 10/10.
        self.assertEqual(body['step'], TOTAL_STEPS)
        self.assertEqual(body['percent'], 100)

        # While the fake was still inside update(), the build stage had
        # already moved the bar to 60% - the long-action case the UI cares
        # about, not just the final value.
        self.assertIn((6, 10, 60), self.updater.snapshots)
        self.assertIn((2, 10, 20), self.updater.snapshots)

    def test_progress_never_goes_backwards(self):
        """Drive the real worker with log stages arriving out of order."""
        out_of_order = ProgressUpdater([
            ('preflight', 'stale line after build'),
            ('done', 'finished'),
            ('preflight', 'even later stale line'),
        ])
        op_id = 'op-monotonic'
        panel._awg_plugin_ops[op_id] = {
            'id': op_id, 'server_id': 0, 'component': KERNEL_MODULE,
            'target': '3.1.20260906', 'state': 'running', 'lines': [],
            'result': None, 'error': None, 'cancel_requested': False,
            'step': 6, 'total': TOTAL_STEPS, 'percent': 60,
            'started_at': 't',
        }
        with patch.object(panel, '_awg_plugin_updater', lambda server_id: out_of_order):
            asyncio.run(panel._run_awg_plugin_update(
                op_id, 0, KERNEL_MODULE, '3.1.20260906', False,
            ))

        op = panel._awg_plugin_ops[op_id]
        self.assertEqual(op['state'], 'success')
        self.assertEqual(out_of_order.snapshots, [(6, 10, 60), (10, 10, 100), (10, 10, 100)])
        self.assertEqual((op['step'], op['total'], op['percent']), (10, 10, 100))

    # ------------------------------------------------------------ persistence

    def test_progress_is_persisted_in_the_journal(self):
        op_id = self._start_update()
        self._wait_until_finished(op_id)

        store = Path(panel._awg_plugin_store_path())
        self.assertTrue(store.exists())
        stored = json.loads(store.read_text(encoding='utf-8'))
        entry = next(item for item in stored if item.get('id') == op_id)
        for key in ('step', 'total', 'percent'):
            self.assertIn(key, entry)
        self.assertEqual(entry['total'], TOTAL_STEPS)
        self.assertEqual((entry['step'], entry['percent']), (10, 100))

    # --------------------------------------------------------------- template

    def test_template_renders_progress_bar(self):
        html = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('awg-progress-track', html)
        self.assertIn('setAttribute(\'role\', \'progressbar\')', html)
        self.assertIn('awg-progress-fill', html)
        self.assertIn('awgProgressShimmer', html)
        self.assertIn('setAwgProgress(component, data.step, data.total, data.percent', html)
        self.assertIn('labelsStep(', html)
        self.assertIn("replace('{step}'", html)
        self.assertIn("replace('{total}'", html)

    def test_translations_have_step_placeholders(self):
        files = sorted(TRANSLATIONS.glob('*.json'))
        self.assertEqual({path.stem for path in files}, {'en', 'fr', 'ru', 'zh', 'fa'})
        for path in files:
            with self.subTest(locale=path.stem):
                payload = json.loads(path.read_text(encoding='utf-8'))
                self.assertIn('awg_plugin_step', payload)
                value = payload['awg_plugin_step']
                self.assertIn('{step}', value)
                self.assertIn('{total}', value)

    def test_ticker_creeps_and_respects_reduced_motion(self):
        html = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('setInterval(', html)
        self.assertIn('op.cap = Math.min(99, op.percent + 9)', html)
        self.assertIn('current.display = Math.min(current.cap, (current.display || 0) + 1)', html)
        self.assertIn('@media (prefers-reduced-motion: reduce)', html)
        reduced = html[html.index('@media (prefers-reduced-motion: reduce)'):]
        self.assertIn('.awg-progress-fill::after { animation: none; }', reduced)


if __name__ == '__main__':
    unittest.main()
