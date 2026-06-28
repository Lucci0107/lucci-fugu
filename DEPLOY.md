# るっちFuguをWebアプリとして自動公開する方法

このプロジェクトは Render + GitHub で自動公開できます。

一度 Render と GitHub を接続すると、以後は GitHub に push するたびに Render が自動でビルドし、Webアプリを更新します。

## 1. GitHubへアップロードする

ローカルで変更をコミットして、GitHub リポジトリへ push します。

```bash
git add .
git commit -m "Renderで自動公開できる設定を追加"
git push
```

## 2. RenderでBlueprintを作成する

1. Render を開く
2. New から Blueprint を選ぶ
3. GitHub の `lucci-fugu` リポジトリを選ぶ
4. `render.yaml` が読み込まれることを確認する
5. 作成する

`render.yaml` により、以下が自動設定されます。

- Web Service 名: `lucci-fugu`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health Check: `/health`
- Auto Deploy: 有効

## 3. Renderに環境変数を登録する

`.env.local` はGitHubへアップロードしません。

Render の Environment 画面で、必要なキーだけ登録してください。

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
XAI_API_KEY
N8N_WEBHOOK_URL
```

必須は `OPENAI_API_KEY` です。

Claude / Gemini / Grok / n8n を使う場合は、それぞれのキーやURLも登録します。

## 4. 公開後の確認

Render の公開URLを開きます。

```text
https://lucci-fugu.onrender.com/
```

死活確認は以下です。

```text
https://lucci-fugu.onrender.com/health
```

## 注意

- APIキーはGitHubへコミットしないでください。
- `.env.local` はローカル専用です。
- Render の無料プランでは、しばらく使わないと起動に時間がかかることがあります。
- `data/` に保存される履歴や概算料金は、Render の無料環境では永続保存されない場合があります。本格運用では外部DBの利用をおすすめします。
