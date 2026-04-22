from __future__ import annotations

import tempfile
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

from play_book_studio.app import server
from play_book_studio.config.settings import load_settings


class _FakeReranker:
    def __init__(self) -> None:
        self.model_name = "fake-reranker"
        self.warmup_calls = 0

    def warmup(self) -> bool:
        self.warmup_calls += 1
        return True


class _FakeThread:
    def __init__(self, *, target, args, name, daemon) -> None:
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1


class _FakeLlmClient:
    def runtime_metadata(self) -> dict[str, object]:
        return {
            "preferred_provider": "deterministic-test",
            "fallback_enabled": False,
            "last_provider": "deterministic-test",
            "last_fallback_used": False,
            "last_attempted_providers": ["deterministic-test"],
        }


class _FakeAnswerer:
    def __init__(self, root: Path) -> None:
        self.settings = load_settings(root)
        self.llm_client = _FakeLlmClient()
        self.retriever = SimpleNamespace(reranker=None)


def _write_frontend_shell(root: Path) -> None:
    dist_dir = root / "presentation-ui" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html><body><div id='pbs-shell'>shared-shell</div></body></html>",
        encoding="utf-8",
    )


@contextmanager
def _test_server(root: Path):
    answerer = _FakeAnswerer(root)
    store = server.SessionStore(root)
    handler = server._build_handler(answerer=answerer, store=store, root_dir=root)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_start_runtime_warmup_starts_daemon_thread_when_reranker_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        answerer = SimpleNamespace(retriever=SimpleNamespace(reranker=None))
        created_threads: list[_FakeThread] = []

        def _build_thread(*, target, args, name, daemon):
            thread = _FakeThread(target=target, args=args, name=name, daemon=daemon)
            created_threads.append(thread)
            return thread

        with patch("play_book_studio.app.server.threading.Thread", side_effect=_build_thread):
            thread = server._start_runtime_warmup(answerer, root)

        assert thread is created_threads[0]
        assert thread.target is server._warmup_runtime_components
        assert thread.args == (answerer, root)
        assert thread.name == "pbs-runtime-warmup"
        assert thread.daemon is True
        assert thread.start_calls == 1


def test_start_runtime_warmup_starts_daemon_thread_when_reranker_present() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        answerer = SimpleNamespace(retriever=SimpleNamespace(reranker=_FakeReranker()))
        created_threads: list[_FakeThread] = []

        def _build_thread(*, target, args, name, daemon):
            thread = _FakeThread(target=target, args=args, name=name, daemon=daemon)
            created_threads.append(thread)
            return thread

        with patch("play_book_studio.app.server.threading.Thread", side_effect=_build_thread):
            thread = server._start_runtime_warmup(answerer, root)

        assert thread is created_threads[0]
        assert thread.target is server._warmup_runtime_components
        assert thread.args == (answerer, root)
        assert thread.name == "pbs-runtime-warmup"
        assert thread.daemon is True
        assert thread.start_calls == 1


def test_warmup_runtime_components_primes_data_control_room_and_reranker() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        reranker = _FakeReranker()
        answerer = SimpleNamespace(retriever=SimpleNamespace(reranker=reranker))

        with patch("play_book_studio.app.server.build_data_control_room_payload") as payload_mock:
            server._warmup_runtime_components(answerer, root)

        payload_mock.assert_called_once_with(root)
        assert reranker.warmup_calls == 1


