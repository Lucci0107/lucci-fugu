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
