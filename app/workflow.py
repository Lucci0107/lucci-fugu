"""AI チームの順次オーケストレーション。"""

from __future__ import annotations

import os
import asyncio
import re
from dataclasses import dataclass
from uuid import uuid4

import httpx
from agents import Agent, Runner

from app.config import settings
from app.costs import cost_summary, estimate_usd, save_run_costs
from app.schemas import AgentOutput, Provider, RunRequest, RunResponse


@dataclass(frozen=True)
class Specialist:
    """担当者の役割、標準プロバイダー、実行指示。"""

    role: str
    default_provider: Provider
    instructions: str


@dataclass(frozen=True)
class GenerationResult:
    """各社APIから受け取った本文とトークン使用量。"""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


SPECIALISTS = (
    Specialist("リサーチ", "gemini", "市場の論点、一次情報を確認すべき点、読者の疑問を箇条書きで整理する。未検証の事実は断定しない。"),
    Specialist("構成", "openai", "前工程の調査を材料に、読者に届く結論先行の構成案を作る。見出しと各節の要点を明示する。"),
    Specialist("文章", "anthropic", "構成をもとに、自然で具体的な日本語の原稿を書く。根拠のない数字・引用は作らない。"),
    Specialist("X投稿", "openai", "原稿をもとに、読みやすいX投稿を3案作る。各案はフック、本文、自然なCTAを含める。出力は投稿本文だけにする。前置き、解説、見出し、案番号、Markdown記法、コードブロック、ハッシュタグ一覧は出力しない。投稿間は空行2行だけで区切る。"),
    Specialist("炎上チェック", "gemini", "成果物を安全・信頼性・誤解可能性の観点で確認し、問題箇所と置換案を具体的に示す。"),
    Specialist("画像プロンプト", "openai", "内容に合う、文字なしのSNS用アイキャッチ画像を生成するための詳細な英語プロンプトを書く。出力は画像生成ツールへそのまま貼れる英語プロンプト1本だけにする。前置き、説明、見出し、Markdown、コードブロック、引用符、サイズ指定、否定文リストは出力しない。"),
)

TEAM_PRESETS = {
    "x": SPECIALISTS,
    "note": (
        SPECIALISTS[0], SPECIALISTS[1],
        Specialist("記事執筆", "anthropic", "調査と構成をもとに、note記事として読み応えのある本文を書く。"),
        Specialist("編集・事実確認", "gemini", "記事を編集し、事実性・読みやすさ・誤解の余地を確認する。"),
        Specialist("タイトル・アイキャッチ", "openai", "記事タイトル案と、文字なしのアイキャッチ用英語プロンプトを作る。"),
    ),
    "line": (
        Specialist("ヒアリング整理", "gemini", "依頼内容から確認すべき業務課題とヒアリング項目を整理する。"),
        Specialist("業務分析", "openai", "現状業務、課題、KPI、LINE自動化の余地を分析する。"),
        Specialist("導線設計", "openai", "友だち追加から成約までのLINE導線を設計する。"),
        Specialist("ステップ配信設計", "anthropic", "配信シナリオ、メッセージ、条件分岐を具体化する。"),
        Specialist("提案書", "anthropic", "クライアント提出用の提案書として、目的・施策・期待効果・進行をまとめる。"),
        Specialist("リスク確認", "gemini", "個人情報、誤認表現、運用リスクを確認し改善案を示す。"),
    ),
}


def _provider_for(specialist: Specialist, overrides: dict[str, Provider]) -> Provider:
    """役割指定を優先し、未設定プロバイダーは OpenAI へ安全にフォールバックする。"""
    selected = overrides.get(specialist.role, specialist.default_provider)
    if selected == "anthropic" and not settings.anthropic_enabled:
        return "openai"
    if selected == "gemini" and not settings.gemini_enabled:
        return "openai"
    if selected == "xai" and not settings.xai_enabled:
        return "openai"
    return selected


def _model_for(provider: Provider, model_override: str | None = None) -> str:
    """プロバイダーと担当指定に応じた安全なモデル名を返す。"""
    if provider == "anthropic":
        if model_override == settings.anthropic_sonnet_model:
            return settings.anthropic_sonnet_model
        return settings.anthropic_model
    if provider == "gemini":
        return settings.gemini_model
    if provider == "xai":
        return settings.xai_model
    return settings.openai_model


async def _run_openai(role: str, instructions: str, prompt: str) -> GenerationResult:
    """OpenAI Agents SDK で一担当を実行する。"""
    agent = Agent(name=f"るっちFugu・{role}", instructions=instructions, model=settings.openai_model)
    result = await Runner.run(agent, prompt)
    usage = result.context_wrapper.usage
    cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
    return GenerationResult(str(result.final_output), usage.input_tokens, usage.output_tokens, cached)


