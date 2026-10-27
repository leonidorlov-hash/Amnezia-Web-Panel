"""Browser regressions for the add-server wizard's real inline handlers.

The page is rendered with Jinja, its production scripts and stylesheet are
removed, and only the wizard script is re-attached to a synthetic DOM/backend.
That keeps the test offline while still executing the handler code that ships
in templates/server_new.html.  Selectors and error codes below come from the
current template and app.py; no production data or SSH is touched.
"""
import json
import os
import re
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
INSPECT = '/api/ssh-trust/onboarding/inspect'
CONFIRM = '/api/ssh-trust/onboarding/confirm'
ADD = '/api/servers/add'


HELPERS_JS = r"""
window._ = function (key) { return window.I18N[key] || key; };

const INSPECT = '/api/ssh-trust/onboarding/inspect';
const CONFIRM = '/api/ssh-trust/onboarding/confirm';
const ADD = '/api/servers/add';
const calls = [];
let inspectResponses = [{
    status: 'unknown',
    host: 'node.example.test',
    port: 2222,
    algorithm: 'ssh-ed25519',
    fingerprint: 'SHA256:synthetic',
    old_fingerprints: [],
    token: 'synthetic-token'
}];
let addResult = {status: 'success', server_id: 7, server_info: {}};
let addErrorCode = null;
let addErrorOnce = null;
let delayedInspect = false;
let pendingInspect = null;

async function apiCall(url, method = 'GET', body = null) {
    calls.push({url: url, method: method,
                body: body ? JSON.parse(JSON.stringify(body)) : null});
    if (url === INSPECT) {
        if (delayedInspect) {
            delayedInspect = false;
            await new Promise(resolve => {
                pendingInspect = {
                    body: body,
                    resolve: () => {
                        pendingInspect = null;
                        resolve();
                    }
                };
            });
        }
        const response = inspectResponses.length > 1
            ? inspectResponses.shift() : inspectResponses[0];
        return JSON.parse(JSON.stringify(response));
    }
    if (url === CONFIRM) {
        return {status: 'success', ssh_authenticated: false};
    }
    if (url === ADD) {
        if (addErrorOnce) {
            const code = addErrorOnce;
            addErrorOnce = null;
            const error = new Error(code);
            error.payload = {error: code, error_code: code};
            throw error;
        }
        if (addErrorCode) {
            const error = new Error(addErrorCode);
            error.payload = {error: addErrorCode, error_code: addErrorCode};
            throw error;
        }
        return JSON.parse(JSON.stringify(addResult));
    }
    throw new Error('unexpected API call: ' + url);
}
"""


class ServerWizardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest('Playwright is not installed')

        cls._playwright = sync_playwright().start()
        launch_options = {'headless': True}
        if os.environ.get('PANEL_BROWSER_EXECUTABLE'):
            launch_options['executable_path'] = os.environ['PANEL_BROWSER_EXECUTABLE']
        try:
            cls.browser = cls._playwright.chromium.launch(**launch_options)
        except Exception as exc:
            cls._playwright.stop()
            raise unittest.SkipTest(f'Chromium is not installed: {type(exc).__name__}')

        cls.strings = json.loads((ROOT / 'translations' / 'en.json').read_text(encoding='utf-8'))
        env = Environment(loader=FileSystemLoader(str(ROOT / 'templates')), autoescape=True)
        cls.html = env.get_template('server_new.html').render(
            request=None,
            lang='en',
            static_v='synthetic',
            site_settings={'title': 'Synthetic panel', 'subtitle': '', 'logo': ''},
            current_user={'username': 'admin', 'role': 'admin'},
            _=lambda key: cls.strings.get(key, key),
            translations_json=json.dumps(cls.strings),
            login_translations_json='{}',
            all_translations_json='{}',
            captcha_settings={},
            telegram_settings={},
            bot_running=False,
        )
        scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', cls.html, re.S)
        cls.wizard_js = next((script for script in scripts if 'const wizardState' in script), None)
        if not cls.wizard_js:
            raise AssertionError('the wizard script was not found in templates/server_new.html')

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, 'browser', None)
        if browser is not None:
            browser.close()
        playwright = getattr(cls, '_playwright', None)
        if playwright is not None:
            playwright.stop()

    def new_page(self, viewport=None):
        context = self.browser.new_context(viewport=viewport or {'width': 1280, 'height': 900})
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        self.addCleanup(self.assertEqual, errors, [], 'uncaught JavaScript errors')

        # Remove production scripts and external assets; CSS is added from disk
        # below so mobile layout checks exercise the shipped rules.
        html = re.sub(r'<script\b.*?</script>', '', self.html, flags=re.S)
        html = re.sub(r'<link[^>]+>', '', html)
        page.set_content(html)
        page.add_style_tag(path=str(ROOT / 'static' / 'css' / 'style.css'))
        page.add_script_tag(content='window.I18N = ' + json.dumps(self.strings) + ';\n' + HELPERS_JS)
        page.add_script_tag(content=self.wizard_js)
        return page

    def calls(self, page, path):
        return page.evaluate('(path) => calls.filter(call => call.url === path)', path)

    def configure_inspect(self, page, *responses):
        page.evaluate('(responses) => { inspectResponses = responses; }', list(responses))

    def configure_add_error(self, page, code):
        page.evaluate('(code) => { addErrorCode = code; }', code)

    def configure_add_error_once(self, page, code):
        page.evaluate('(code) => { addErrorOnce = code; }', code)

    def set_address_field(self, page, selector, value):
        """Change a possibly hidden address field and run the real input handler."""
        page.evaluate(
            '([selector, value]) => {'
            '  const input = document.querySelector(selector);'
            '  input.value = value;'
            "  input.dispatchEvent(new Event('input', {bubbles: true}));"
            '}',
            [selector, value])

    def drive_to_trust(self, page, host='node.example.test', port='2222'):
        page.fill('#wizardHost', host)
        page.fill('#wizardPort', port)
        page.click('#wizardAddressNext')
        page.wait_for_function(
            "wizardState.step === 2 && !document.getElementById('wizardTrustBody').hidden")

    def drive_to_review(self, page, password='synthetic-password'):
        page.fill('#wizardUser', 'root')
        page.fill('#wizardPassword', password)
        page.evaluate('wizardReview()')
        page.wait_for_function('wizardState.step === 4')

    def test_unknown_inspect_and_confirmation_never_send_credentials(self):
        page = self.new_page()
        self.configure_inspect(page, {
            'status': 'unknown', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:unknown',
            'old_fingerprints': [], 'token': 'synthetic-token',
        })
        self.drive_to_trust(page)

        inspect = self.calls(page, INSPECT)
        self.assertEqual(len(inspect), 1)
        self.assertEqual(inspect[0]['body'], {'host': 'node.example.test', 'ssh_port': 2222})
        for field in ('username', 'password', 'private_key'):
            self.assertNotIn(field, inspect[0]['body'])
        self.assertTrue(page.locator('#wizardTrustUnknownCheck').is_visible())
        self.assertTrue(page.locator('#wizardTrustChangedChecklist').is_hidden())
        self.assertTrue(page.locator('#wizardOldFingerprintWrap').is_hidden())

        self.assertTrue(page.locator('#wizardTrustContinue').is_disabled())
        page.evaluate('wizardTrustContinue()')
        page.wait_for_timeout(50)
        self.assertEqual(self.calls(page, CONFIRM), [])

        page.check('#wizardTrustVerified')
        self.assertFalse(page.locator('#wizardTrustContinue').is_disabled())
        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')

        confirm = self.calls(page, CONFIRM)
        self.assertEqual(len(confirm), 1)
        self.assertEqual(confirm[0]['body'], {
            'host': 'node.example.test', 'ssh_port': 2222,
            'token': 'synthetic-token', 'confirmed': True,
        })
        for field in ('username', 'password', 'private_key'):
            self.assertNotIn(field, confirm[0]['body'])

    def test_trusted_key_moves_to_credentials_without_confirmation(self):
        page = self.new_page()
        self.configure_inspect(page, {
            'status': 'trusted', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:trusted',
            'old_fingerprints': [],
        })
        self.drive_to_trust(page)

        self.assertEqual(page.locator('#wizardTrustBadge').text_content(),
                         page.evaluate("_('ssh_trust_trusted')"))
        self.assertTrue(page.locator('#wizardTrustConfirmWrap').is_hidden())
        self.assertFalse(page.locator('#wizardTrustContinue').is_disabled())
        self.assertEqual(page.locator('#wizardTrustContinue').text_content().strip(),
                         page.evaluate("_('wizard_continue')"))

        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')
        self.assertEqual(self.calls(page, CONFIRM), [])

    def test_changed_key_needs_both_checkboxes_before_confirm(self):
        page = self.new_page()
        self.configure_inspect(page, {
            'status': 'changed', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:new',
            'old_fingerprints': [{'algorithm': 'ssh-ed25519',
                                  'fingerprint': 'SHA256:old'}],
            'token': 'changed-token',
        })
        self.drive_to_trust(page)

        self.assertTrue(page.locator('#wizardTrustChangedChecklist').is_visible())
        self.assertTrue(page.locator('#wizardTrustUnknownCheck').is_hidden())
        self.assertTrue(page.locator('#wizardOldFingerprintWrap').is_visible())
        self.assertIn('SHA256:new', page.locator('#wizardTrustFingerprint').text_content())
        self.assertIn('SHA256:old', page.locator('#wizardOldFingerprints').text_content())
        self.assertTrue(page.locator('#wizardTrustContinue').is_disabled())

        page.evaluate('wizardTrustContinue()')
        page.wait_for_timeout(50)
        self.assertEqual(self.calls(page, CONFIRM), [])

        page.check('#wizardTrustChangedVerified')
        self.assertTrue(page.locator('#wizardTrustContinue').is_disabled())
        page.evaluate('wizardTrustContinue()')
        page.wait_for_timeout(50)
        self.assertEqual(self.calls(page, CONFIRM), [])

        page.check('#wizardTrustChangedReplace')
        self.assertFalse(page.locator('#wizardTrustContinue').is_disabled())
        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')

        confirm = self.calls(page, CONFIRM)
        self.assertEqual(len(confirm), 1)
        self.assertEqual(confirm[0]['body']['token'], 'changed-token')
        self.assertTrue(confirm[0]['body']['confirmed'])
        for field in ('username', 'password', 'private_key'):
            self.assertNotIn(field, confirm[0]['body'])

    def test_credentials_only_go_to_add_and_success_links_to_the_server(self):
        page = self.new_page()
        self.configure_inspect(page, {
            'status': 'trusted', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:trusted',
            'old_fingerprints': [],
        })
        self.drive_to_trust(page)
        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')

        self.drive_to_review(page)
        self.assertEqual(self.calls(page, ADD), [])

        page.click('#wizardConnectBtn')
        page.wait_for_function("document.getElementById('wizardSuccess').hidden === false")

        add = self.calls(page, ADD)
        self.assertEqual(len(add), 1)
        self.assertEqual(add[0]['body']['host'], 'node.example.test')
        self.assertEqual(add[0]['body']['ssh_port'], 2222)
        self.assertEqual(add[0]['body']['username'], 'root')
        self.assertEqual(add[0]['body']['password'], 'synthetic-password')
        self.assertNotIn('private_key', add[0]['body'])

        # Credentials are not copied into either trust endpoint.
        for path in (INSPECT, CONFIRM):
            for call in self.calls(page, path):
                for field in ('username', 'password', 'private_key'):
                    self.assertNotIn(field, call['body'])

        self.assertTrue(page.locator('#wizardConnectPanel').is_hidden())
        self.assertTrue(page.locator('#wizardSuccess').is_visible())
        self.assertEqual(page.get_attribute('#wizardOpenServer', 'href'), '/server/7')
        self.assertEqual(page.input_value('#wizardPassword'), '')

    def test_add_error_codes_route_the_ui_to_the_matching_step(self):
        cases = {
            'authentication_failed': ('#wizardCredentialsError', 'wizard_error_auth', 3),
            'network_error': ('#wizardConnectError', 'wizard_error_network', 4),
        }
        for code, (selector, message_key, step) in cases.items():
            with self.subTest(error_code=code):
                page = self.new_page()
                self.configure_inspect(page, {
                    'status': 'trusted', 'host': 'node.example.test', 'port': 2222,
                    'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:trusted',
                    'old_fingerprints': [],
                })
                self.drive_to_trust(page)
                page.click('#wizardTrustContinue')
                page.wait_for_function('wizardState.step === 3')
                self.drive_to_review(page)
                self.configure_add_error(page, code)

                page.click('#wizardConnectBtn')
                page.wait_for_function(
                    '(args) => wizardState.step === args[0] && '
                    '!document.querySelector(args[1]).hidden',
                    arg=[step, selector])
                self.wait_for_error_text(page, selector, message_key)

                self.assertEqual(page.evaluate("_('%s')" % message_key),
                                 page.locator(selector).text_content())
                self.assertEqual(len(self.calls(page, INSPECT)), 1)
                self.assertEqual(self.calls(page, CONFIRM), [])
                self.assertTrue(page.evaluate('wizardState.trustSatisfied'))

        for code, status in (('host_key_unknown', 'unknown'),
                             ('host_key_changed', 'changed')):
            with self.subTest(error_code=code):
                page = self.new_page()
                self.configure_inspect(
                    page,
                    {'status': 'trusted', 'host': 'node.example.test', 'port': 2222,
                     'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:trusted',
                     'old_fingerprints': []},
                    {'status': status, 'host': 'node.example.test', 'port': 2222,
                     'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:current',
                     'old_fingerprints': [], 'token': 'replacement-token'},
                )
                self.drive_to_trust(page)
                page.click('#wizardTrustContinue')
                page.wait_for_function('wizardState.step === 3')
                self.drive_to_review(page)
                self.configure_add_error(page, code)

                page.click('#wizardConnectBtn')
                page.wait_for_function(
                    '(status) => wizardState.step === 2 && '
                    'wizardState.candidate && wizardState.candidate.status === status && '
                    "!document.getElementById('wizardTrustBody').hidden && "
                    '!wizardState.busy', arg=status)
                message_key = ('wizard_error_host_key_unknown' if code == 'host_key_unknown'
                               else 'wizard_error_host_key_changed')
                self.wait_for_error_text(page, '#wizardInspectError', message_key)

                self.assertEqual(len(self.calls(page, INSPECT)), 2)
                self.assertEqual(self.calls(page, CONFIRM), [])
                self.assertFalse(page.evaluate('wizardState.trustSatisfied'))

    def test_host_key_rejection_recovers_and_second_add_succeeds(self):
        page = self.new_page()
        self.configure_inspect(
            page,
            {'status': 'trusted', 'host': 'node.example.test', 'port': 2222,
             'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:trusted',
             'old_fingerprints': []},
            {'status': 'changed', 'host': 'node.example.test', 'port': 2222,
             'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:changed',
             'old_fingerprints': [{'algorithm': 'ssh-ed25519',
                                   'fingerprint': 'SHA256:trusted'}],
             'token': 'replacement-token'},
        )
        self.drive_to_trust(page)
        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')
        self.drive_to_review(page)

        # First add fails after authentication with a rotated host key. The
        # wizard must not leave its connect button busy in the hidden step 4.
        self.configure_add_error_once(page, 'host_key_changed')
        page.click('#wizardConnectBtn')
        page.wait_for_function(
            '(status) => wizardState.step === 2 && '
            'wizardState.candidate && wizardState.candidate.status === status && '
            "!document.getElementById('wizardTrustBody').hidden && "
            '!wizardState.busy',
            arg='changed')
        self.assertEqual(len(self.calls(page, INSPECT)), 2)
        self.assertTrue(page.locator('#wizardTrustChangedChecklist').is_visible())
        self.assertTrue(page.locator('#wizardTrustContinue').is_disabled())

        # Both explicit confirmations are required for the changed key.
        page.evaluate('wizardTrustContinue()')
        page.wait_for_timeout(50)
        self.assertEqual(self.calls(page, CONFIRM), [])
        page.check('#wizardTrustChangedVerified')
        self.assertTrue(page.locator('#wizardTrustContinue').is_disabled())
        page.evaluate('wizardTrustContinue()')
        page.wait_for_timeout(50)
        self.assertEqual(self.calls(page, CONFIRM), [])
        page.check('#wizardTrustChangedReplace')
        self.assertFalse(page.locator('#wizardTrustContinue').is_disabled())
        page.click('#wizardTrustContinue')
        page.wait_for_function('wizardState.step === 3')
        self.assertEqual(len(self.calls(page, CONFIRM)), 1)

        # Invalidation deliberately clears credentials; enter them again.
        self.assertEqual(page.input_value('#wizardUser'), '')
        self.assertEqual(page.input_value('#wizardPassword'), '')
        self.drive_to_review(page)
        self.assertFalse(page.locator('#wizardConnectBtn').is_disabled())
        self.assertEqual(page.locator('#wizardConnectBtn').text_content().strip(),
                         page.evaluate("_('wizard_connect_button')"))

        page.click('#wizardConnectBtn')
        page.wait_for_function("document.getElementById('wizardSuccess').hidden === false")
        self.assertEqual(len(self.calls(page, ADD)), 2)
        self.assertEqual(page.get_attribute('#wizardOpenServer', 'href'), '/server/7')

    def wait_for_error_text(self, page, selector, message_key):
        page.wait_for_function(
            '(args) => { const el = document.querySelector(args[0]); '
            'return el && !el.hidden && el.textContent === window._(args[1]); }',
            arg=[selector, message_key])

    def test_endpoint_change_invalidates_candidate_and_ignores_stale_inspect(self):
        for field, value in (('#wizardHost', 'other.example.test'),
                             ('#wizardPort', '2200')):
            with self.subTest(field=field):
                page = self.new_page()
                self.configure_inspect(page, {
                    'status': 'unknown', 'host': 'node.example.test', 'port': 2222,
                    'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:unknown',
                    'old_fingerprints': [], 'token': 'synthetic-token',
                })
                self.drive_to_trust(page)
                # The address inputs are inside step 1, which is hidden while
                # step 2 is active. Push the value through the real handler.
                self.set_address_field(page, field, value)
                page.wait_for_function('wizardState.step === 1')
                self.assertIsNone(page.evaluate('wizardState.candidate'))
                self.assertFalse(page.evaluate('wizardState.trustSatisfied'))
                self.assertTrue(page.locator('#wizardTrustBody').is_hidden())
                self.assertFalse(page.evaluate(
                    "document.getElementById('wizardTrustConfirmWrap').hidden"))
                self.assertFalse(page.is_checked('#wizardTrustVerified'))

        # A response that was already in flight must not populate the UI after
        # the endpoint changes.
        page = self.new_page()
        self.configure_inspect(page, {
            'status': 'unknown', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:stale',
            'old_fingerprints': [], 'token': 'stale-token',
        })
        page.evaluate('delayedInspect = true')
        page.fill('#wizardHost', 'node.example.test')
        page.fill('#wizardPort', '2222')
        page.click('#wizardAddressNext')
        page.wait_for_function('pendingInspect !== null')
        self.set_address_field(page, '#wizardPort', '2200')
        page.evaluate('pendingInspect.resolve()')
        page.wait_for_function('pendingInspect === null')
        page.wait_for_timeout(100)

        self.assertEqual(page.evaluate('wizardState.step'), 1)
        self.assertIsNone(page.evaluate('wizardState.candidate'))
        self.assertTrue(page.locator('#wizardTrustBody').is_hidden())
        self.assertEqual(page.locator('#wizardTrustEndpoint').text_content(), '')

    def test_mobile_progress_and_no_horizontal_overflow(self):
        page = self.new_page(viewport={'width': 375, 'height': 812})
        self.assertEqual(page.evaluate('window.innerWidth'), 375)
        self.assertTrue(page.locator('#wizardProgressMobile').is_visible())
        self.assertEqual(
            page.evaluate("getComputedStyle(document.querySelector('.wizard-progress')).display"),
            'none')
        self.assertEqual(
            page.locator('#wizardProgressMobile').text_content(),
            page.evaluate("_('wizard_progress_mobile').replace('{current}', '1').replace('{total}', '4')"))
        self.assert_no_horizontal_overflow(page)

        self.configure_inspect(page, {
            'status': 'unknown', 'host': 'node.example.test', 'port': 2222,
            'algorithm': 'ssh-ed25519', 'fingerprint': 'SHA256:unknown',
            'old_fingerprints': [], 'token': 'synthetic-token',
        })
        self.drive_to_trust(page)
        self.assertEqual(
            page.locator('#wizardProgressMobile').text_content(),
            page.evaluate("_('wizard_progress_mobile').replace('{current}', '2').replace('{total}', '4')"))
        self.assert_no_horizontal_overflow(page)

    def assert_no_horizontal_overflow(self, page):
        widths = page.evaluate("""() => ({
            view: window.innerWidth,
            document: document.documentElement.scrollWidth,
            body: document.body.scrollWidth
        })""")
        self.assertLessEqual(max(widths['document'], widths['body']), widths['view'] + 1,
                             f'horizontal overflow: {widths}')


if __name__ == '__main__':
    unittest.main()
