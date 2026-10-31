import unittest

from managers.awg_plugin_updater import (
    AwgPluginUpdater,
    KERNEL_MODULE,
    PluginUpdateError,
    USERSPACE,
    parse_tag,
    pick_latest,
    version_tuple,
)

OLD = '3.1.20260812'
NEW = '3.1.20260906'
GO_NEW = '3.1.20260828'


class FakeSSH:
    """Scripted SSH double: records every command, answers by handler."""

    def __init__(self, handler=None):
        self.commands = []
        self.handler = handler or (lambda command: ('', '', 0))

    def run_command(self, command, timeout=60, _retried=False, stdin_input=None):
        self.commands.append(command)
        return self.handler(command)

    def run_sudo_script(self, script, timeout=120):
        self.commands.append(script)
        return self.handler(script)

    def find(self, needle):
        return [command for command in self.commands if needle in command]


def kernel_handler(*, refs='0', headers='yes', tools='yes', clone=(0, ''), build=0,
                   install=0, modprobe=0, verify=NEW):
    state = {'modinfo_calls': 0}

    def handler(command):
        if 'awk' in command and '/proc/modules' in command:
            return (refs, '', 0)
        if 'uname -r' in command and 'HEADERS=' in command:
            lines = ['KVER=6.12.113+deb13-amd64']
            lines.append('HEADERS=%s' % headers)
            lines.append('DKMS=%s' % tools)
            lines.append('GCC=%s' % tools)
            lines.append('MAKE=%s' % tools)
            return ('\n'.join(lines), '', 0)
        if 'modinfo -F version amneziawg' in command:
            state['modinfo_calls'] += 1
            return ((verify if state['modinfo_calls'] > 1 else OLD), '', 0)
        if 'git clone' in command:
            return ('', clone[1], clone[0])
        if 'dkms add' in command:
            return ('', '', 0)
        if 'dkms build' in command:
            return ('', 'make: *** [Makefile:12: modules] Error 2' if build else '', build)
        if 'dkms install' in command:
            return ('', '', install)
        if 'modprobe -r amneziawg' in command:
            return ('', '', 0)
        if 'modprobe amneziawg' in command:
            return ('', '', modprobe)
        if 'depmod' in command:
            return ('', '', 0)
        if 'dkms remove' in command:
            return ('', '', 0)
        if command.startswith('docker ps'):
            return ('', '', 0)
        return ('', '', 0)

    return handler


class TagTests(unittest.TestCase):
    def test_parse_tag(self):
        self.assertEqual(parse_tag('v3.1.20260906'), NEW)
        self.assertEqual(parse_tag('3.1.20260906'), NEW)
        self.assertIsNone(parse_tag('latest'))
        self.assertIsNone(parse_tag('v3.1.2026'))
        self.assertIsNone(parse_tag('v3.1.20260906-rc1'))

    def test_version_tuple(self):
        self.assertEqual(version_tuple(NEW), (3, 1, 20260906))
        self.assertIsNone(version_tuple('nope'))

    def test_pick_latest_orders_by_date(self):
        tags = ['v3.1.20260812', 'v3.1.20260906', 'v3.1.20260828', 'release-notes']
        self.assertEqual(pick_latest(tags), '3.1.20260906')

    def test_pick_latest_ignores_invalid(self):
        self.assertIsNone(pick_latest(['latest', 'v2.0', '']))
        self.assertIsNone(pick_latest([]))


