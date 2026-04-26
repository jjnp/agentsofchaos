from __future__ import annotations

import asyncio
import os
import shutil

from agentsofchaos_orchestrator.domain.errors import (
    RuntimeExecutionError,
    SandboxUnavailableError,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    SandboxBackend,
    SandboxedExecutionRequest,
    SandboxedExecutionSpec,
    SandboxedProcess,
    SandboxKind,
    SandboxNetworkPolicy,
)


class DockerSandboxBackend:
    """Container-based sandbox using ``docker run``.

    Translates a ``SandboxedExecutionSpec`` into:

        docker run --rm --init
                   --user <uid>:<gid>
                   -w <cwd>
                   -v <rw>:<rw>:rw   (per RW mount)
                   -v <ro>:<ro>:ro   (per RO mount)
                   --network=<none|host>
                   -e KEY=VAL ...
                   <image> -- <command...>

    The image is configurable; default is a slim base. Operators are
    expected to choose an image that already contains the toolchain
    their runtime needs (for Pi: a base with the ``pi`` binary mounted
    in via an extra RO mount, or baked into the image).

    Stronger isolation than bubblewrap (separate filesystem, cgroup
    limits, named-network policy) at the cost of process startup
    latency and a docker daemon dependency.
    """

    def __init__(
        self,
        *,
        docker_binary: str = "docker",
        image: str = "debian:stable-slim",
    ) -> None:
        self._docker_binary = docker_binary
        self._image = image

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DOCKER

    async def probe(self) -> None:
        if shutil.which(self._docker_binary) is None:
            raise SandboxUnavailableError(
                f"docker binary {self._docker_binary!r} not found on PATH; "
                "install docker or set AOC_SANDBOX_BACKEND=none"
            )
        # ``docker info`` exercises the daemon socket too — a missing
        # daemon is the most common reason `docker` is on PATH but
        # unusable on a fresh machine.
        process = await asyncio.create_subprocess_exec(
            self._docker_binary,
            "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace").strip() or "docker info failed"
            raise SandboxUnavailableError(f"docker probe failed: {message}")

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
                    "docker process closed stdin before input was delivered"
                ) from error
        return process  # type: ignore[return-value]

    def build_argv(self, spec: SandboxedExecutionSpec) -> tuple[str, ...]:
        argv: list[str] = [
            self._docker_binary,
            "run",
            "--rm",
            "--init",
            # Attach stdin without allocating a TTY. Required for any
            # RPC-style runtime (pi --mode rpc, claude-code, codex)
            # that reads JSON commands from stdin; without `-i` the
            # container sees EOF immediately and exits before the
            # orchestrator can send its first command.
            "-i",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-w",
            str(spec.cwd),
            "--network",
            "none" if spec.network is SandboxNetworkPolicy.NONE else "host",
        ]
        for rw_mount in spec.read_write_mounts:
            argv.extend(["-v", f"{rw_mount}:{rw_mount}:rw"])
        for ro_mount in spec.read_only_mounts:
            argv.extend(["-v", f"{ro_mount}:{ro_mount}:ro"])
        for key, value in spec.env.items():
            argv.extend(["-e", f"{key}={value}"])
        argv.append(self._image)
        argv.extend(spec.command)
        return tuple(argv)


_: SandboxBackend = DockerSandboxBackend()
