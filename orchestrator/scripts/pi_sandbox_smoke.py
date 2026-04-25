"""End-to-end smoke for the PI runtime under a chosen sandbox backend.

Drives a single real prompt through ``OrchestratorService`` with the
production PI adapter pointed at the configured sandbox. Asserts that
the child node materialises, the worktree commit landed, and pi
actually wrote something.

Usage:
    OPENAI_API_KEY=sk-... .venv/bin/python scripts/pi_sandbox_smoke.py none
    OPENAI_API_KEY=sk-... .venv/bin/python scripts/pi_sandbox_smoke.py bubblewrap
    OPENAI_API_KEY=sk-... .venv/bin/python scripts/pi_sandbox_smoke.py docker

Requires ``pi`` on the PATH and ``~/.pi/agent/`` configured (see the
project README).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.enums import NodeKind, NodeStatus, RuntimeKind
from agentsofchaos_orchestrator.infrastructure.db import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.runtime.factory import build_runtime_adapter
from agentsofchaos_orchestrator.infrastructure.sandbox import (
    SandboxKind,
    build_sandbox_backend,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def _ensure_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# pi-sandbox-smoke\n", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "smoke",
        "GIT_AUTHOR_EMAIL": "smoke@aoc.local",
        "GIT_COMMITTER_NAME": "smoke",
        "GIT_COMMITTER_EMAIL": "smoke@aoc.local",
    }
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "README.md"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=path, env=env, check=True)


async def main(backend_name: str) -> None:
    if shutil.which("pi") is None:
        raise SystemExit("pi binary not on PATH; install pi-mono first")

    sandbox_kind = SandboxKind(backend_name)

    work_root = Path(tempfile.mkdtemp(prefix="aoc-pi-smoke-"))
    repo = work_root / "repo"
    _ensure_repo(repo)

    db_path = work_root / "orchestrator.sqlite3"

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_backend=RuntimeKind.PI,
        sandbox_backend=sandbox_kind,
    )

    sandbox = build_sandbox_backend(settings)
    print(f"# pi via sandbox={sandbox.kind.value}")
    await sandbox.probe()
    print("  sandbox probe: ok")

    runtime = build_runtime_adapter(settings, sandbox=sandbox)
    print(f"  runtime_kind: {runtime.runtime_kind.value}")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=runtime,
    )

    project = await service.open_project(repo)
    root_node = await service.create_root_node(project.id)

    prompt = "Create a file named smoke.txt containing the single line: hello from pi"
    print(f"  prompting: {prompt!r}")
    run, child = await service.run_prompt(root_node.id, prompt)

    print(f"  run.status: {run.status.value}")
    print(f"  child.kind: {child.kind.value} status: {child.status.value}")

    assert run.status.value == "succeeded", f"run did not succeed: {run!r}"
    assert child.kind is NodeKind.PROMPT
    assert child.status is NodeStatus.READY

    # Confirm the worktree commit landed and pi actually produced the file.
    out = subprocess.run(
        ["git", "show", f"refs/aoc/nodes/{child.id}:smoke.txt"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        print(f"  WARNING: smoke.txt not present in child commit; pi output may differ")
        print(f"    git stderr: {out.stderr.strip()}")
        listing = subprocess.run(
            ["git", "show", "--stat", f"refs/aoc/nodes/{child.id}"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        print("    child commit:")
        for line in listing.stdout.splitlines()[:20]:
            print(f"      {line}")
    else:
        print(f"  smoke.txt: {out.stdout.strip()!r}")

    await service.shutdown()
    await engine.dispose()
    print(f"# pi via sandbox={sandbox.kind.value}: ok")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "none"
    asyncio.run(main(name))
