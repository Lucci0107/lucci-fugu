"""API の軽量テスト。"""

from fastapi.testclient import TestClient

from main import app
from app.schemas import RunRequest
from app.costs import estimate_usd
from app.workflow import _xai_citations, _xai_response_text


def test_health_returns_json() -> None:
    """死活監視エンドポイントは JSON を返す。"""
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == "ok"


def test_custom_template_agents_are_accepted() -> None:
    """カスタムテンプレートの担当設定をAPI入力として受け付ける。"""
    request = RunRequest(
        goal="メルマガを作る",
        brief="個人事業主向けの週刊メルマガ原稿を作りたい。",
        agents=[
            {
                "role": "企画",
                "provider": "xai",
                "instructions": "読者に役立つ企画案を3つ作る。",
            }
        ],
    )
    assert request.agents[0].role == "企画"
    assert request.agents[0].provider == "xai"


def test_model_overrides_and_xai_search_are_accepted() -> None:
    """長文用SonnetとGrok検索設定をAPI入力として受け付ける。"""
    request = RunRequest(
        brief="重要なnote記事を、最新の事例も含めて作りたい。",
        model_overrides={"記事執筆": "claude-sonnet-4-5-20250929"},
        xai_live_search=True,
    )
    assert request.model_overrides["記事執筆"] == "claude-sonnet-4-5-20250929"
    assert request.xai_live_search is True


def test_estimate_usd_uses_model_token_prices() -> None:
    """既知モデルはトークン数から概算料金を算出する。"""
    assert estimate_usd("gpt-5.4-mini", 1_000_000, 1_000_000) == 5.25
    assert estimate_usd("unknown-model", 100, 100) is None


def test_xai_responses_output_and_citations_are_normalized() -> None:
    """Grok Responses APIの本文と参照URLを画面表示向けに整形する。"""
    payload = {
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "最新の要約です。"}]}],
        "citations": [{"url": "https://example.com/a"}, {"url": "https://example.com/a"}, {"url": "https://example.com/b"}],
    }
    assert _xai_response_text(payload) == "最新の要約です。"
    assert _xai_citations(payload) == ["https://example.com/a", "https://example.com/b"]


def test_costs_returns_json() -> None:
    """概算料金の集計エンドポイントはJSONを返す。"""
    response = TestClient(app).get("/api/costs")
    assert response.status_code == 200
    assert response.json()["label"] == "概算"


def test_health_reports_missing_openai_key(monkeypatch) -> None:
    """接続表示は実際の設定有無と一致する。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert TestClient(app).get("/health").json()["providers"]["openai"] is False


def test_public_app_requires_credentials(monkeypatch) -> None:
    """画面・API・静的ファイルは認証なしでは利用できない。"""
    monkeypatch.setenv("APP_PASSWORD", "qa-password")
    monkeypatch.setenv("APP_USERNAME", "qa-user")
    with TestClient(app) as client:
        for path in ("/", "/static/app.js", "/api/user-settings", "/api/costs", "/docs"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["detail"] == "認証が必要です。"
        assert client.post("/api/runs", json={"brief": "検証用の依頼本文です。"}).status_code == 401
        assert client.put("/api/user-settings", json={}).status_code == 401
        assert client.get("/", auth=("qa-user", "wrong-password")).status_code == 401
        assert client.get("/", auth=("qa-user", "qa-password")).status_code == 200
        assert client.get("/health").status_code == 200


def test_render_without_password_fails_closed(monkeypatch) -> None:
    """Renderで認証設定が欠けてもAI実行を公開しない。"""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/user-settings").status_code == 503
        assert client.get("/health").status_code == 200


def test_invalid_run_does_not_start_generation(monkeypatch) -> None:
    """短すぎる依頼は実行前に拒否する。"""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    response = TestClient(app).post("/api/runs", json={"brief": "短文"})
    assert response.status_code == 422


def test_settings_persist_without_touching_user_data(monkeypatch, tmp_path) -> None:
    """n8nとテンプレート設定を独立した保存先で往復確認する。"""
    from app import user_settings

    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setattr(user_settings, "SETTINGS_PATH", tmp_path / "settings.json")
    with TestClient(app) as client:
        assert client.get("/api/user-settings").json() == {}
        saved = {"n8n_enabled": True, "custom_templates": [{"id": "qa-template"}]}
        assert client.put("/api/user-settings", json=saved).json() == saved
        assert client.get("/api/user-settings").json() == saved
