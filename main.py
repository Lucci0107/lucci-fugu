"""FastAPI のエントリーポイント。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.costs import cost_summary
from app.schemas import RunRequest, RunResponse
from app.workflow import run_team
from app.user_settings import load_user_settings, save_user_settings


ROOT = Path(__file__).parent
app = FastAPI(title="るっちFugu API", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """操作画面を返す。"""
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon() -> FileResponse:
    """ブラウザタブ用のファビコンを返す。"""
    return FileResponse(ROOT / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
async def health() -> JSONResponse:
    """Render 等の死活監視用エンドポイント。"""
    return JSONResponse({"status": "ok", "providers": {"openai": True, "anthropic": settings.anthropic_enabled, "gemini": settings.gemini_enabled, "xai": settings.xai_enabled}, "models": {"openai": settings.openai_model, "anthropic": settings.anthropic_model, "anthropic_sonnet": settings.anthropic_sonnet_model, "gemini": settings.gemini_model, "xai": settings.xai_model}})


@app.post("/api/runs", response_model=RunResponse)
async def create_run(request: RunRequest) -> RunResponse:
    """AI チームの処理を開始し、成果物を JSON で返す。"""
    return await run_team(request)


@app.get("/api/user-settings")
async def get_user_settings() -> JSONResponse:
    """画面設定をJSONで返す。"""
    return JSONResponse(load_user_settings())


@app.put("/api/user-settings")
async def put_user_settings(settings_body: dict) -> JSONResponse:
    """画面設定を保存する。"""
    return JSONResponse(save_user_settings(settings_body))


@app.get("/api/costs")
async def get_costs() -> JSONResponse:
    """保存済みのAPI概算料金をJSONで返す。"""
    return JSONResponse(cost_summary())
