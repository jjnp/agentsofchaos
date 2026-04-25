"""HTTP-level integration tests against the FastAPI app.

These complement the in-process unit tests in test_prompt_run.py /
test_orchestrator_service.py / test_merge_flow.py / etc. by exercising
the routing layer, response schemas, and error handlers end-to-end with
the same shapes the frontend consumes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentsofchaos_orchestrator.api.app import create_app
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from tests.helpers import initialize_test_repository


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_path = tmp_path / "api-int.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_backend="noop",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    return repository_root


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "Orchestrator" in body["app_name"]


def test_open_project_is_idempotent(client: TestClient, repo: Path) -> None:
    first = client.post("/projects/open", json={"path": str(repo)})
    assert first.status_code == 201, first.text
    project_id = first.json()["id"]

    second = client.post("/projects/open", json={"path": str(repo)})
    assert second.status_code == 201
    assert second.json()["id"] == project_id, "re-opening the same path must return the same project id"


def test_open_invalid_path_is_400(client: TestClient, tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    r = client.post("/projects/open", json={"path": str(not_a_repo)})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "INVALID_REPOSITORY"


def test_full_root_prompt_flow(client: TestClient, repo: Path) -> None:
    """The flow the frontend's smoke test exercises, but at the HTTP level."""
    open_r = client.post("/projects/open", json={"path": str(repo)})
    project_id = open_r.json()["id"]

    # Empty graph at first.
    graph0 = client.get(f"/projects/{project_id}/graph").json()
    assert graph0["nodes"] == []

    # Create root.
    root_r = client.post(f"/projects/{project_id}/nodes/root")
    assert root_r.status_code == 201, root_r.text
    root = root_r.json()
    assert root["kind"] == "root"
    assert root["status"] == "ready"
    assert root["parent_node_ids"] == []
    root_id = root["id"]

    # Second root attempt → 409.
    second_root = client.post(f"/projects/{project_id}/nodes/root")
    assert second_root.status_code == 409
    assert second_root.json()["error"]["code"] == "ROOT_NODE_ALREADY_EXISTS"

    # Single-node fetch round-trips.
    by_id = client.get(f"/projects/{project_id}/nodes/{root_id}").json()
    assert by_id == root

    # Code snapshot expansion.
    code = client.get(
        f"/projects/{project_id}/code-snapshots/{root['code_snapshot_id']}"
    ).json()
    assert len(code["commit_sha"]) == 40
    assert code["git_ref"]

    # Diff against empty tree shows the seeded README.md as added.
    diff = client.get(f"/projects/{project_id}/nodes/{root_id}/diff").json()
    assert diff["base_commit_sha"] is None
    assert diff["totals"]["files"] == 1
    assert any(f["path"] == "README.md" and f["change_type"] == "added" for f in diff["files"])

    # Prompt the root → noop runtime succeeds quickly → child node appears.
    run_r = client.post(
        f"/projects/{project_id}/nodes/{root_id}/runs/prompt",
        json={"prompt": "smoke prompt"},
    )
    assert run_r.status_code == 201, run_r.text
    run = run_r.json()
    assert run["source_node_id"] == root_id
    # Sandbox audit trail: every run records which sandbox contained it.
    # The TestClient fixture uses the default settings (sandbox_backend=none),
    # so we expect "none" here. Operators flipping AOC_SANDBOX_BACKEND will
    # see "bubblewrap"/"docker" persisted on every subsequent run — the
    # whole point of the audit trail.
    assert run["sandbox"] == "none"
    child_id = run["planned_child_node_id"]
    assert child_id

    # The run executes in a background asyncio task (supervisor). Poll the
    # graph until the child appears. Each TestClient call yields to the loop.
    deadline_polls = 50
    final_run = run
    for _ in range(deadline_polls):
        final_run = client.get(f"/projects/{project_id}/runs/{run['id']}").json()
        if final_run["status"] in {"succeeded", "failed", "cancelled"}:
            break
    assert final_run["status"] == "succeeded", final_run

    # Graph now has 2 nodes; child has the root as a parent.
    graph2 = client.get(f"/projects/{project_id}/graph").json()
    assert len(graph2["nodes"]) == 2, graph2
    child = next(n for n in graph2["nodes"] if n["id"] == child_id)
    assert child["kind"] == "prompt"
    assert root_id in child["parent_node_ids"]


