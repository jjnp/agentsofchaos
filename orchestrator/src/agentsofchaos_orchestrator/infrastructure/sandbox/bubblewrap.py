from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from agentsofchaos_orchestrator.domain.errors import (
    RuntimeExecutionError,
    SandboxUnavailableError,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    SandboxBackend,
    SandboxKind,
    SandboxNetworkPolicy,
    SandboxedExecutionRequest,
    SandboxedExecutionSpec,
    SandboxedProcess,
)


class BubblewrapSandboxBackend:
    """Namespace-based sandbox using ``bwrap``.

    Builds an argv that:
      * binds host ``/usr``, ``/bin``, ``/lib``, ``/lib64``, ``/etc``
        read-only so the agent has a usable userspace
      * binds each requested RW mount read-write
      * binds each requested RO mount read-only
      * exposes ``/proc`` and a minimal ``/dev``
      * unshares the network when ``network=none``
      * enters a fresh session and dies with the parent so any
        accidental orphaned processes are reaped
      * sets only the env vars in the spec (no ``--clearenv`` because
        we never inherit; we build env from the spec)

    Bubblewrap is intentionally light. It does not protect against
    kernel exploits or resource exhaustion — pick the docker backend
    for those.
    """

    def __init__(self, *, bwrap_binary: str = "bwrap") -> None:
        self._bwrap_binary = bwrap_binary

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.BUBBLEWRAP

    async def probe(self) -> None:
        if shutil.which(self._bwrap_binary) is None:
            raise SandboxUnavailableError(
                f"bubblewrap binary {self._bwrap_binary!r} not found on PATH; "
                "install bubblewrap or set AOC_SANDBOX_BACKEND=none"
            )
        version_proc = await asyncio.create_subprocess_exec(
            self._bwrap_binary,
            "--version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        rc = await version_proc.wait()
        if rc != 0:
            raise SandboxUnavailableError(
                f"bubblewrap binary {self._bwrap_binary!r} failed `--version` (exit {rc})"
            )
        # `bwrap --version` doesn't exercise namespace creation, which is
        # the actual failure mode operators hit on hosts that ship bwrap
        # but block unprivileged user namespaces (Ubuntu 24.04+ via
        # AppArmor, hardened containers, etc.). Catch that here so the
        # daemon refuses to start instead of failing on the first run
        # with a cryptic "setting up uid map: Permission denied".
        # Need to expose at least one host program so bwrap can exec it
        # *after* the namespace is up. ``--ro-bind /`` is harmless for a
        # probe and ensures whatever path we pick (`/usr/bin/true`,
        # `/bin/true`, …) is reachable.
        userns_proc = await asyncio.create_subprocess_exec(
            self._bwrap_binary,
            "--unshare-user",
            "--uid",
            "0",
            "--gid",
            "0",
            "--ro-bind",
            "/",
            "/",
            "--",
            "/usr/bin/true" if Path("/usr/bin/true").exists() else "/bin/true",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await userns_proc.communicate()
        if userns_proc.returncode != 0:
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            hint = self._userns_failure_hint(stderr)
            raise SandboxUnavailableError(
                f"bubblewrap cannot create an unprivileged user namespace on this "
                f"host (exit {userns_proc.returncode}). Underlying error: {stderr!r}.\n"
                f"{hint}"
            )

    @staticmethod
    def _userns_failure_hint(stderr: str) -> str:
        # The two most common shapes we've seen on real hosts:
        #   * "setting up uid map: Permission denied" — Ubuntu 24.04
        #     AppArmor's `restrict_unprivileged_userns` block
        #   * "No such file or directory" on /proc/self/uid_map — kernel
        #     userns disabled entirely
        lower = stderr.lower()
        if "uid map" in lower and "permission denied" in lower:
            return (
                "This is the Ubuntu 24.04+ AppArmor restriction on "
                "unprivileged user namespaces. Either:\n"
                "  - relax it system-wide: "
                "`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`\n"
                "  - or install a per-binary AppArmor profile that "
                "permits unpriv-userns for the bwrap binary.\n"
                "Alternatively switch to AOC_SANDBOX_BACKEND=docker or =none."
            )
        if "no such file" in lower and "uid_map" in lower:
            return (
                "User namespaces appear to be disabled in this kernel "
                "(/proc/self/uid_map missing). Enable CONFIG_USER_NS or "
                "switch to AOC_SANDBOX_BACKEND=docker or =none."
            )
        return (
            "Switch to AOC_SANDBOX_BACKEND=docker or =none, or fix the "
            "underlying user-namespace permissions on this host."
        )

    async def spawn(self, request: SandboxedExecutionRequest) -> SandboxedProcess:
        argv = self.build_argv(request.spec)
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if request.stdin is not None and process.stdin is not None:
            process.stdin.write(request.stdin)
            try:
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as error:
                raise RuntimeExecutionError(
                    "bubblewrap process closed stdin before input was delivered"
                ) from error
        return process  # type: ignore[return-value]

    def build_argv(self, spec: SandboxedExecutionSpec) -> tuple[str, ...]:
        argv: list[str] = [
            self._bwrap_binary,
            "--die-with-parent",
            "--new-session",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]
        # Read-only system directories so the agent has a working userspace.
        for system_dir in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc"):
            if Path(system_dir).exists():
                argv.extend(["--ro-bind", system_dir, system_dir])

        for ro_mount in spec.read_only_mounts:
            self._add_mount(argv, "--ro-bind-try", ro_mount)
        for rw_mount in spec.read_write_mounts:
            self._add_mount(argv, "--bind", rw_mount)

        # Always make the cwd reachable; harmless duplicate of an
        # explicit RW mount if the caller already listed it.
        argv.extend(["--chdir", str(spec.cwd)])

        if spec.network is SandboxNetworkPolicy.NONE:
            argv.append("--unshare-net")
        else:
            # Network=full means "share the host netns", but DNS still
            # has to work inside the sandbox. On systemd-resolved
            # distros (Ubuntu, Fedora, Debian-12+) /etc/resolv.conf is
            # a symlink to /run/systemd/resolve/stub-resolv.conf — and
            # /run is not part of our default ro-bind set. Without this
            # the agent gets `getent hosts: not found` and every LLM
            # call fails before it leaves the box.
            for resolver_dir in self._resolve_dns_state_dirs():
                self._add_mount(argv, "--ro-bind-try", resolver_dir)

        # Build env from the spec only. ``--setenv`` adds; we never
        # inherit the daemon's env into the namespace.
        for key, value in spec.env.items():
            argv.extend(["--setenv", key, value])

        argv.append("--")
        argv.extend(spec.command)
        return tuple(argv)

    @staticmethod
    def _resolve_dns_state_dirs() -> tuple[Path, ...]:
        """Directories the symlink-following DNS resolution chain hits.

        Empty when /etc/resolv.conf is a regular file (no fix needed).
        Otherwise contains the parent of whatever the symlink ends up
        pointing at, so the chain resolves inside the sandbox.
        """
        resolv = Path("/etc/resolv.conf")
        if not resolv.is_symlink():
            return ()
        try:
            target = resolv.resolve(strict=False)
        except OSError:
            return ()
        target_dir = target.parent
        # Skip if the target already lives in /etc (we already bound it).
        try:
            target_dir.relative_to("/etc")
            return ()
        except ValueError:
            return (target_dir,)

    @staticmethod
    def _add_mount(argv: list[str], flag: str, path: Path) -> None:
        path_str = str(path)
        argv.extend([flag, path_str, path_str])


_: SandboxBackend = BubblewrapSandboxBackend()
