"""FastAPI のエントリーポイント。"""

from pathlib import Path
import base64
import os
import secrets

from fastapi import FastAPI, Request
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


@app.middleware("http")
async def protect_app(request: Request, call_next):
    """公開環境のAI実行・設定・画面を共通の認証で保護する。"""
    if request.url.path == "/health":
        return await call_next(request)
    password = os.getenv("APP_PASSWORD", "")
    if not password:
        if os.getenv("RENDER", "").lower() == "true":
            return JSONResponse({"detail": "APP_PASSWORDをRenderの環境変数に設定してください。"}, status_code=503)
        return await call_next(request)
    username = os.getenv("APP_USERNAME", "lucci")
    expected = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
    supplied = request.headers.get("Authorization", "")
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        return JSONResponse(
            {"detail": "認証が必要です。"},
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="lucci-fugu", charset="UTF-8"'},
        )
    return await call_next(request)


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
    return JSONResponse({"status": "ok", "providers": {"openai": settings.openai_enabled, "anthropic": settings.anthropic_enabled, "gemini": settings.gemini_enabled, "xai": settings.xai_enabled}, "models": {"openai": settings.openai_model, "anthropic": settings.anthropic_model, "anthropic_sonnet": settings.anthropic_sonnet_model, "gemini": settings.gemini_model, "xai": settings.xai_model}})


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