def test_spa_deep_links_return_index_html_for_pbs_surfaces() -> None:
    spa_routes = (
        "/",
        "/details",
        "/studio",
        "/workspace",
        "/llmwikibook",
        "/studio-v2",
        "/playbook-library",
        "/playbook-library/control-tower",
        "/playbook-library/repository",
        "/ops",
        "/ops/workspaces",
        "/ops/connections",
        "/ops/overview",
        "/ops/resources",
        "/ops/chat",
        "/ops/actions",
        "/ops/scm",
        "/ops/details",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            for route in spa_routes:
                response = requests.get(f"{base_url}{route}", timeout=10)

                assert response.status_code == 200, route
                assert response.headers["Content-Type"].startswith("text/html"), route
                assert "<!DOCTYPE html>" in response.text, route
                assert "pbs-shell" in response.text, route


def test_workspaces_api_creates_and_lists_workspace_records() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            create_response = requests.post(
                f"{base_url}/api/v1/workspaces",
                json={"name": "Demo Ops Workspace", "environment": "prod"},
                timeout=10,
            )
            list_response = requests.get(f"{base_url}/api/v1/workspaces", timeout=10)

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Demo Ops Workspace"
        assert created["environment"] == "prod"
        assert created["slug"] == "demo-ops-workspace"
        assert created["workspace_id"]

        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["count"] == 1
        assert payload["items"][0]["workspace_id"] == created["workspace_id"]


def test_ocp_connection_api_creates_lists_and_disconnects_profiles() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            create_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/connect",
                json={
                    "workspace_id": "ws-1",
                    "cluster_url": "https://api.cluster.example.com:6443",
                    "auth_mode": "token",
                    "verify_ssl": True,
                    "default_namespace": "demo",
                    "display_name": "prod-cluster",
                    "username": "developer",
                    "save_profile": True,
                },
                timeout=10,
            )
            created = create_response.json()
            connection_id = created["connection"]["connection_id"]

            list_response = requests.get(
                f"{base_url}/api/v1/auth/ocp/profiles?workspace_id=ws-1",
                timeout=10,
            )
            status_response = requests.get(
                f"{base_url}/api/v1/auth/ocp/status/{connection_id}",
                timeout=10,
            )
            disconnect_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/disconnect",
                json={"connection_id": connection_id},
                timeout=10,
            )

        assert create_response.status_code == 201
        assert created["connected"] is True
        assert created["connection"]["display_name"] == "prod-cluster"

        listed = list_response.json()
        assert list_response.status_code == 200
        assert listed["count"] == 1
        assert listed["items"][0]["connection_id"] == connection_id

        loaded = status_response.json()
        assert status_response.status_code == 200
        assert loaded["connected"] is True
        assert loaded["connection"]["cluster_url"] == "https://api.cluster.example.com:6443"

        disconnected = disconnect_response.json()
        assert disconnect_response.status_code == 200
        assert disconnected["connected"] is False


def test_ocp_overview_and_metrics_api_return_operational_payloads() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            create_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/connect",
                json={
                    "workspace_id": "ws-1",
                    "cluster_url": "https://api.cluster.example.com:6443",
                    "auth_mode": "token",
                    "verify_ssl": True,
                    "default_namespace": "demo",
                    "display_name": "prod-cluster",
                },
                timeout=10,
            )
            connection_id = create_response.json()["connection"]["connection_id"]

            overview_response = requests.get(f"{base_url}/api/v1/ocp/overview/{connection_id}", timeout=10)
            metrics_response = requests.get(f"{base_url}/api/v1/ocp/metrics/{connection_id}?window=1h&step=5m", timeout=10)

        assert overview_response.status_code == 200
        overview = overview_response.json()
        assert overview["connection_id"] == connection_id
        assert overview["cluster_url"] == "https://api.cluster.example.com:6443"
        assert overview["namespace_count"] >= 1
        assert isinstance(overview["resource_counts"], dict)

        assert metrics_response.status_code == 200
        metrics = metrics_response.json()
        assert metrics["connection_id"] == connection_id
        assert metrics["window"] == "1h"
        assert metrics["step"] == "5m"
        assert len(metrics["series"]) == 3


def test_ocp_resource_api_returns_namespaces_list_and_manifest_detail() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            create_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/connect",
                json={
                    "workspace_id": "ws-1",
                    "cluster_url": "https://api.cluster.example.com:6443",
                    "auth_mode": "token",
                    "verify_ssl": True,
                    "default_namespace": "demo",
                    "display_name": "prod-cluster",
                },
                timeout=10,
            )
            connection_id = create_response.json()["connection"]["connection_id"]

            namespaces_response = requests.get(f"{base_url}/api/v1/ocp/namespaces/{connection_id}", timeout=10)
            resources_response = requests.get(
                f"{base_url}/api/v1/ocp/resources/{connection_id}?resource=pods&namespace=demo",
                timeout=10,
            )
            resource_name = resources_response.json()["items"][0]["name"]
            detail_response = requests.get(
                f"{base_url}/api/v1/ocp/resource-detail/{connection_id}?resource=pods&namespace=demo&name={resource_name}",
                timeout=10,
            )

        assert namespaces_response.status_code == 200
        namespaces = namespaces_response.json()
        assert namespaces["connection_id"] == connection_id
        assert "demo" in namespaces["items"]

        assert resources_response.status_code == 200
        resources = resources_response.json()
        assert resources["resource"] == "pods"
        assert resources["namespace"] == "demo"
        assert resources["count"] >= 1

        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["name"] == resource_name
        assert detail["namespace"] == "demo"
        assert "metadata" in detail["manifest_yaml"]


