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
- 観測→検索→評価→改善のループを最短で回せること（SQLite正本）

## Scope方針（観測→改善ループ）

- 目的: 普通の企業内開発者でも、観測（trace）→検索（掘る）→評価（judge）→改善→再評価のループを回せること
- まずは手元（SQLite）で完結し、外部基盤を必須にしない
- SQLiteは正式な検索実装の一つであり、仕様障壁が低いリファレンス実装とする

## 非ゴール（やらない）

- 価格表（モデル単価）の同梱・追随・自動更新
- 予算超過の強制停止、複雑なルーティング、統制ポリシーの中核実装
- 統制は必要なら外部ゲートウェイ/社内基盤で後付けする

## Async / Agents SDK 連携（Escape hatch）

### Paved path（推奨の一本道）
kantan-llm の推奨パスは **同期（sync）**のラッパー経由の利用です。このパスでは以下を “保証” します。

- provider 推測 / model 正規化 / 環境変数解決
- provider フォールバック方針
- API 方針（Responses / Chat など）のガード
- 自動トレーシング（有効化されている場合）

### Non-goals（Paved path の非ゴール）
- Async-first API（最初から async 前提の設計）
- Streaming の保証（sync / paved path では扱わない）

### Escape hatches（例外導線）
ASGI（FastAPI / Starlette 等）で event loop をブロックしないために、Async は **escape hatch（例外導線）**として提供します。Async には 2 段階あります。

1) **Raw async client bundle（ガード無し / 自動トレース無し）**
- 互換性最大化のため、SDK の `AsyncOpenAI` を “そのまま” 返します。
- ただし raw client 返却では、kantan-llm の **API ガード / 自動トレーシングは強制しません**。
- 代わりに、下流（例: OpenAI Agents SDK）へ渡せるよう **正規化済み model/provider/base_url も一緒に返します**。

2) **KantanAsyncLLM（ガードあり / 自動トレースあり）**
- 同期版（KantanLLM）と同等の保証（正規化/フォールバック/ガード/トレース）を提供する async ラッパーです。
- ただし Agents SDK 側にもトレーシング機構があるため、二重計測にならないよう “どちらでトレースするか” を明示します（後述）。
- streaming API を提供し、最終応答でまとめてトレースします（チャンク単位のトレースはしない）。

### OpenAI Agents SDK 連携（設計の前提）
Async escape hatch は **OpenAI Agents SDK で “任意の AsyncOpenAI client を差し替える”**用途を想定します。

- Agents SDK は `set_default_openai_client(AsyncOpenAI(...))` によりデフォルト client を差し替えられます。
- また `OpenAIResponsesModel(..., openai_client=AsyncOpenAI(...))` のように、モデル単位で `openai_client` を渡すこともできます。
- kantan-agents では上記 2 つのメソッドを利用して client を差し替えます。

このため kantan-llm は、Agents SDK に渡しやすいように raw async client 返却時でも **正規化済み model 名を必ず外に出す**設計にします。

### Tracing policy（二重計測を避ける）
Agents SDK 側にもトレーシング無効化の導線があるため、運用では次のいずれかを選びます。

- A) Agents SDK のトレースを使う（kantan 側トレースは無効、または raw client）
- B) kantan のトレースを使う（Agents SDK 側トレースは無効）

### Resolver parity（最重要保証）
- sync / async の推測・正規化ロジックは単一 resolver に集約する
- get_llm() と get_async_llm()/get_async_llm_client() の解決結果は一致すること

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
| F9 | Trace検索サービス | Trace/Spanを検索・抽出する共通I/Fを提供する | F8 | ◯ | 0.3 |
| F10 | SQLite正本の改善ループ強化（最小） | SQLiteTracer の原子性・usage正規化を改善する | F8, F9 | ◯ | 0.4+ |
| F11 | ルーブリック検索ユーティリティ | search I/F を使った失敗抽出/バケット分けを補助する | F9 | ◯ | 0.4+ |
| F12 | Async 導線 / Agents SDK 連携（escape hatch） | raw async client bundle と KantanAsyncLLM を提供する | F2, F3, F4, F5, F6, F8 | ✗ | 0.6 |