class VersionDetectionTests(unittest.TestCase):
    def test_installed_kernel_parsed(self):
        ssh = FakeSSH(lambda command: (OLD, '', 0))
        self.assertEqual(
            AwgPluginUpdater(ssh).installed_versions()[KERNEL_MODULE], OLD,
        )

    def test_installed_kernel_absent(self):
        ssh = FakeSSH(lambda command: ('', '', 1))
        self.assertIsNone(
            AwgPluginUpdater(ssh).installed_versions()[KERNEL_MODULE],
        )

    def test_userspace_from_image_label(self):
        def handler(command):
            if command.startswith('docker ps -a'):
                return ('amnezia-awg3\tamneziavpn/amneziawg-go:latest', '', 0)
            if 'Config.Labels' in command:
                return (GO_NEW, '', 0)
            return ('', '', 0)

        ssh = FakeSSH(handler)
        self.assertEqual(
            AwgPluginUpdater(ssh).installed_versions()[USERSPACE], GO_NEW,
        )

    def test_userspace_falls_back_to_image_tag(self):
        def handler(command):
            if command.startswith('docker ps -a'):
                return ('amnezia-awg2\tamneziavpn/amneziawg-go:%s' % OLD, '', 0)
            return ('', '', 0)

        ssh = FakeSSH(handler)
        self.assertEqual(
            AwgPluginUpdater(ssh).installed_versions()[USERSPACE], OLD,
        )


class StatusTests(unittest.TestCase):
    def test_update_available(self):
        updater = AwgPluginUpdater(FakeSSH())
        status = updater.status(
            latest={KERNEL_MODULE: NEW, USERSPACE: GO_NEW},
            installed={KERNEL_MODULE: OLD, USERSPACE: OLD},
        )
        self.assertTrue(status['components'][KERNEL_MODULE]['update_available'])
        self.assertTrue(status['components'][USERSPACE]['update_available'])

    def test_up_to_date(self):
        updater = AwgPluginUpdater(FakeSSH())
        status = updater.status(
            latest={KERNEL_MODULE: NEW, USERSPACE: GO_NEW},
            installed={KERNEL_MODULE: NEW, USERSPACE: GO_NEW},
        )
        self.assertFalse(status['components'][KERNEL_MODULE]['update_available'])
        self.assertFalse(status['components'][USERSPACE]['update_available'])

    def test_unknown_installed_is_update(self):
        updater = AwgPluginUpdater(FakeSSH())
        status = updater.status(
            latest={KERNEL_MODULE: NEW, USERSPACE: None},
            installed={KERNEL_MODULE: None, USERSPACE: None},
        )
        self.assertTrue(status['components'][KERNEL_MODULE]['update_available'])
        self.assertFalse(status['components'][USERSPACE]['update_available'])


class PreflightTests(unittest.TestCase):
    def test_missing_headers_blocks(self):
        ssh = FakeSSH(kernel_handler(headers='no'))
        check = AwgPluginUpdater(ssh).preflight(KERNEL_MODULE)
        self.assertFalse(check['ready'])
        self.assertTrue(any('headers' in item for item in check['blockers']))

    def test_missing_tools_blocks(self):
        ssh = FakeSSH(kernel_handler(tools='no'))
        check = AwgPluginUpdater(ssh).preflight(KERNEL_MODULE)
        self.assertFalse(check['ready'])
        self.assertEqual(len(check['blockers']), 3)

    def test_ready_when_dependencies_present(self):
        ssh = FakeSSH(kernel_handler())
        check = AwgPluginUpdater(ssh).preflight(KERNEL_MODULE)
        self.assertTrue(check['ready'])
        self.assertFalse(check['requires_interruption'])


