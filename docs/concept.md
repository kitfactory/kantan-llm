# kantan-llm concept（v0.2）

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
| F8 | Tracing / Tracer | `with trace` と `get_llm(..., tracer=...)` でスパンを記録する（Agents SDK互換） | F1 | ✅ | 0.2 |

## フェーズ分け

### Phase 0.1（このリポジトリの対象）

- F1〜F5 をMVPとして実装する
- F6 を「できれば」として実装する（全滅時に原因が分かる）
- テストは「import / `get_llm` の分岐 / 必要環境変数不足のエラー」をスモークとして用意する

### 将来（今回は不要）

- Streaming / Async
- structured output
- retry/backoff
- キャッシュ、セッション、詳細なレート制御

### Phase 0.2（Tracer追加）

- F8 を実装する
  - `kantan_llm.tracing.trace(...)`（OpenAI Agents SDK互換I/F）
  - `get_llm(..., tracer=...)` でLLM呼び出しをスパンとして記録
  - Tracer実装: PrintTracer / SQLiteTracer / OTELTracer

## 合意済み（F8: PrintTracerのデフォルト）

- 色分け: 入力（プロンプト）と出力を色分けして表示する
- 出力粒度: usage等の付帯情報は出さず、入力と出力のみ表示する（trace_id/span_id/elapsed等も出さない）
- 簡易マスク: Token/KEY等の秘匿値っぽい文字列は簡易マスクする（PII対策は将来オプション）
- 省略: デフォルトは省略しない（上限は環境変数等で設定されたときのみ発動）
- 自動生成Trace名: `with trace` なしのLLM呼び出しで自動生成するTraceの `workflow_name` は `default_workflow_name` とする
- 省略上限の環境変数: `KANTAN_LLM_TRACING_MAX_CHARS`
- 省略上限の適用範囲: PrintTracer / SQLiteTracer / OTELTracer のすべてに共通で適用する
- 記録する出力内容: 出力テキスト、または構造化出力（structured output）、または関数呼び出し（function calling）の内容を記録対象とする
