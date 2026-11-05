# るっちFugu

ChatGPT・Claude・Gemini・Grok を専門チームとして順番に動かし、成果物を n8n へ渡せる FastAPI アプリです。

## チーム構成

`リサーチ → 構成 → 文章 → X投稿 → 炎上チェック → 画像プロンプト`

- OpenAI: OpenAI Agents SDK で担当を実行
- Claude / Gemini: API キーを設定した場合、担当ごとに切替可能
- n8n: `N8N_WEBHOOK_URL` を設定して「完了後に n8n へ渡す」を選ぶと、全成果物を JSON で POST

## 起動

```bash
uv sync
uv run uvicorn main:app --reload
```

ブラウザで `http://127.0.0.1:8000` を開きます。

## Webアプリとして自動公開

Render + GitHub で自動公開できます。

このリポジトリには `render.yaml` を用意しているため、GitHub に push したあと Render の Blueprint として読み込むだけで、Webアプリとして公開できます。

詳しい手順は [DEPLOY.md](DEPLOY.md) を見てください。

## API

`POST /api/runs`

```json
{
  "goal": "AI活用術のX投稿を作る",
  "brief": "ChatGPT＋Claude＋Gemini＋n8nでAIチームを作る方法を解説したい。",
  "providers": {"リサーチ": "gemini", "文章": "anthropic"},
  "send_to_n8n": true
}
```

すべての API レスポンスは JSON です。API キーや依頼本文をアプリケーションログには記録しません。

Renderでは `APP_PASSWORD` によるアクセス認証が必須です。詳しくは [DEPLOY.md](DEPLOY.md) を参照してください。OpenAI Agents SDKのトレース記録は無効化しています。

## 検証

```bash
uv sync --extra dev
uv run --extra dev pytest -q
node --check static/app.js
```

テストは外部のAI APIやn8nへ送信せず、一時ファイルで設定・料金を検証します。GitHub Actionsも同じ検証を実行します。
