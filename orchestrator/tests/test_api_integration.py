"""HTTP-level integration tests against the FastAPI app.

These complement the in-process unit tests in test_prompt_run.py /
test_orchestrator_service.py / test_merge_flow.py / etc. by exercising
the routing layer, response schemas, and error handlers end-to-end with
the same shapes the frontend consumes.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from agentsofchaos_orchestrator.api.app import create_app
from agentsofchaos_orchestrator.domain.enums import RuntimeCapability, RuntimeKind
from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.runtime import (
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from tests.helpers import initialize_test_repository


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_path = tmp_path / "api-int.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_backend=RuntimeKind.NOOP,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    return repository_root


class ApiConflictRuntimeAdapter:
    def __init__(
        self,
        *,
        resolve_conflict: bool,
        leave_unmerged_index: bool = False,
        fail_resolution: bool = False,
    ) -> None:
        self._resolve_conflict = resolve_conflict
        self._leave_unmerged_index = leave_unmerged_index
        self._fail_resolution = fail_resolution

    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.CUSTOM

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        if "You are resolving an Agents of Chaos conflicted merge node." in request.prompt:
            if self._fail_resolution:
                raise RuntimeExecutionError("simulated resolution runtime failure")
            if self._resolve_conflict:
                (request.worktree_path / "conflict.txt").write_text(
                    "resolved by api runtime\n",
                    encoding="utf-8",
                )
            if self._leave_unmerged_index:
                _force_unmerged_index_entry(request.worktree_path, "conflict.txt")
            return RuntimeExecutionResult(
                transcript_text="USER: resolve\nASSISTANT: attempted resolution\n",
                summary_text="Attempted merge resolution",
            )

        file_name, content = request.prompt.split(":", maxsplit=1)
        (request.worktree_path / file_name).write_text(content, encoding="utf-8")
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: wrote {file_name}\n",
            summary_text=f"Wrote {file_name}",
        )


def _git_hash_object(worktree_path: Path, content: str) -> str:
    completed = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=worktree_path,
        input=content,
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _force_unmerged_index_entry(worktree_path: Path, relative_path: str) -> None:
    ancestor = _git_hash_object(worktree_path, "ancestor\n")
    ours = _git_hash_object(worktree_path, "ours\n")
    theirs = _git_hash_object(worktree_path, "theirs\n")
    index_info = "".join(
        (
            f"0 {'0' * 40}\t{relative_path}\n",
            f"100644 {ancestor} 1\t{relative_path}\n",
            f"100644 {ours} 2\t{relative_path}\n",
            f"100644 {theirs} 3\t{relative_path}\n",
        )
    )
    subprocess.run(
        ["git", "update-index", "--index-info"],
        cwd=worktree_path,
        input=index_info,
        text=True,
        check=True,
        capture_output=True,
    )


def make_client_with_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime: ApiConflictRuntimeAdapter,
) -> TestClient:
    db_path = tmp_path / "api-runtime.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_backend=RuntimeKind.CUSTOM,
    )
    monkeypatch.setattr(
        "agentsofchaos_orchestrator.api.app.build_runtime_adapter",
        lambda _settings, *, sandbox: runtime,
    )
    return TestClient(create_app(settings))


def response_json_object(response: Response) -> dict[str, object]:
    body = response.json()
    assert isinstance(body, dict)
    return {str(key): value for key, value in body.items()}


def wait_for_run_terminal(client: TestClient, project_id: str, run_id: str) -> dict[str, object]:
    final_run: dict[str, object] | None = None
    for _ in range(100):
        final_run = response_json_object(client.get(f"/projects/{project_id}/runs/{run_id}"))
        if final_run["status"] in {"succeeded", "failed", "cancelled"}:
            return final_run
    raise AssertionError(f"run did not reach terminal status: {final_run}")


def create_merge_from_prompt_writes(
    client: TestClient,
    project_id: str,
    root_id: str,
    *,
    source_prompt: str,
    target_prompt: str,
    expected_status: str,
) -> dict[str, object]:
    source_response = client.post(
        f"/projects/{project_id}/nodes/{root_id}/runs/prompt",
        json={"prompt": source_prompt},
    )
    source_run = response_json_object(source_response)
    source_run = wait_for_run_terminal(client, project_id, str(source_run["id"]))
    assert source_run["status"] == "succeeded", source_run

    target_response = client.post(
        f"/projects/{project_id}/nodes/{root_id}/runs/prompt",
        json={"prompt": target_prompt},
    )
    target_run = response_json_object(target_response)
    target_run = wait_for_run_terminal(client, project_id, str(target_run["id"]))
    assert target_run["status"] == "succeeded", target_run

    merge = client.post(
        f"/projects/{project_id}/merges",
        json={
            "source_node_id": source_run["planned_child_node_id"],
            "target_node_id": target_run["planned_child_node_id"],
        },
    )
    assert merge.status_code == 201, merge.text
    body = response_json_object(merge)
    node = response_json_object_value(body["node"])
    assert node["status"] == expected_status, body
    return body


def create_conflicted_merge(client: TestClient, project_id: str, root_id: str) -> dict[str, object]:
    return create_merge_from_prompt_writes(
        client,
        project_id,
        root_id,
        source_prompt="conflict.txt:source",
        target_prompt="conflict.txt:target",
        expected_status="code_conflicted",
    )


def create_clean_merge(client: TestClient, project_id: str, root_id: str) -> dict[str, object]:
    return create_merge_from_prompt_writes(
        client,
        project_id,
        root_id,
        source_prompt="source.txt:source",
        target_prompt="target.txt:target",
        expected_status="ready",
    )


def response_json_object_value(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def assert_no_resolution_node_or_report(client: TestClient, project_id: str) -> None:
    graph = response_json_object(client.get(f"/projects/{project_id}/graph"))
    graph_nodes = graph["nodes"]
    assert isinstance(graph_nodes, list)
    assert not [
        node
        for node in graph_nodes
        if response_json_object_value(node)["kind"] == "resolution"
    ]

    artifacts_body = response_json_object(client.get(f"/projects/{project_id}/artifacts"))
    artifacts = artifacts_body["artifacts"]
    assert isinstance(artifacts, list)
    assert not [
        artifact
        for artifact in artifacts
        if response_json_object_value(artifact)["kind"] == "resolution_report"
    ]


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "Orchestrator" in body["app_name"]


def test_health_sandbox_reports_ok_for_default_none_backend(
    client: TestClient,
) -> None:
    """The default sandbox backend (`none`) is always usable — it just
    spawns processes directly. `/health/sandbox` must say so."""
    r = client.get("/health/sandbox")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "none"
    assert body["status"] == "ok"
    assert body["detail"] is None


def test_health_runtime_reports_ok_for_noop_backend(client: TestClient) -> None:
    """The noop runtime has no host dependencies — `/health/runtime`
    must report ok in the default fixture."""
    r = client.get("/health/runtime")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "noop"
    assert body["status"] == "ok"
    assert body["detail"] is None


def test_health_runtime_reports_unavailable_when_pi_binary_missing(
    tmp_path: Path,
) -> None:
    """When the configured runtime can't run on this host the endpoint
    surfaces a specific, operator-actionable error in the `detail`
    field — a 200 body with `status=unavailable`, not a 5xx, so
    monitoring can poll it without confusing transport errors with
    diagnostic state.
    """
    db_path = tmp_path / "api-int.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_backend=RuntimeKind.PI,
        # An absolute path that doesn't exist — pi probe will fail
        # cleanly with the configured-path message.
        pi_binary=str(tmp_path / "no-such-pi-binary"),
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        r = test_client.get("/health/runtime")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "pi"
    assert body["status"] == "unavailable"
    assert "no-such-pi-binary" in body["detail"]


def test_open_project_is_idempotent(client: TestClient, repo: Path) -> None:
    first = client.post("/projects/open", json={"path": str(repo)})
    assert first.status_code == 201, first.text
    project_id = first.json()["id"]

    second = client.post("/projects/open", json={"path": str(repo)})
    assert second.status_code == 201
    assert second.json()["id"] == project_id, (
        "re-opening the same path must return the same project id"
    )


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

    # Opening a project now creates the immutable root automatically.
    graph0 = client.get(f"/projects/{project_id}/graph").json()
    assert len(graph0["nodes"]) == 1
    root = graph0["nodes"][0]
    assert root["kind"] == "root"
    assert root["status"] == "ready"
    assert root["parent_node_ids"] == []
    root_id = root["id"]

    # The legacy explicit endpoint remains idempotent for old UI callers.
    root_r = client.post(f"/projects/{project_id}/nodes/root")
    assert root_r.status_code == 201, root_r.text
    assert root_r.json()["id"] == root_id

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


def test_resolution_run_endpoint_creates_successor_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(resolve_conflict=True),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])

        resolution = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Resolve the conflict with the target behavior."},
        )
        assert resolution.status_code == 201, resolution.text
        resolution_run = response_json_object(resolution)
        assert resolution_run["source_node_id"] == merge_node_id
        final_run = wait_for_run_terminal(custom_client, project_id, str(resolution_run["id"]))
        assert final_run["status"] == "succeeded", final_run

        graph = response_json_object(custom_client.get(f"/projects/{project_id}/graph"))
        graph_nodes = graph["nodes"]
        assert isinstance(graph_nodes, list)
        resolution_nodes = [
            response_json_object_value(node)
            for node in graph_nodes
            if response_json_object_value(node)["kind"] == "resolution"
        ]
        assert len(resolution_nodes) == 1, graph
        resolution_node = resolution_nodes[0]
        assert resolution_node["parent_node_ids"] == [merge_node_id]
        assert resolution_node["status"] == "ready"

        artifacts_body = response_json_object(
            custom_client.get(
                f"/projects/{project_id}/artifacts",
                params={"node_id": str(resolution_node["id"])},
            )
        )
        artifacts = artifacts_body["artifacts"]
        assert isinstance(artifacts, list)
        reports = [
            response_json_object_value(artifact)
            for artifact in artifacts
            if response_json_object_value(artifact)["kind"] == "resolution_report"
        ]
        assert reports, artifacts
        report = custom_client.get(
            f"/projects/{project_id}/artifacts/{reports[0]['id']}/content"
        )
        assert report.status_code == 200, report.text
        report_body = response_json_object(report)
        assert report_body["conflicted_merge_node_id"] == merge_node_id
        assert report_body["successor_node_id"] == resolution_node["id"]
        assert report_body["resolution_run_id"] == final_run["id"]
        assert report_body["validated"] is True
        assert isinstance(report_body["source_merge_report_artifact_id"], str)
        assert isinstance(report_body["runtime_transcript_artifact_id"], str)
        assert report_body["runtime_transcript_artifact_id"] != reports[0]["id"]

        all_artifacts_body = response_json_object(
            custom_client.get(f"/projects/{project_id}/artifacts")
        )
        all_artifacts = all_artifacts_body["artifacts"]
        assert isinstance(all_artifacts, list)
        all_artifact_ids = {
            response_json_object_value(artifact)["id"] for artifact in all_artifacts
        }
        assert report_body["source_merge_report_artifact_id"] in all_artifact_ids
        assert report_body["runtime_transcript_artifact_id"] in all_artifact_ids


def test_resolution_run_endpoint_rejects_non_merge_node(
    client: TestClient,
    repo: Path,
) -> None:
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    root = client.post(f"/projects/{project_id}/nodes/root").json()
    response = client.post(
        f"/projects/{project_id}/merges/{root['id']}/resolution-runs/prompt",
        json={"prompt": "Resolve this."},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MERGE_INVALID_NODES"


def test_resolution_run_endpoint_rejects_non_conflicted_merge_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(resolve_conflict=True),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_clean_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])

        response = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node['id']}/resolution-runs/prompt",
            json={"prompt": "Resolve this clean merge."},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "MERGE_INVALID_NODES"


def test_resolution_run_endpoint_rejects_missing_merge_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(resolve_conflict=True),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])
        report_path = repo / ".aoc" / "artifacts" / f"merge-report-{merge_node_id}.json"
        report_path.unlink()

        response = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Resolve this."},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MERGE_ANCESTOR_ERROR"


def test_resolution_run_endpoint_rejects_invalid_merge_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(resolve_conflict=True),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])
        report_path = repo / ".aoc" / "artifacts" / f"merge-report-{merge_node_id}.json"
        report_path.write_text("[]", encoding="utf-8")

        response = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Resolve this."},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MERGE_ANCESTOR_ERROR"


def test_resolution_run_fails_when_agent_leaves_conflict_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(resolve_conflict=False),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])

        resolution = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Try resolving but leave the file unchanged."},
        )
        assert resolution.status_code == 201, resolution.text
        resolution_run = response_json_object(resolution)
        final_run = wait_for_run_terminal(custom_client, project_id, str(resolution_run["id"]))

        assert final_run["status"] == "failed", final_run
        error_message = final_run["error_message"]
        assert isinstance(error_message, str)
        assert "conflict markers" in error_message
        assert_no_resolution_node_or_report(custom_client, project_id)


def test_resolution_run_fails_when_agent_leaves_unmerged_index_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(
            resolve_conflict=True,
            leave_unmerged_index=True,
        ),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])

        resolution = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Resolve text but forget to clear the git index."},
        )
        assert resolution.status_code == 201, resolution.text
        resolution_run = response_json_object(resolution)
        final_run = wait_for_run_terminal(custom_client, project_id, str(resolution_run["id"]))

        assert final_run["status"] == "failed", final_run
        error_message = final_run["error_message"]
        assert isinstance(error_message, str)
        assert "unmerged git index entries" in error_message
        assert_no_resolution_node_or_report(custom_client, project_id)


def test_resolution_run_fails_when_runtime_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> None:
    with make_client_with_runtime(
        tmp_path,
        monkeypatch,
        ApiConflictRuntimeAdapter(
            resolve_conflict=False,
            fail_resolution=True,
        ),
    ) as custom_client:
        opened = response_json_object(
            custom_client.post("/projects/open", json={"path": str(repo)})
        )
        project_id = str(opened["id"])
        root = response_json_object(custom_client.post(f"/projects/{project_id}/nodes/root"))
        merge = create_conflicted_merge(custom_client, project_id, str(root["id"]))
        merge_node = response_json_object_value(merge["node"])
        merge_node_id = str(merge_node["id"])

        resolution = custom_client.post(
            f"/projects/{project_id}/merges/{merge_node_id}/resolution-runs/prompt",
            json={"prompt": "Try resolving."},
        )
        assert resolution.status_code == 201, resolution.text
        resolution_run = response_json_object(resolution)
        final_run = wait_for_run_terminal(custom_client, project_id, str(resolution_run["id"]))

        assert final_run["status"] == "failed", final_run
        error_message = final_run["error_message"]
        assert isinstance(error_message, str)
        assert "simulated resolution runtime failure" in error_message
        assert_no_resolution_node_or_report(custom_client, project_id)


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




def test_node_file_content_endpoint_returns_raw_bytes(
    client: TestClient, repo: Path
) -> None:
    """`GET /nodes/{id}/files/{path}/content` reads bytes from git at
    the node's commit and returns them as a download. README.md was
    seeded into the fixture repo; the root node's snapshot should
    have it verbatim.
    """
    project_id = client.post("/projects/open", json={"path": str(repo)}).json()["id"]
    root = client.get(f"/projects/{project_id}/graph").json()["nodes"][0]

    r = client.get(
        f"/projects/{project_id}/nodes/{root['id']}/files/README.md/content"
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert 'attachment; filename="README.md"' in r.headers["content-disposition"]
    # Fixture from initialize_test_repository seeds a README; just
    # verify we got non-empty bytes back (the helper's exact content
    # is its concern, not this test's).
    assert len(r.content) > 0
