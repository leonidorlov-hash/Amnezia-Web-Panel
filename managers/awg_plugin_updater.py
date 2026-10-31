"""Safe updates of the AmneziaWG components used by a managed server.

Two components are handled independently:

* ``kernel_module`` – the DKMS-built ``amneziawg`` kernel module.
* ``userspace``     – the ``amneziavpn/amneziawg-go`` container image.

The single non-negotiable rule of this module is that a failed update must
leave the server on the version it was running before the operation.  That is
why nothing here removes an installed/working version before the replacement
has been built and verified, and why every failure path ends either with the
previous state untouched or with an explicit rollback.

The module never touches ``data.json`` and never decides authorization: the
caller (``app.py``) does that.
"""

import json
import re
import time
import urllib.request
from datetime import datetime, timezone

MODULE_REPO = 'https://github.com/amnezia-vpn/amneziawg-linux-kernel-module.git'
GO_REPO = 'https://github.com/amnezia-vpn/amneziawg-go'
GO_IMAGE = 'amneziavpn/amneziawg-go'

KERNEL_MODULE = 'kernel_module'
USERSPACE = 'userspace'
COMPONENTS = (KERNEL_MODULE, USERSPACE)

#: ``v3.1.20260812`` -> ``3.1.20260812``.  Anything else is not offered as an
#: update target: release names, ``latest`` and free-form tags are rejected so
#: a malicious or renamed tag can never be passed to a shell script.
TAG_RE = re.compile(r'^v?(\d+\.\d+\.\d{8})$')

_VERSION_RE = re.compile(r'(\d+\.\d+\.\d{8})')

#: GitHub tag listings change slowly; one lookup per component per process is
#: plenty and keeps the status endpoint from being rate limited.
TAG_CACHE_TTL = 6 * 60 * 60
_tag_cache = {}


