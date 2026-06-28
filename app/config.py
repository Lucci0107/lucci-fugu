"""環境変数から設定を読む。"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv(".env.local")


@dataclass(frozen=True)
class Settings:
    """実行時設定。シークレット値そのものは保持・出力しない。"""

    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    anthropic_sonnet_model: str = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-4-5-20250929")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    xai_model: str = os.getenv("XAI_MODEL", "grok-4.3")
    n8n_webhook_url: str | None = os.getenv("N8N_WEBHOOK_URL") or None

    @property
    def anthropic_enabled(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    @property
    def gemini_enabled(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    @property
    def xai_enabled(self) -> bool:
        return bool(os.getenv("XAI_API_KEY"))


settings = Settings()
