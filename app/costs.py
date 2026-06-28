"""トークン使用量から概算料金を算出・保存する。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


COSTS_PATH = Path(__file__).parent.parent / "data" / "cost_records.json"
PRICING_PATH = Path(__file__).parent.parent / "config" / "model_pricing.json"
JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class TokenPrice:
    """100万トークンあたりの標準料金（米ドル）。"""

    input_usd: float
    output_usd: float
    cached_input_usd: float


def _load_prices() -> dict[str, TokenPrice]:
    """設定ファイルからモデル別の標準単価を読み込む。"""
    try:
        raw_prices = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
        return {
            model: TokenPrice(
                float(price["input_usd_per_million"]),
                float(price["output_usd_per_million"]),
                float(price["cached_input_usd_per_million"]),
            )
            for model, price in raw_prices.items()
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {}


def estimate_usd(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float | None:
    """モデル単価とトークン数から概算料金を返す。単価不明ならNone。"""
    price = _load_prices().get(model)
    if price is None:
        return None
    cached = min(max(cached_input_tokens, 0), max(input_tokens, 0))
    standard_input = max(input_tokens - cached, 0)
    return round(
        (standard_input * price.input_usd + cached * price.cached_input_usd + max(output_tokens, 0) * price.output_usd) / 1_000_000,
        8,
    )


def _load_records() -> list[dict]:
    """保存済みの概算料金レコードを返す。"""
    try:
        data = json.loads(COSTS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_run_costs(run_id: str, items: list[dict]) -> None:
    """実行ごとの料金情報だけを保存する。依頼本文や成果物は保存しない。"""
    records = _load_records()
    created_at = datetime.now(JST).isoformat()
    records.extend({"run_id": run_id, "created_at": created_at, **item} for item in items if item.get("estimated_usd") is not None)
    COSTS_PATH.parent.mkdir(exist_ok=True)
    COSTS_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def cost_summary(run_id: str | None = None) -> dict:
    """今回・AI別累計・当月合計を概算として集計する。"""
    records = _load_records()
    current_month = datetime.now(JST).strftime("%Y-%m")
    monthly = [item for item in records if str(item.get("created_at", ""))[:7] == current_month]
    run_records = [item for item in records if run_id and item.get("run_id") == run_id]

    def total(items: list[dict]) -> float:
        return round(sum(float(item.get("estimated_usd", 0)) for item in items), 8)

    provider_totals: dict[str, float] = {}
    for item in records:
        provider = str(item.get("provider", "unknown"))
        provider_totals[provider] = round(provider_totals.get(provider, 0) + float(item.get("estimated_usd", 0)), 8)

    return {
        "label": "概算",
        "currency": "USD",
        "month": current_month,
        "run_total_usd": total(run_records),
        "monthly_total_usd": total(monthly),
        "provider_totals_usd": provider_totals,
        "record_count": len(records),
    }
