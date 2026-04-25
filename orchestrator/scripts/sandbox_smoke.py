"""End-to-end smoke for the sandbox backends.

Runs real processes through the configured backend and asserts the
isolation policy actually holds. Unit tests verify argv translation;
this script verifies the *behaviour* — does the kernel actually deny
the writes we said it would.

Usage:
    .venv/bin/python scripts/sandbox_smoke.py docker
    .venv/bin/python scripts/sandbox_smoke.py bubblewrap
    .venv/bin/python scripts/sandbox_smoke.py none

The script exits 0 if every assertion holds. It exits non-zero (and
prints which assertion failed) if any policy is silently bypassed —
treat that as a regression.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from agentsofchaos_orchestrator.infrastructure.sandbox import (
    SandboxBackend,
    SandboxKind,
    SandboxNetworkPolicy,
    SandboxedExecutionRequest,
    SandboxedExecutionSpec,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.bubblewrap import (
    BubblewrapSandboxBackend,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.docker import DockerSandboxBackend
from agentsofchaos_orchestrator.infrastructure.sandbox.none_backend import NoSandboxBackend


def select_backend(name: str) -> SandboxBackend:
    if name == "none":
        return NoSandboxBackend()
    if name == "bubblewrap":
        return BubblewrapSandboxBackend()
    if name == "docker":
        # Alpine has sh + getent + write-protected /etc; nothing fancy.
        return DockerSandboxBackend(image="alpine:latest")
    raise SystemExit(f"unknown backend: {name}")


async def run_capture(
    sandbox: SandboxBackend,
    spec: SandboxedExecutionSpec,
) -> tuple[int, str, str]:
    proc = await sandbox.spawn(SandboxedExecutionRequest(spec=spec))
    stdout, stderr = await proc.communicate()
    rc = proc.returncode if proc.returncode is not None else -1
    return rc, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def smoke(sandbox: SandboxBackend) -> None:
    print(f"# {sandbox.kind.value}")
    await sandbox.probe()
    print("  probe: ok")

    with tempfile.TemporaryDirectory() as workdir_str:
        work = Path(workdir_str)
        (work / "input.txt").write_text("hello\n", encoding="utf-8")

        # 1) Roundtrip: read + write inside the RW mount.
        rc, out, _ = await run_capture(
            sandbox,
            SandboxedExecutionSpec(
                command=(
                    "sh",
                    "-c",
                    f"cat {work}/input.txt && echo wrote >> {work}/input.txt && echo done",
                ),
                cwd=work,
                read_write_mounts=(work,),
                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
                network=SandboxNetworkPolicy.NONE,
            ),
        )
        assert rc == 0, f"roundtrip exit {rc}: {out}"
        assert "hello" in out and "done" in out, f"roundtrip stdout: {out!r}"
        assert (work / "input.txt").read_text() == "hello\nwrote\n", "host file not updated"
        print("  rw mount: ok")

        # 2) Negative: write outside the RW mount must fail.
        # NoSandboxBackend can't enforce this (it's just a subprocess);
        # skip the assertion there but still print whether the write
        # happened so smoke output is honest.
        rc, out, _ = await run_capture(
            sandbox,
            SandboxedExecutionSpec(
                command=(
                    "sh",
                    "-c",
                    "echo pwned > /etc/aoc-smoke 2>&1; echo exit=$?",
                ),
                cwd=work,
                read_write_mounts=(work,),
                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
                network=SandboxNetworkPolicy.NONE,
            ),
        )
        if sandbox.kind is SandboxKind.NONE:
            print(f"  fs deny: SKIPPED (none backend offers no fs isolation)")
        else:
            assert "exit=0" not in out, f"FS WRITE ESCAPED SANDBOX: {out!r}"
            print("  fs deny: ok")

        # 3) Network policy: with NONE, DNS must fail.
        rc, out, _ = await run_capture(
            sandbox,
            SandboxedExecutionSpec(
                command=(
                    "sh",
                    "-c",
                    "getent hosts example.com 2>&1; echo exit=$?",
                ),
                cwd=work,
                read_write_mounts=(work,),
                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
                network=SandboxNetworkPolicy.NONE,
            ),
        )
        if sandbox.kind is SandboxKind.NONE:
            print("  net deny: SKIPPED (none backend has no network isolation)")
        else:
            assert "exit=0" not in out, f"DNS RESOLVED UNDER network=none: {out!r}"
            print("  net deny: ok")

        # 4) Network policy: with FULL, DNS must succeed — otherwise no
        # LLM-backed agent (Pi, Claude Code, Codex) can reach its
        # provider, and the sandbox is unusable for the actual runtimes
        # we ship.
        rc, out, _ = await run_capture(
            sandbox,
            SandboxedExecutionSpec(
                command=(
                    "sh",
                    "-c",
                    "getent hosts example.com 2>&1; echo exit=$?",
                ),
                cwd=work,
                read_write_mounts=(work,),
                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
                network=SandboxNetworkPolicy.FULL,
            ),
        )
        if sandbox.kind is SandboxKind.NONE:
            print("  net allow: ok (no isolation)")
        else:
            assert "exit=0" in out, f"DNS FAILED under network=full: {out!r}"
            print("  net allow: ok")

        # 5) Env whitelist: only what the spec contained plus container/host defaults.
        rc, out, _ = await run_capture(
            sandbox,
            SandboxedExecutionSpec(
                command=("sh", "-c", "env | sort"),
                cwd=work,
                read_write_mounts=(work,),
                env={
                    "AOC_SMOKE_TOKEN": "intended",
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                },
                network=SandboxNetworkPolicy.NONE,
            ),
        )
        assert "AOC_SMOKE_TOKEN=intended" in out, f"env passthrough lost: {out!r}"
        # Anything daemon-specific (e.g. AOC_DATABASE_URL) must NOT have leaked.
        assert "AOC_DATABASE_URL" not in out, f"daemon env leaked into sandbox: {out!r}"
        print("  env whitelist: ok")

    print(f"# {sandbox.kind.value}: all checks passed")


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "none"
    asyncio.run(smoke(select_backend(name)))


if __name__ == "__main__":
    main()