class PluginUpdateError(Exception):
    """Operation failure with a stable machine-readable ``code``."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_tag(tag):
    """Return the bare version from a release tag, or ``None``."""
    match = TAG_RE.match((tag or '').strip())
    return match.group(1) if match else None


def version_tuple(version):
    """Comparable ``(major, minor, date)`` tuple, or ``None``."""
    parsed = parse_tag(version)
    if not parsed:
        return None
    major, minor, date = parsed.split('.')
    return int(major), int(minor), int(date)


def pick_latest(tags):
    """Highest valid version among ``tags``, ignoring everything else."""
    best = None
    for tag in tags or ():
        version = parse_tag(tag)
        if version is None:
            continue
        if best is None or version_tuple(version) > version_tuple(best):
            best = version
    return best


def _repo_slug(repo):
    """``https://github.com/owner/name.git`` -> ``owner/name``.

    The GitHub API needs the owner: a bare repository name answers 404, which
    is exactly the kind of failure that must not be mistaken for "up to date".
    """
    text = (repo or '').strip()
    if 'github.com/' in text:
        text = text.split('github.com/', 1)[1]
    return text.replace('.git', '').strip('/')


def _github_tags(repo):
    url = 'https://api.github.com/repos/%s/tags?per_page=100' % repo
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'amnezia-web-panel',
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return [entry.get('name', '') for entry in payload if isinstance(entry, dict)]


def _github_compare(repo, base, head):
    url = 'https://api.github.com/repos/%s/compare/%s...%s' % (repo, base, head)
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'amnezia-web-panel',
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode('utf-8'))
    commits = []
    for item in payload.get('commits') or []:
        commits.append({
            'sha': (item.get('sha') or '')[:8],
            'subject': ((item.get('commit') or {}).get('message') or '').splitlines()[0],
        })
    return commits


def _iteration(text):
    return re.findall(r'^(\d+\.\d+\.\d{8})', text or '', re.MULTILINE)


class AwgPluginUpdater:
    """Version discovery and fail-safe updates for one server."""

    def __init__(self, ssh, *, tag_source=None):
        self.ssh = ssh
        self._tag_source = tag_source or _github_tags

    # ---------------------------------------------------------------- versions

    def latest_versions(self):
        """Newest published version of each component."""
        now = time.time()
        result = {}
        for component, repo in ((KERNEL_MODULE, MODULE_REPO), (USERSPACE, GO_REPO)):
            cached = _tag_cache.get(component)
            if cached and now - cached[0] < TAG_CACHE_TTL:
                result[component] = cached[1]
                continue
            name = _repo_slug(repo)
            try:
                tags = self._tag_source(name)
            except Exception as exc:  # network/API failure is not "up to date"
                raise PluginUpdateError(
                    'version_check_failed',
                    'cannot read published versions: %s' % exc,
                )
            latest = pick_latest(tags)
            _tag_cache[component] = (now, latest)
            result[component] = latest
        return result

    def installed_versions(self):
        """Versions actually present on the managed server."""
        out, _, _ = self.ssh.run_command(
            "modinfo -F version amneziawg 2>/dev/null || "
            "cat /sys/module/amneziawg/version 2>/dev/null || true"
        )
        kernel = _VERSION_RE.search((out or '').strip())
        return {
            KERNEL_MODULE: kernel.group(1) if kernel else None,
            USERSPACE: self._userspace_version(),
        }

    def _go_containers(self):
        out, _, _ = self.ssh.run_command(
            "docker ps -a --format '{{.Names}}\t{{.Image}}' 2>/dev/null || true"
        )
        containers = []
        for line in (out or '').splitlines():
            if '\t' not in line:
                continue
            name, image = line.split('\t', 1)
            if image.split(':', 1)[0].strip() != GO_IMAGE:
                continue
            containers.append((name.strip(), image.strip()))
        return containers

    def _userspace_version(self):
        containers = self._go_containers()
        versions = set()
        for name, image in containers:
            out, _, _ = self.ssh.run_command(
                "docker inspect --format "
                "'{{index .Config.Labels \"org.opencontainers.image.version\"}}' "
                "%s 2>/dev/null || true" % name
            )
            for found in _iteration(out or ''):
                versions.add(found)
            if not versions:
                tag = image.split(':', 1)[-1]
                for found in _iteration(tag):
                    versions.add(found)
        if not versions:
            return None
        return sorted(versions, key=version_tuple)[-1]

    def status(self, latest=None, installed=None):
        latest = latest if latest is not None else self.latest_versions()
        installed = installed if installed is not None else self.installed_versions()
        components = {}
        for component in COMPONENTS:
            current = installed.get(component)
            available = latest.get(component)
            components[component] = {
                'installed': current,
                'available': available,
                'update_available': bool(
                    available and (current is None or version_tuple(current) < version_tuple(available))
                ),
                'installed_detected': current is not None,
            }
        return {
            'components': components,
            'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

    def changelog(self, component, version):
        repo = MODULE_REPO if component == KERNEL_MODULE else GO_REPO
        name = _repo_slug(repo)
        installed = self.installed_versions().get(component)
        if not installed or not version:
            return []
        try:
            return _github_compare(
                name,
                'v%s' % installed if not installed.startswith('v') else installed,
                'v%s' % version,
            )
        except Exception as exc:
            raise PluginUpdateError('changelog_failed', 'cannot read changelog: %s' % exc)

    # -------------------------------------------------------------- preflight

    def _module_ref_count(self):
        out, _, _ = self.ssh.run_command(
            "awk '$1==\"amneziawg\"{print $3}' /proc/modules 2>/dev/null || true"
        )
        text = (out or '').strip()
        return int(text) if text.isdigit() else 0

    def preflight(self, component):
        if component not in COMPONENTS:
            raise PluginUpdateError('unsupported', 'unknown component')
        if component == KERNEL_MODULE:
            out, _, _ = self.ssh.run_command(
                "echo KVER=$(uname -r); "
                "test -d /lib/modules/$(uname -r)/build && echo HEADERS=yes || echo HEADERS=no; "
                "command -v dkms >/dev/null && echo DKMS=yes || echo DKMS=no; "
                "command -v gcc >/dev/null && echo GCC=yes || echo GCC=no; "
                "command -v make >/dev/null && echo MAKE=yes || echo MAKE=no"
            )
            values = dict(
                line.split('=', 1) for line in (out or '').splitlines() if '=' in line
            )
            refs = self._module_ref_count()
            blockers = []
            if values.get('HEADERS') != 'yes':
                blockers.append('no kernel headers for the running kernel')
            for tool in ('dkms', 'gcc', 'make'):
                if values.get(tool.upper()) != 'yes':
                    blockers.append('%s is not installed' % tool)
            return {
                'component': component,
                'kernel': values.get('KVER'),
                'requires_interruption': refs > 0,
                'ready': not blockers,
                'blockers': blockers,
            }
        containers = self._go_containers()
        if not containers:
            raise PluginUpdateError('not_installed', 'no userspace AWG containers found')
        return {
            'component': component,
            'containers': [name for name, _ in containers],
            # Pulling an image restarts nothing: the containers keep running
            # the previous image until the protocol is reinstalled.
            'requires_interruption': False,
            'ready': True,
            'blockers': [],
        }

    # ---------------------------------------------------------------- updates

    def update(self, component, target, *, allow_interrupt=False, log=None):
        log = log or (lambda stage, message: None)
        if component not in COMPONENTS:
            raise PluginUpdateError('unsupported', 'unknown component')
        version = parse_tag(target)
        if version is None:
            raise PluginUpdateError('unsupported', 'refusing unsupported target %r' % (target,))

        check = self.preflight(component)
        log('preflight', 'kernel %s, blockers: %s' % (check.get('kernel'), check.get('blockers') or 'none'))
        if check['blockers']:
            raise PluginUpdateError('preflight_failed', '; '.join(check['blockers']))
        if check['requires_interruption'] and not allow_interrupt:
            raise PluginUpdateError(
                'requires_confirmation',
                'updating this component temporarily interrupts active tunnels',
            )

        if component == KERNEL_MODULE:
            return self._update_kernel(version, allow_interrupt, log)
        return self._update_userspace(version, allow_interrupt, log)

    # -- kernel ---------------------------------------------------------------

    def _run(self, command, log, stage, timeout=120, sudo=False):
        log(stage, command)
        runner = self.ssh.run_sudo_script if sudo else self.ssh.run_command
        out, err, code = runner(command, timeout=timeout)
        text = ((out or '') + (err or '')).strip()
        if text:
            for line in text.splitlines()[-40:]:
                log(stage, line)
        return out or '', err or '', code

    def _update_kernel(self, version, allow_interrupt, log):
        previous = self.installed_versions().get(KERNEL_MODULE)
        stopped = self._stop_awg_containers(log) if allow_interrupt else []

        try:
            # 1) Build the new module next to the old one.  A failure here
            #    leaves the installed module untouched.
            self._run('rm -rf /tmp/awg-plugin-update', log, 'prepare')
            out, err, code = self._run(
                'git clone --depth 1 --branch v%s %s /tmp/awg-plugin-update'
                % (version, MODULE_REPO),
                log, 'download', timeout=300,
            )
            if code != 0:
                raise PluginUpdateError('update_failed', 'cannot download module sources')

            self._run(
                'cd /tmp/awg-plugin-update/src && '
                "sed -i 's/^PACKAGE_VERSION=.*/PACKAGE_VERSION=\"%s\"/' dkms.conf"
                % version,
                log, 'prepare',
            )
            out, err, code = self._run(
                'cd /tmp/awg-plugin-update/src && dkms add .', log, 'dkms-add', timeout=300,
            )
            if code != 0:
                raise PluginUpdateError('update_failed', 'dkms add failed')

            out, err, code = self._run(
                'dkms build amneziawg/%s' % version, log, 'build', timeout=1800,
            )
            if code != 0:
                self._run('dkms remove amneziawg/%s --all' % version, log, 'cleanup', timeout=300)
                raise PluginUpdateError('update_failed', 'dkms build failed; previous module kept')

            out, err, code = self._run(
                'dkms install amneziawg/%s --force' % version, log, 'install', timeout=600,
            )
            if code != 0:
                self._run('dkms remove amneziawg/%s --all' % version, log, 'cleanup', timeout=300)
                raise PluginUpdateError('update_failed', 'dkms install failed; previous module kept')

            # 2) Swap the loaded module only now.  If this fails we remove the
            #    new DKMS version and reload whatever was active before.
            log('activate', 'unloading the current module')
            self._run('modprobe -r amneziawg', log, 'activate', timeout=120, sudo=True)
            out, err, code = self._run('modprobe amneziawg', log, 'activate', timeout=120, sudo=True)
            if code != 0:
                self._rollback_kernel(version, previous, log)
                raise PluginUpdateError('update_failed', 'module built but could not be loaded; rolled back')

            out, _, _ = self._run(
                'modinfo -F version amneziawg 2>/dev/null || true', log, 'verify',
            )
            loaded = _VERSION_RE.search(out or '')
            if not loaded or loaded.group(1) != version:
                self._rollback_kernel(version, previous, log)
                raise PluginUpdateError('update_failed', 'loaded module version mismatch; rolled back')

            self._start_awg_containers(stopped, log)
            return {
                'component': KERNEL_MODULE,
                'previous': previous,
                'installed': version,
                'state': 'updated',
                'rolled_back': False,
            }
        except PluginUpdateError:
            self._start_awg_containers(stopped, log)
            raise
        except Exception as exc:
            self._start_awg_containers(stopped, log)
            raise PluginUpdateError('update_failed', str(exc))

    def _rollback_kernel(self, version, previous, log):
        """Restore the previously loaded module after a failed activation."""
        log('rollback', 'restoring previous module %s' % (previous or 'unknown'))
        self._run('dkms remove amneziawg/%s --all' % version, log, 'rollback', timeout=600)
        self._run('depmod -a', log, 'rollback', timeout=120, sudo=True)
        self._run('modprobe amneziawg', log, 'rollback', timeout=120, sudo=True)
        out, _, _ = self._run(
            'modinfo -F version amneziawg 2>/dev/null || true', log, 'rollback',
        )
        loaded = _VERSION_RE.search(out or '')
        if previous and (not loaded or loaded.group(1) != previous):
            raise PluginUpdateError(
                'rollback_failed',
                'could not restore module %s; reload the host before relying on AWG' % previous,
            )

    def _awg_container_names(self):
        out, _, _ = self.ssh.run_command(
            "docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^amnezia-awg' || true"
        )
        return [line.strip() for line in (out or '').splitlines() if line.strip()]

    def _stop_awg_containers(self, log):
        names = self._awg_container_names()
        for name in names:
            log('stop', 'stopping %s to release the kernel module' % name)
            self.ssh.run_command('docker stop %s' % name, timeout=120)
        return names

    def _start_awg_containers(self, names, log):
        for name in names or ():
            log('start', 'starting %s' % name)
            self.ssh.run_command('docker start %s' % name, timeout=120)

    # -- userspace ------------------------------------------------------------

    def _update_userspace(self, version, allow_interrupt, log):
        """Pull the image and stop.

        Recreating a user's AWG container from `docker inspect` cannot be done
        safely: the panel builds the image from a generated Dockerfile and the
        container carries bind mounts, capabilities and a start script that is
        regenerated by ``install_protocol``.  A half-faithful ``docker run``
        would silently drop parts of that configuration, so this version only
        verifies that the registry has the requested image and tells the admin
        to reinstall the protocol, which performs the recreate through the
        panel's own, tested path.
        """
        containers = self._go_containers()
        if not containers:
            raise PluginUpdateError('not_installed', 'no userspace AWG containers found')

        before = self._userspace_version()
        log('pull', 'pulling %s:latest' % GO_IMAGE)
        out, err, code = self.ssh.run_command(
            'docker pull %s:latest' % GO_IMAGE, timeout=1800,
        )
        text = ((out or '') + (err or '')).strip()
        for line in text.splitlines()[-40:]:
            log('pull', line)
        if code != 0:
            raise PluginUpdateError('update_failed', 'image pull failed; containers untouched')

        after = self._userspace_version()
        if after is None or version_tuple(after) is None or version_tuple(after) < version_tuple(version):
            log('verify', 'registry image is still %s, expected %s' % (after, version))
            raise PluginUpdateError(
                'unsupported',
                'the published image does not contain %s yet; nothing was restarted' % version,
            )

        for name, _ in containers:
            log('manual', '%s keeps running the previous image until the protocol is reinstalled' % name)
        return {
            'component': USERSPACE,
            'previous': before,
            'installed': after,
            'state': 'manual_step_required',
            'rolled_back': False,
        }
