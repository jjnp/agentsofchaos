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
        process = await asyncio.create_subprocess_exec(
            self._bwrap_binary,
            "--version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        rc = await process.wait()
        if rc != 0:
            raise SandboxUnavailableError(
                f"bubblewrap binary {self._bwrap_binary!r} failed `--version` (exit {rc})"
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

        # Build env from the spec only. ``--setenv`` adds; we never
        # inherit the daemon's env into the namespace.
        for key, value in spec.env.items():
            argv.extend(["--setenv", key, value])

        argv.append("--")
        argv.extend(spec.command)
        return tuple(argv)

    @staticmethod
    def _add_mount(argv: list[str], flag: str, path: Path) -> None:
        path_str = str(path)
        argv.extend([flag, path_str, path_str])


_: SandboxBackend = BubblewrapSandboxBackend()
