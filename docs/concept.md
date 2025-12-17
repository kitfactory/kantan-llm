# kantan-llm concept（v0.1）

## 想定ユーザーと困りごと

- 想定ユーザー: Pythonで検証・CLI・小ツールを作る開発者
- 困りごと: LLM利用のたびに毎回書いてしまう `get_llm` 相当処理（キー取得、接続先、モデル→プロバイダー判定など）を最小記述で済ませたい

## 設計原則

- 最短コードパス（覚えることを減らす）
- デフォルトで動く（設定ファイル必須にしない）
- 推測 + 上書き可能（自動判定が基本、明示指定で上書き）
- 壊れにくさ（エラーが明確）
- 原形保持（OpenAI/非OpenAIで返却形式を無理に統一しない）

## 機能一覧（表）

| Spec ID | 機能名 | 概要 | 依存 | MVP | Phase |
|---|---|---|---|---|---|
| F1 | `get_llm(model, **options)` | モデル名からLLMクライアントを取得する | F2, F3, F4, F5 | ✅ | 0.1 |
| F2 | プロバイダー推測 | `gpt-*`→OpenAI、`claude-*`/`gemini-*`→互換（Chat）など | - | ✅ | 0.1 |
| F3 | API採用方針 | OpenAIはResponses、非OpenAIはChat Completions互換を正本にする | - | ✅ | 0.1 |
| F4 | 環境変数設定 | `OPENAI_*` と（LMStudio/Ollama/OpenRouter等の）環境変数を読む | - | ✅ | 0.1 |
| F5 | 明示指定（上書き） | `provider=` / `providers=` で推測を上書きする | F2 | ✅ | 0.1 |
| F6 | フォールバック | `providers=[...]` で利用可能なものを順に試す | F4, F5 | ◯ | 0.1（MVP+） |
| F7 | 任意設定ファイル | `provider.json` 等で base_url/api_key を定義できる | F4 | ✗ | 将来 |

## フェーズ分け

### Phase 0.1（このリポジトリの対象）

- F1〜F5 をMVPとして実装する
- F6 を「できれば」として実装する（全滅時に原因が分かる）
- テストは「import / `get_llm` の分岐 / 必要環境変数不足のエラー」をスモークとして用意する

### 将来（今回は不要）

- Streaming / Async
- structured output
- retry/backoff
- Tracer/OTEL連携
- キャッシュ、セッション、詳細なレート制御