def test_ops_chat_api_returns_operational_answer_and_resource_items() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            create_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/connect",
                json={
                    "workspace_id": "ws-1",
                    "cluster_url": "https://api.cluster.example.com:6443",
                    "auth_mode": "token",
                    "verify_ssl": True,
                    "default_namespace": "demo",
                    "display_name": "prod-cluster",
                },
                timeout=10,
            )
            connection_id = create_response.json()["connection"]["connection_id"]

            chat_response = requests.post(
                f"{base_url}/api/v1/ops/chat",
                json={
                    "connection_id": connection_id,
                    "message": "demo namespace의 pod 보여줘",
                    "namespace": "demo",
                    "history": [],
                },
                timeout=10,
            )

        assert chat_response.status_code == 200
        payload = chat_response.json()
        assert payload["connection_id"] == connection_id
        assert payload["mode"] in {"resource_list", "resource_detail", "namespace_list"}
        assert payload["namespace"] == "demo"
        assert isinstance(payload["answer"], str)
        assert payload["items"]


def test_actions_api_supports_preview_request_approval_execution_and_audit() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            connection_response = requests.post(
                f"{base_url}/api/v1/auth/ocp/connect",
                json={
                    "workspace_id": "ws-1",
                    "cluster_url": "https://api.cluster.example.com:6443",
                    "auth_mode": "token",
                    "verify_ssl": True,
                    "default_namespace": "openshift-monitoring",
                    "display_name": "prod-cluster",
                },
                timeout=10,
            )
            connection_id = connection_response.json()["connection"]["connection_id"]

            preview_response = requests.post(
                f"{base_url}/api/v1/actions/preview",
                json={
                    "connection_id": connection_id,
                    "actor_id": "ui-local",
                    "actor_roles": ["operator"],
                    "action_type": "scale_deployment",
                    "namespace": "openshift-monitoring",
                    "resource_name": "ops-deployment-01",
                    "replicas": 3,
                    "reason": "Need more capacity",
                },
                timeout=10,
            )

            request_response = requests.post(
                f"{base_url}/api/v1/actions/requests",
                json={
                    "connection_id": connection_id,
                    "actor_id": "ui-local",
                    "actor_roles": ["operator"],
                    "action_type": "scale_deployment",
                    "namespace": "openshift-monitoring",
                    "resource_name": "ops-deployment-01",
                    "replicas": 3,
                    "reason": "Need more capacity",
                },
                timeout=10,
            )
            request_id = request_response.json()["request_id"]

            approve_response = requests.post(
                f"{base_url}/api/v1/actions/requests/{request_id}/approve",
                json={"actor_id": "approver-1", "actor_roles": ["operator"], "decision_note": "approved"},
                timeout=10,
            )
            execute_response = requests.post(
                f"{base_url}/api/v1/actions/requests/{request_id}/execute",
                json={"actor_id": "executor-1", "actor_roles": ["operator"], "force": False},
                timeout=10,
            )
            requests_response = requests.get(f"{base_url}/api/v1/actions/requests?limit=20", timeout=10)
            executions_response = requests.get(f"{base_url}/api/v1/actions/executions?limit=20", timeout=10)
            audit_response = requests.get(f"{base_url}/api/v1/actions/audit?limit=20", timeout=10)

        assert preview_response.status_code == 200
        preview = preview_response.json()
        assert preview["action_type"] == "scale_deployment"
        assert preview["resource_name"] == "ops-deployment-01"

        assert request_response.status_code == 201
        created_request = request_response.json()
        assert created_request["status"] == "pending"

        assert approve_response.status_code == 200
        approved = approve_response.json()
        assert approved["status"] in {"pending", "approved"}

        assert execute_response.status_code == 200
        execution = execute_response.json()
        assert execution["status"] == "completed"

        assert requests_response.status_code == 200
        assert requests_response.json()["items"]

        assert executions_response.status_code == 200
        assert executions_response.json()["items"]

        assert audit_response.status_code == 200
        assert audit_response.json()["items"]