class KernelUpdateTests(unittest.TestCase):
    def test_success_order_and_old_kept(self):
        ssh = FakeSSH(kernel_handler())
        result = AwgPluginUpdater(ssh).update(KERNEL_MODULE, NEW)
        self.assertEqual(result['state'], 'updated')
        self.assertEqual(result['installed'], NEW)
        self.assertEqual(result['previous'], OLD)

        clone = next(i for i, c in enumerate(ssh.commands) if 'git clone' in c)
        build = next(i for i, c in enumerate(ssh.commands) if 'dkms build' in c)
        install = next(i for i, c in enumerate(ssh.commands) if 'dkms install' in c)
        unload = next(i for i, c in enumerate(ssh.commands) if 'modprobe -r amneziawg' in c)
        self.assertLess(clone, build)
        self.assertLess(build, install)
        self.assertLess(install, unload)
        # The working DKMS version must never be removed on the happy path.
        self.assertFalse([c for c in ssh.commands if 'dkms remove amneziawg/%s' % OLD in c])

    def test_build_failure_keeps_old_module(self):
        ssh = FakeSSH(kernel_handler(build=1))
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(ssh).update(KERNEL_MODULE, NEW)
        self.assertEqual(ctx.exception.code, 'update_failed')
        self.assertTrue(ssh.find('dkms remove amneziawg/%s --all' % NEW))
        self.assertFalse(ssh.find('modprobe -r amneziawg'))
        self.assertFalse(ssh.find('dkms remove amneziawg/%s' % OLD))

    def test_modprobe_failure_rolls_back(self):
        ssh = FakeSSH(kernel_handler(modprobe=1, verify=OLD))
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(ssh).update(KERNEL_MODULE, NEW)
        self.assertEqual(ctx.exception.code, 'update_failed')
        self.assertTrue(ssh.find('dkms remove amneziawg/%s --all' % NEW))
        self.assertTrue(ssh.find('depmod'))
        self.assertFalse(ssh.find('dkms remove amneziawg/%s' % OLD))

    def test_requires_confirmation_changes_nothing(self):
        ssh = FakeSSH(kernel_handler(refs='2'))
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(ssh).update(KERNEL_MODULE, NEW, allow_interrupt=False)
        self.assertEqual(ctx.exception.code, 'requires_confirmation')
        self.assertFalse(ssh.find('git clone'))
        self.assertFalse(ssh.find('dkms add'))
        self.assertFalse(ssh.find('dkms build'))
        self.assertFalse(ssh.find('modprobe -r'))
        self.assertFalse(ssh.find('modprobe amneziawg'))

    def test_rejects_unsupported_target(self):
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(FakeSSH()).update(KERNEL_MODULE, 'latest')
        self.assertEqual(ctx.exception.code, 'unsupported')


class UserspaceUpdateTests(unittest.TestCase):
    def _handler(self, pull_code=0, image_version=GO_NEW):
        def handler(command):
            if command.startswith('docker ps -a'):
                return ('amnezia-awg3\tamneziavpn/amneziawg-go:latest', '', 0)
            if 'Config.Labels' in command:
                return (image_version, '', 0)
            if command.startswith('docker pull'):
                return ('', 'pull access denied' if pull_code else '', pull_code)
            return ('', '', 0)

        return handler

    def test_pull_failure_touches_nothing(self):
        ssh = FakeSSH(self._handler(pull_code=1))
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(ssh).update(USERSPACE, GO_NEW)
        self.assertEqual(ctx.exception.code, 'update_failed')
        self.assertFalse(ssh.find('docker stop'))
        self.assertFalse(ssh.find('docker rename'))

    def test_registry_older_than_target_stops_before_restart(self):
        ssh = FakeSSH(self._handler(image_version=OLD))
        with self.assertRaises(PluginUpdateError) as ctx:
            AwgPluginUpdater(ssh).update(USERSPACE, GO_NEW)
        self.assertEqual(ctx.exception.code, 'unsupported')
        self.assertFalse(ssh.find('docker stop'))
        self.assertFalse(ssh.find('docker rename'))

    def test_success_reports_manual_step_and_keeps_containers(self):
        ssh = FakeSSH(self._handler(image_version=GO_NEW))
        result = AwgPluginUpdater(ssh).update(USERSPACE, GO_NEW)
        self.assertEqual(result['state'], 'manual_step_required')
        self.assertFalse(ssh.find('docker stop'))
        self.assertFalse(ssh.find('docker rename'))


class ChangelogTests(unittest.TestCase):
    def test_unknown_installed_version_returns_empty(self):
        ssh = FakeSSH(lambda command: ('', '', 1))
        self.assertEqual(AwgPluginUpdater(ssh).changelog(KERNEL_MODULE, NEW), [])


if __name__ == '__main__':
    unittest.main()