def test_artifacts_list_and_fetch(client: TestClient, repo: Path) -> None:
    """The full prompt flow records at least a runtime transcript artifact;
    the listing + content endpoints surface it for the frontend."""
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    root = client.post(f"/projects/{project_id}/nodes/root").json()
    run = client.post(
        f"/projects/{project_id}/nodes/{root['id']}/runs/prompt",
        json={"prompt": "artifact probe"},
    ).json()
    # Wait for the run to complete (artifact is recorded on success).
    final_run = run
    for _ in range(80):
        final_run = client.get(f"/projects/{project_id}/runs/{run['id']}").json()
        if final_run["status"] in {"succeeded", "failed", "cancelled"}:
            break
    assert final_run["status"] == "succeeded"

    listed = client.get(f"/projects/{project_id}/artifacts")
    assert listed.status_code == 200
    artifacts = listed.json()["artifacts"]
    transcripts = [a for a in artifacts if a["kind"] == "runtime_transcript"]
    assert transcripts, f"expected at least one transcript artifact, got: {artifacts}"

    # Filtering by run_id narrows the result.
    by_run = client.get(
        f"/projects/{project_id}/artifacts",
        params={"run_id": final_run["id"]},
    ).json()["artifacts"]
    assert by_run and all(a["run_id"] == final_run["id"] for a in by_run)

    # Single fetch returns the same shape.
    single = client.get(
        f"/projects/{project_id}/artifacts/{transcripts[0]['id']}"
    ).json()
    assert single["id"] == transcripts[0]["id"]

    # Content streaming returns the actual file bytes.
    content = client.get(
        f"/projects/{project_id}/artifacts/{transcripts[0]['id']}/content"
    )
    assert content.status_code == 200
    # Noop runtime transcript shape: USER:/ASSISTANT: lines.
    assert "USER:" in content.text or "ASSISTANT:" in content.text


def test_unknown_artifact_returns_404(client: TestClient, repo: Path) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    r = client.get(
        f"/projects/{project_id}/artifacts/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_unknown_project_returns_404(client: TestClient) -> None:
    r = client.get("/projects/00000000-0000-0000-0000-000000000000/graph")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_unknown_node_returns_404(client: TestClient, repo: Path) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    r = client.get(
        f"/projects/{project_id}/nodes/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NODE_NOT_FOUND"


def test_unknown_snapshot_returns_404(client: TestClient, repo: Path) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    r = client.get(
        f"/projects/{project_id}/code-snapshots/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SNAPSHOT_NOT_FOUND"


def test_context_diff_endpoint_returns_section_diff(
    client: TestClient, repo: Path
) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    root = client.post(f"/projects/{project_id}/nodes/root").json()

    # Drive a prompt run so the daemon's noop runtime produces a child snapshot
    # whose context differs from the root's (added goal + handoff_note).
    prompt_run = client.post(
        f"/projects/{project_id}/nodes/{root['id']}/runs/prompt",
        json={"prompt": "context-diff probe"},
    )
    assert prompt_run.status_code == 201, prompt_run.text

    # Poll the graph until the child node materialises (run runs async).
    child_id: str | None = None
    for _ in range(80):
        graph = client.get(f"/projects/{project_id}/graph").json()
        for node in graph["nodes"]:
            if node["kind"] == "prompt":
                child_id = node["id"]
                break
        if child_id is not None:
            break
        import time

        time.sleep(0.05)
    assert child_id is not None, "child node never appeared"

    diff = client.get(f"/projects/{project_id}/nodes/{child_id}/context-diff")
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["node_id"] == child_id
    assert body["base_snapshot_id"] is not None
    sections = {section["section"]: section for section in body["sections"]}
    # Goals gets the user prompt as a new item; handoff_notes gets the handoff
    # note. Both should report at least one addition.
    assert sections["goals"]["additions"] >= 1
    assert sections["handoff_notes"]["additions"] >= 1
    assert body["totals"]["additions"] == sum(
        section["additions"] for section in body["sections"]
    )


def test_merge_same_node_is_422(client: TestClient, repo: Path) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    root = client.post(f"/projects/{project_id}/nodes/root").json()
    r = client.post(
        f"/projects/{project_id}/merges",
        json={"source_node_id": root["id"], "target_node_id": root["id"]},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "MERGE_INVALID_NODES"
