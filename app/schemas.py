"""API の入出力スキーマ。"""

from typing import Literal

from pydantic import BaseModel, Field


Provider = Literal["openai", "anthropic", "gemini", "xai"]


class TemplateAgent(BaseModel):
    """ユーザー作成テンプレート内の担当者設定。"""

    role: str = Field(min_length=1, max_length=80)
    provider: Provider
    instructions: str = Field(min_length=1, max_length=2_000)


class RunRequest(BaseModel):
    """チームへ渡す制作依頼。"""

    brief: str = Field(min_length=10, max_length=8_000, description="制作依頼の本文")
    goal: str = Field(default="AI活用術のX投稿を作る", max_length=300)
    providers: dict[str, Provider] = Field(default_factory=dict)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    template: str = "x"
    agents: list[TemplateAgent] = Field(default_factory=list, max_length=12)
    send_to_n8n: bool = False
    xai_live_search: bool = False


class AgentOutput(BaseModel):
    """一人の担当者が生成した成果物。"""

    role: str
    provider: Provider
    model: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_usd: float | None = None


class RunResponse(BaseModel):
    """チーム実行の結果。"""

    run_id: str
    status: Literal["completed", "failed"]
    outputs: list[AgentOutput]
    n8n: dict[str, str | bool]
    costs: dict = Field(default_factory=dict)