async def _run_anthropic(instructions: str, prompt: str, model: str) -> GenerationResult:
    """Anthropic Messages API を呼ぶ。"""
    headers = {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {"model": model, "max_tokens": 1800, "system": instructions, "messages": [{"role": "user", "content": prompt}]}
    async with httpx.AsyncClient(timeout=90) as client:
        for attempt in range(3):
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if response.status_code != 529 or attempt == 2:
                response.raise_for_status()
                break
            await asyncio.sleep(2 * (attempt + 1))
    data = response.json()
    usage = data.get("usage", {})
    return GenerationResult(
        data["content"][0]["text"],
        int(usage.get("input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
        int(usage.get("cache_read_input_tokens", 0)),
    )


async def _run_gemini(instructions: str, prompt: str) -> GenerationResult:
    """Gemini generateContent API を呼ぶ。"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {"system_instruction": {"parts": [{"text": instructions}]}, "contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=payload)
        response.raise_for_status()
    data = response.json()
    usage = data.get("usageMetadata", {})
    return GenerationResult(
        data["candidates"][0]["content"]["parts"][0]["text"],
        int(usage.get("promptTokenCount", 0)),
        int(usage.get("candidatesTokenCount", 0)),
        int(usage.get("cachedContentTokenCount", 0)),
    )


def _xai_response_text(data: dict) -> str:
    """Responses API の出力形式から最終本文を取り出す。"""
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"]
    parts: list[str] = []
    for output in data.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    if parts:
        return "\n".join(parts)
    raise RuntimeError("GrokのResponses APIから本文を取得できませんでした")


def _xai_citations(data: dict) -> list[str]:
    """検索結果のURLを重複なく整形する。"""
    citations = data.get("citations", [])
    urls = [item.get("url") if isinstance(item, dict) else str(item) for item in citations]
    return list(dict.fromkeys(url for url in urls if url and url.startswith("http")))[:8]


async def _run_xai(instructions: str, prompt: str, live_search: bool) -> GenerationResult:
    """xAI Responses APIを呼び、必要な時だけWeb／X検索を使う。"""
    headers = {"Authorization": f"Bearer {os.environ['XAI_API_KEY']}", "Content-Type": "application/json"}
    payload: dict = {
        "model": settings.xai_model,
        "input": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
    }
    if live_search:
        payload["tools"] = [{"type": "web_search"}, {"type": "x_search"}]
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post("https://api.x.ai/v1/responses", headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    usage = data.get("usage", {})
    cached = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
    content = _xai_response_text(data)
    citations = _xai_citations(data) if live_search else []
    if citations:
        content += "\n\n参照ソース:\n" + "\n".join(f"- {url}" for url in citations)
    return GenerationResult(
        content,
        int(usage.get("input_tokens", usage.get("prompt_tokens", 0))),
        int(usage.get("output_tokens", usage.get("completion_tokens", 0))),
        int(cached or 0),
    )


async def _run_specialist(provider: Provider, specialist: Specialist, prompt: str, model: str, xai_live_search: bool) -> GenerationResult:
    """選択されたモデルに担当を委譲する。"""
    if provider == "anthropic":
        return await _run_anthropic(specialist.instructions, prompt, model)
    if provider == "gemini":
        return await _run_gemini(specialist.instructions, prompt)
    if provider == "xai":
        return await _run_xai(specialist.instructions, prompt, xai_live_search)
    return await _run_openai(specialist.role, specialist.instructions, prompt)


async def _send_to_n8n(payload: dict) -> dict[str, str | bool]:
    """設定済みの n8n Webhook に成果物を渡す。"""
    if not settings.n8n_webhook_url:
        return {"sent": False, "message": "N8N_WEBHOOK_URL が未設定です"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(settings.n8n_webhook_url, json=payload)
        response.raise_for_status()
    return {"sent": True, "message": "n8n Webhook へ送信しました"}


async def run_team(request: RunRequest) -> RunResponse:
    """前の担当の成果物を次の担当へ渡し、チームとして実行する。"""
    run_id = str(uuid4())
    outputs: list[AgentOutput] = []
    context = f"制作目的: {request.goal}\n\n依頼内容:\n{request.brief}"

    specialists = (
        tuple(Specialist(agent.role, agent.provider, agent.instructions) for agent in request.agents)
        if request.agents
        else TEAM_PRESETS.get(request.template, SPECIALISTS)
    )

    try:
        for specialist in specialists:
            provider = _provider_for(specialist, request.providers)
            model = _model_for(provider, request.model_overrides.get(specialist.role))
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    generation = await _run_specialist(provider, specialist, context, model, request.xai_live_search)
                    break
                except Exception as error:
                    last_error = error
                    if attempt == 2:
                        if provider == "gemini":
                            generation = await _run_openai(
                                f"{specialist.role}（Gemini代行）",
                                specialist.instructions,
                                context,
                            )
                            provider = "openai"
                            model = _model_for(provider)
                            break
                        raise RuntimeError(
                            f"{specialist.role}担当（{provider}）で失敗: "
                            f"{type(error).__name__}: {str(error)[:240]}"
                        ) from error
                    await asyncio.sleep(2 * (attempt + 1))
            else:
                raise last_error or RuntimeError("担当の実行に失敗しました")
            output = AgentOutput(
                role=specialist.role,
                provider=provider,
                model=model,
                content=generation.content,
                input_tokens=generation.input_tokens,
                output_tokens=generation.output_tokens,
                cached_input_tokens=generation.cached_input_tokens,
                estimated_usd=estimate_usd(model, generation.input_tokens, generation.output_tokens, generation.cached_input_tokens),
            )
            outputs.append(output)
            context += f"\n\n--- {specialist.role} の成果物 ---\n{generation.content}"
        n8n = await _send_to_n8n({"run_id": run_id, "goal": request.goal, "outputs": [output.model_dump() for output in outputs]}) if request.send_to_n8n else {"sent": False, "message": "送信は要求されていません"}
        save_run_costs(run_id, [output.model_dump(exclude={"role", "content"}) for output in outputs])
        return RunResponse(run_id=run_id, status="completed", outputs=outputs, n8n=n8n, costs=cost_summary(run_id))
    except Exception as error:
        safe_error = re.sub(r"([?&]key=)[^&\s'\"]+", r"\1[REDACTED]", str(error))
        return RunResponse(run_id=run_id, status="failed", outputs=outputs, n8n={"sent": False, "message": f"実行を停止しました: {safe_error}"}, costs={"label": "概算"})
