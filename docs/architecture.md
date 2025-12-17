# kantan-llm architecture（v0.1）

## 1. レイヤーと責務

- Public API layer
  - `kantan_llm.get_llm` を公開する
  - 入力バリデーション、推測/上書き、フォールバック選択を行う
- Provider layer
  - provider推測、環境変数/引数からの設定解決
  - OpenAI SDK `OpenAI` クライアントを適切な `api_key` / `base_url` で構築する
- Wrapper layer
  - `llm.responses.create(...)` / `llm.chat.completions.create(...)` を提供する
  - 返却（Responses/ChatCompletions）は原形保持（変換しない）

依存方向: Public API → Provider → Wrapper（逆依存はしない）

## 2. 主要I/F（最小粒度・最小引数）

### 2.1 Public API

```python
def get_llm(
    model: str,
    *,
    provider: str | None = None,
    providers: list[str] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
):
    ...
```

### 2.2 Wrapper

- `KantanLLM`
  - 属性: `provider: str`, `model: str`, `client: OpenAI`
  - `responses.create(...)`（provider=`openai` のみ）
  - `chat.completions.create(...)`（provider=`compat` のみ）

## 3. ログ/エラー方針

- 例外メッセージは必ず Error ID を含める（例: `[kantan-llm][E2] ...`）
- `providers=[...]` の全滅時は候補ごとの失敗理由をまとめて返す
- 機密情報（APIキー等）をエラー文面に含めない