## フェーズ分け

### Phase 0.1（このリポジトリの対象）

- F1〜F5 をMVPとして実装する
- F6 を「できれば」として実装する（全滅時に原因が分かる）
- テストは「import / `get_llm` の分岐 / 必要環境変数不足のエラー」をスモークとして用意する

### 将来（今回は不要）

- Streaming（sync / paved path）
- Async-first API
- structured output
- retry/backoff
- キャッシュ、セッション、詳細なレート制御

### Phase 0.2（Tracer追加）

- F8 を実装する
  - `kantan_llm.tracing.trace(...)`（OpenAI Agents SDK互換I/F）
  - `get_llm(..., tracer=...)` でLLM呼び出しをスパンとして記録
  - Tracer実装: PrintTracer / SQLiteTracer / OTELTracer

### Phase 0.3（検索サービス）

- F9 を実装する
  - Trace/Spanの検索I/Fを提供する（SQLite/OTEL共通）
  - 評価スコア抽出やtool call有無などの検索をサポート
  - 既存Traceに追加されたSpanの差分取得をサポート

### Phase 0.4（観測→改善ループの強化）

- SQLiteを正本とし、観測→検索→評価→改善の導線を整備する
- usageの正本記録（Span）と、Trace合計のキャッシュ（任意）を追加する

### Phase 0.4+（SQLite正本の改善ループ強化: 最小）

- SQLiteTracer の書き込みを原子化して「部分書き込み」を防ぐ
- usageキーの揺れを最小正規化し、total_tokens を安定させる
- SQLなしで閾値未満のjudgeを拾うユーティリティを追加する

### Phase 0.6（Async / Agents SDK 連携）

- F12 を実装する
  - `get_async_llm_client`（raw async bundle）を提供する
  - `get_async_llm`（KantanAsyncLLM）を提供する
  - sync/async の resolver parity を保証する
  - KantanAsyncLLM の streaming API とまとめトレースを整備する
  - Agents SDK 連携例と二重トレース方針を整備する


## 合意済み（F8: PrintTracerのデフォルト）

- 色分け: 入力（プロンプト）と出力を色分けして表示する
- 出力粒度: usage等の付帯情報は出さず、入力と出力のみ表示する（trace_id/span_id/elapsed等も出さない）
- 簡易マスク: Token/KEY等の秘匿値っぽい文字列は簡易マスクする（PII対策は将来オプション）
- 省略: デフォルトは省略しない（上限は環境変数等で設定されたときのみ発動）
- 自動生成Trace名: `with trace` なしのLLM呼び出しで自動生成するTraceの `workflow_name` は `default_workflow_name` とする
- 省略上限の環境変数: `KANTAN_LLM_TRACING_MAX_CHARS`
- 省略上限の適用範囲: PrintTracer / SQLiteTracer / OTELTracer のすべてに共通で適用する
- 記録する出力内容: 出力テキスト / 構造化出力（structured output） / 関数呼び出し（tool call） / ルーブリックを記録対象とし、`output_kind`（text/tool_calls/structured/judge）で区別保存する

## kantan-llm / kantan-agents のすみわけ（案）

- kantan-llm: Trace/Span の記録・保存・検索I/Fを提供し、`kind` など分析起点の最小規約を整備する
- kantan-llm: Agents SDK を必須依存にせず、Tracer互換I/Fで連携できる状態を維持する
- kantan-agents: Agents SDK のAPIを再エクスポートし、Agentクラスでメタ情報（agent名/prompt名/版）を付与する
- kantan-agents: `judge` など評価Span生成・rubric正規化・検索ユーティリティを体験として提供する
