"""Sandbox backend tests.

The bubblewrap and docker backends are only end-to-end runnable on
hosts that ship the corresponding binary. Tests focus on the
deterministic argv-translation surface — which is the only place where
backend bugs can introduce silent policy holes.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from agentsofchaos_orchestrator.domain.errors import SandboxUnavailableError
from agentsofchaos_orchestrator.infrastructure.sandbox import (
    NoSandboxBackend,
    SandboxKind,
    SandboxNetworkPolicy,
    SandboxedExecutionRequest,
    SandboxedExecutionSpec,
    build_sandbox_backend,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.bubblewrap import (
    BubblewrapSandboxBackend,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.docker import DockerSandboxBackend
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def _spec(tmp_path: Path, *, network: SandboxNetworkPolicy = SandboxNetworkPolicy.FULL) -> SandboxedExecutionSpec:
    cwd = tmp_path / "work"
    cwd.mkdir()
    ro = tmp_path / "creds"
    ro.mkdir()
    return SandboxedExecutionSpec(
        command=("echo", "hello"),
        cwd=cwd,
        read_write_mounts=(cwd,),
        read_only_mounts=(ro,),
        env={"FOO": "bar"},
        network=network,
    )


def test_no_sandbox_kind_and_probe_is_inert() -> None:
    sandbox = NoSandboxBackend()
    assert sandbox.kind is SandboxKind.NONE
    asyncio.run(sandbox.probe())  # never raises


@pytest.mark.asyncio
async def test_no_sandbox_round_trips_stdout(tmp_path: Path) -> None:
    sandbox = NoSandboxBackend()
    spec = SandboxedExecutionSpec(
        command=("/bin/sh", "-c", "echo hello-from-sandbox"),
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
    )
    process = await sandbox.spawn(SandboxedExecutionRequest(spec=spec))
    stdout, _stderr = await process.communicate()
    assert process.returncode == 0
    assert stdout.strip() == b"hello-from-sandbox"


def test_bubblewrap_argv_layout(tmp_path: Path) -> None:
    backend = BubblewrapSandboxBackend(bwrap_binary="bwrap")
    spec = _spec(tmp_path, network=SandboxNetworkPolicy.NONE)
    argv = backend.build_argv(spec)

    # Sanity: invocation, RO system mounts, RW worktree, network unshare,
    # explicit chdir, env passthrough only via --setenv (no host inherit),
    # command separator, then the actual command.
    assert argv[0] == "bwrap"
    assert "--die-with-parent" in argv
    assert "--new-session" in argv
    assert "--unshare-net" in argv

    # RW worktree is bound RW; RO creds bound RO (via --ro-bind-try so
    # absent paths don't break the spawn).
    rw_arg = argv.index("--bind")
    assert argv[rw_arg + 1] == str(spec.cwd)
    ro_arg = argv.index("--ro-bind-try")
    assert argv[ro_arg + 1] == str(spec.read_only_mounts[0])

    # Env is delivered through bwrap's setenv flag, not by inheritance.
    setenv_index = argv.index("--setenv")
    assert argv[setenv_index + 1 : setenv_index + 3] == ("FOO", "bar")

    # `--` separates bwrap flags from the spawned command.
    sep = argv.index("--", argv.index("--setenv"))
    assert tuple(argv[sep + 1 :]) == spec.command


def test_bubblewrap_argv_full_network_does_not_unshare(tmp_path: Path) -> None:
    backend = BubblewrapSandboxBackend(bwrap_binary="bwrap")
    argv = backend.build_argv(_spec(tmp_path, network=SandboxNetworkPolicy.FULL))
    assert "--unshare-net" not in argv


@pytest.mark.asyncio
async def test_bubblewrap_probe_fails_when_binary_missing() -> None:
    backend = BubblewrapSandboxBackend(bwrap_binary="bwrap-this-does-not-exist")
    with pytest.raises(SandboxUnavailableError):
        await backend.probe()


def test_bubblewrap_userns_hint_apparmor_block() -> None:
    # Real Ubuntu 24.04 stderr captured during this very build.
    stderr = "bwrap: setting up uid map: Permission denied"
    hint = BubblewrapSandboxBackend._userns_failure_hint(stderr)
    assert "AppArmor" in hint
    assert "apparmor_restrict_unprivileged_userns" in hint


def test_bubblewrap_userns_hint_kernel_disabled() -> None:
    stderr = "bwrap: cannot open /proc/self/uid_map: No such file or directory"
    hint = BubblewrapSandboxBackend._userns_failure_hint(stderr)
    assert "CONFIG_USER_NS" in hint or "user namespaces" in hint.lower()


def test_bubblewrap_userns_hint_generic_fallback() -> None:
    hint = BubblewrapSandboxBackend._userns_failure_hint("totally unfamiliar error")
    assert "AOC_SANDBOX_BACKEND" in hint


def test_docker_argv_layout(tmp_path: Path) -> None:
    backend = DockerSandboxBackend(docker_binary="docker", image="debian:stable-slim")
    spec = _spec(tmp_path, network=SandboxNetworkPolicy.NONE)
    argv = backend.build_argv(spec)

    assert argv[0] == "docker"
    assert argv[1] == "run"
    assert "--rm" in argv
    assert "--init" in argv
    # Stdin attached without a TTY so RPC runtimes can be driven.
    assert "-i" in argv

    # Network mode is none for the requested policy.
    network_idx = argv.index("--network")
    assert argv[network_idx + 1] == "none"

    # User + workdir set up correctly.
    user_idx = argv.index("--user")
    assert argv[user_idx + 1] == f"{os.getuid()}:{os.getgid()}"
    workdir_idx = argv.index("-w")
    assert argv[workdir_idx + 1] == str(spec.cwd)

    # Mounts are listed with the right RW/RO suffix.
    rw_mount = f"{spec.read_write_mounts[0]}:{spec.read_write_mounts[0]}:rw"
    ro_mount = f"{spec.read_only_mounts[0]}:{spec.read_only_mounts[0]}:ro"
    assert rw_mount in argv
    assert ro_mount in argv

    # Env arrives via -e KEY=VAL.
    assert "FOO=bar" in argv

    # Image precedes the command.
    image_idx = argv.index("debian:stable-slim")
    assert tuple(argv[image_idx + 1 :]) == spec.command


def test_docker_argv_full_network_uses_host(tmp_path: Path) -> None:
    backend = DockerSandboxBackend(docker_binary="docker", image="debian:stable-slim")
    argv = backend.build_argv(_spec(tmp_path, network=SandboxNetworkPolicy.FULL))
    network_idx = argv.index("--network")
    assert argv[network_idx + 1] == "host"


@pytest.mark.asyncio
async def test_docker_probe_fails_when_binary_missing() -> None:
    backend = DockerSandboxBackend(
        docker_binary="docker-this-does-not-exist",
        image="debian:stable-slim",
    )
    with pytest.raises(SandboxUnavailableError):
        await backend.probe()


def test_factory_resolves_kind_from_settings() -> None:
    none_settings = Settings(sandbox_backend=SandboxKind.NONE)
    bubblewrap_settings = Settings(sandbox_backend=SandboxKind.BUBBLEWRAP)
    docker_settings = Settings(sandbox_backend=SandboxKind.DOCKER)

    assert build_sandbox_backend(none_settings).kind is SandboxKind.NONE
    assert build_sandbox_backend(bubblewrap_settings).kind is SandboxKind.BUBBLEWRAP
    assert build_sandbox_backend(docker_settings).kind is SandboxKind.DOCKER