def test_scm_api_supports_oauth_connection_repository_and_deployment_plan() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            workspace_response = requests.post(
                f"{base_url}/api/v1/workspaces",
                json={"name": "SCM Workspace", "environment": "prod"},
                timeout=10,
            )
            workspace_id = workspace_response.json()["workspace_id"]

            oauth_response = requests.post(
                f"{base_url}/api/v1/oauth/github/start?workspace_id={workspace_id}",
                timeout=10,
            )

            manual_connection_response = requests.post(
                f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections",
                json={
                    "provider": "gitlab",
                    "host_url": "https://gitlab.example.com",
                    "auth_type": "token",
                    "account_label": "team-gitlab",
                },
                timeout=10,
            )
            scm_connection_id = manual_connection_response.json()["scm_connection_id"]

            repository_response = requests.post(
                f"{base_url}/api/v1/workspaces/{workspace_id}/scm/repositories",
                json={
                    "scm_connection_id": scm_connection_id,
                    "repo_full_name": "team/demo-repo",
                    "default_branch": "main",
                    "config_path": "deploy/config.yaml",
                    "delivery_mode": "gitops_commit",
                    "manifest_kind": "config_yaml",
                    "target_cluster_url": "https://api.cluster.example.com:6443",
                    "target_namespace": "openshift-monitoring",
                    "auto_deploy_enabled": True,
                },
                timeout=10,
            )
            repository_id = repository_response.json()["repository_id"]

            list_connections_response = requests.get(
                f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections",
                timeout=10,
            )
            list_repositories_response = requests.get(
                f"{base_url}/api/v1/workspaces/{workspace_id}/scm/repositories",
                timeout=10,
            )
            plan_response = requests.post(
                f"{base_url}/api/v1/workspaces/{workspace_id}/scm/repositories/{repository_id}/deployment-plan",
                json={
                    "resource_kind": "Deployment",
                    "resource_name": "ops-deployment-01",
                    "target_namespace": "openshift-monitoring",
                    "replicas": 3,
                    "image_tag": "v2.0.0",
                    "config_key": "replicas",
                    "reason": "Synthetic deployment update",
                },
                timeout=10,
            )

        assert oauth_response.status_code == 200
        oauth_payload = oauth_response.json()
        assert oauth_payload["provider"] == "github"
        assert "oauth_status=connected" in oauth_payload["authorize_url"]

        assert manual_connection_response.status_code == 201
        assert manual_connection_response.json()["provider"] == "gitlab"

        assert repository_response.status_code == 201
        assert repository_response.json()["repo_full_name"] == "team/demo-repo"

        assert list_connections_response.status_code == 200
        assert list_connections_response.json()["items"]

        assert list_repositories_response.status_code == 200
        assert list_repositories_response.json()["items"]

        assert plan_response.status_code == 200
        plan = plan_response.json()
        assert plan["repo_full_name"] == "team/demo-repo"
        assert plan["trigger_kind"] in {"gitops_sync", "cicd_pipeline"}
        assert plan["suggested_updates"]


def test_scm_repository_discovery_returns_provider_repositories() -> None:
    class _FakeResponse:
        def __init__(self, payload, status_code=200) -> None:
            self._payload = payload
            self.status_code = status_code
            self.content = b"{}"

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)
        (root / ".env").write_text("GITHUB_CLASSIC_TOKEN=fake-token\n", encoding="utf-8")
        real_requests_get = requests.get

        def _fake_get(url, headers=None, params=None, timeout=None):  # noqa: ARG001
            if url == "https://api.github.com/user/repos":
                return _FakeResponse(
                    [
                        {
                            "id": 1,
                            "full_name": "team/repo-one",
                            "name": "repo-one",
                            "default_branch": "main",
                            "html_url": "https://github.com/team/repo-one",
                            "private": True,
                        },
                        {
                            "id": 2,
                            "full_name": "team/repo-two",
                            "name": "repo-two",
                            "default_branch": "dev",
                            "html_url": "https://github.com/team/repo-two",
                            "private": False,
                        },
                    ]
                )
            return real_requests_get(url, headers=headers, params=params, timeout=timeout)

        with patch("play_book_studio.app.scm_store.requests.get", side_effect=_fake_get):
            with _test_server(root) as base_url:
                workspace_response = requests.post(
                    f"{base_url}/api/v1/workspaces",
                    json={"name": "Discovery Workspace", "environment": "dev"},
                    timeout=10,
                )
                workspace_id = workspace_response.json()["workspace_id"]
                connection_response = requests.post(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections",
                    json={
                        "provider": "github",
                        "host_url": "https://github.com",
                        "auth_type": "token",
                        "account_label": "team-gh",
                    },
                    timeout=10,
                )
                connection_id = connection_response.json()["scm_connection_id"]
                discover_response = requests.get(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections/{connection_id}/discover-repositories?query=repo",
                    timeout=10,
                )

        assert discover_response.status_code == 200
        payload = discover_response.json()
        assert len(payload["items"]) == 2
        assert payload["items"][0]["full_name"] == "team/repo-one"


