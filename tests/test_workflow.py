"""外部APIへ送信せずに引き継ぎ・料金・エラー処理を検証する。"""

import asyncio
from types import SimpleNamespace

from app import costs, workflow
from app.schemas import RunRequest


def test_team_passes_outputs_to_next_role_and_n8n(monkeypatch, tmp_path):
    prompts = []
    sent = []

    async def generate(provider, specialist, prompt, model, live_search):
        prompts.append(prompt)
        return workflow.GenerationResult(f"{specialist.role}の成果物", 1000, 500)

    async def send(payload):
        sent.append(payload)
        return {"sent": True, "message": "送信済み"}

    monkeypatch.setattr(workflow, "_run_specialist", generate)
    monkeypatch.setattr(workflow, "_send_to_n8n", send)
    monkeypatch.setattr(costs, "COSTS_PATH", tmp_path / "costs.json")
    request = RunRequest(brief="検証用の依頼を作成します。", send_to_n8n=True, agents=[
        {"role": "企画", "provider": "openai", "instructions": "企画を作る"},
        {"role": "執筆", "provider": "openai", "instructions": "原稿を書く"},
    ])
    result = asyncio.run(workflow.run_team(request))
    assert result.status == "completed"
    assert len(result.outputs) == 2
    assert "企画の成果物" in prompts[1]
    assert sent[0]["outputs"][1]["role"] == "執筆"
    assert result.costs["record_count"] == 2
    assert "検証用の依頼" not in costs.COSTS_PATH.read_text()
    assert "成果物" not in costs.COSTS_PATH.read_text()


def test_error_response_excludes_credentials_and_private_content(monkeypatch):
    async def fail(*args):
        raise RuntimeError("Bearer qa-secret https://example.com/hook/qa-secret 個人用の依頼本文")

    async def no_wait(*args):
        return None

    monkeypatch.setattr(workflow, "_run_specialist", fail)
    monkeypatch.setattr(workflow.asyncio, "sleep", no_wait)
    request = RunRequest(brief="検証用の依頼を作成します。", agents=[
        {"role": "企画", "provider": "openai", "instructions": "企画を作る"},
    ])
    result = asyncio.run(workflow.run_team(request))
    assert result.status == "failed"
    assert "qa-secret" not in result.model_dump_json()
    assert "個人用の依頼本文" not in result.model_dump_json()


def test_openai_run_disables_prompt_tracing(monkeypatch):
    async def run(agent, prompt, *, run_config):
        assert run_config.tracing_disabled is True
        return SimpleNamespace(final_output="検証用成果物", context_wrapper=SimpleNamespace(
            usage=SimpleNamespace(input_tokens=100, output_tokens=20)))

    monkeypatch.setattr(workflow.Runner, "run", run)
    result = asyncio.run(workflow._run_openai("企画", "指示", "依頼"))
    assert result.content == "検証用成果物"
    assert result.input_tokens == 100


def test_n8n_failure_preserves_completed_outputs_and_costs(monkeypatch, tmp_path):
    """Webhook障害でも生成済みの成果物と料金を失わない。"""
    async def generate(*args):
        return workflow.GenerationResult("完成原稿", 1000, 500)

    async def fail(payload):
        raise RuntimeError("https://example.com/private-webhook-token")

    monkeypatch.setattr(workflow, "_run_specialist", generate)
    monkeypatch.setattr(workflow, "_send_to_n8n", fail)
    monkeypatch.setattr(costs, "COSTS_PATH", tmp_path / "costs.json")
    request = RunRequest(brief="検証用の依頼を作成します。", send_to_n8n=True, agents=[
        {"role": "企画", "provider": "openai", "instructions": "企画を作る"},
    ])
    result = asyncio.run(workflow.run_team(request))
    assert result.status == "completed"
    assert result.outputs[0].content == "完成原稿"
    assert result.n8n["sent"] is False
    assert "private-webhook-token" not in result.model_dump_json()
    assert result.costs["record_count"] == 1