def test_scm_config_path_discovery_returns_ranked_candidates() -> None:
    class _FakeResponse:
        def __init__(self, payload, status_code=200) -> None:
            self._payload = payload
            self.status_code = status_code
            self.content = b"{}"

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)
        (root / ".env").write_text("GITHUB_CLASSIC_TOKEN=fake-token\n", encoding="utf-8")
        real_requests_get = requests.get

        def _fake_get(url, headers=None, params=None, timeout=None):  # noqa: ARG001
            if url == "https://api.github.com/repos/team/repo-one/git/trees/main":
                return _FakeResponse(
                    {
                        "tree": [
                            {"path": "config.yaml", "type": "blob"},
                            {"path": "deploy/values.yaml", "type": "blob"},
                            {"path": "kustomize/overlays/prod/kustomization.yaml", "type": "blob"},
                        ]
                    }
                )
            return real_requests_get(url, headers=headers, params=params, timeout=timeout)

        with patch("play_book_studio.app.scm_store.requests.get", side_effect=_fake_get):
            with _test_server(root) as base_url:
                workspace_response = requests.post(
                    f"{base_url}/api/v1/workspaces",
                    json={"name": "Config Discovery Workspace", "environment": "dev"},
                    timeout=10,
                )
                workspace_id = workspace_response.json()["workspace_id"]
                connection_response = requests.post(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections",
                    json={
                        "provider": "github",
                        "host_url": "https://github.com",
                        "auth_type": "token",
                        "account_label": "team-gh",
                    },
                    timeout=10,
                )
                connection_id = connection_response.json()["scm_connection_id"]
                discover_response = requests.get(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections/{connection_id}/discover-config-paths?repo_full_name=team/repo-one&ref=main",
                    timeout=10,
                )

        assert discover_response.status_code == 200
        payload = discover_response.json()
        assert payload["items"]
        assert payload["items"][0]["path"] == "config.yaml"
        assert payload["items"][0]["manifest_kind"] == "config_yaml"


def test_scm_config_file_preview_returns_decoded_content() -> None:
    class _FakeResponse:
        def __init__(self, payload, status_code=200) -> None:
            self._payload = payload
            self.status_code = status_code
            self.content = b"{}"

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)
        (root / ".env").write_text("GITHUB_CLASSIC_TOKEN=fake-token\n", encoding="utf-8")
        real_requests_get = requests.get

        def _fake_get(url, headers=None, params=None, timeout=None):  # noqa: ARG001
            if url == "https://api.github.com/repos/team/repo-one/contents/config.yaml":
                return _FakeResponse(
                    {
                        "content": "cmVwbGljYXM6IDMK",
                        "encoding": "base64",
                    }
                )
            return real_requests_get(url, headers=headers, params=params, timeout=timeout)

        with patch("play_book_studio.app.scm_store.requests.get", side_effect=_fake_get):
            with _test_server(root) as base_url:
                workspace_response = requests.post(
                    f"{base_url}/api/v1/workspaces",
                    json={"name": "Preview Workspace", "environment": "dev"},
                    timeout=10,
                )
                workspace_id = workspace_response.json()["workspace_id"]
                connection_response = requests.post(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections",
                    json={
                        "provider": "github",
                        "host_url": "https://github.com",
                        "auth_type": "token",
                        "account_label": "team-gh",
                    },
                    timeout=10,
                )
                connection_id = connection_response.json()["scm_connection_id"]
                preview_response = requests.get(
                    f"{base_url}/api/v1/workspaces/{workspace_id}/scm/connections/{connection_id}/preview-config-file?repo_full_name=team/repo-one&path=config.yaml&ref=main",
                    timeout=10,
                )

        assert preview_response.status_code == 200
        payload = preview_response.json()
        assert payload["path"] == "config.yaml"
        assert payload["content"] == "replicas: 3\n"


def test_runtime_namespaces_resolve_viewer_html_instead_of_shared_spa_shell() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_frontend_shell(root)

        with _test_server(root) as base_url:
            response = requests.get(f"{base_url}/wiki/entities/etcd/index.html", timeout=10)

        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/html")
        assert "OCP 출처 뷰어" in response.text
        assert "pbs-shell" not in response.text
