# kantan-llm plan（v0.3）

チェックしながら進める（Doneは `[x]`）。

- [x] `docs/concept.md` / `docs/spec.md` / `docs/architecture.md` を要件に合わせて作成
- [x] `get_llm`（推測/上書き/フォールバック）を実装
- [x] 環境変数の仕様をREADMEに明記
- [x] 例外（Error ID）を実装し、READMEの失敗例と文言一致
- [x] 最小テスト（import / 分岐 / 不足エラー）を追加
- [x] `pytest` を通す

## Phase 0.2（Tracer追加: F8）

- [x] `docs/concept.md` / `docs/spec.md` / `docs/architecture.md` をTracer要件に合わせて更新（合意含む）
- [x] `kantan_llm.tracing`（Trace/Span/Scope/Tracer I/F）を実装
- [x] Tracer実装: PrintTracer（色分け）を実装
- [x] Tracer実装: SQLiteTracer（スキーマ/マイグレーションなしの最小）を実装
- [x] Tracer実装: OTELTracer（オプション依存、未導入時はE15）を実装
- [x] `get_llm(..., tracer=...)` を実装し、LLM呼び出しをSpanとして記録
- [x] テスト: `with trace` 有無でSpanが記録されること
- [x] テスト: Tracerが例外を投げてもLLM呼び出しが継続すること

## Phase 0.3（検索サービス: F9）

- [x] 検索I/F（TraceSearchService/Query/Record）を実装
- [x] SQLiteTracerの検索実装（Trace/Span/keywords/tool_call/name/limit）
- [x] 差分取得（get_spans_since/ingest_seq）を実装
- [x] 自動記録（structured output / tool_call / rubric の正規化）を実装
- [x] rubric（score/comment）抽出を実装
- [x] テスト: SQLite検索（keywords/has_tool_call/has_error）
- [x] テスト: get_spans_since の順序と排他条件
- [x] テスト: name での絞り込み（custom/function）
- [x] テスト: 時刻のnaive/aware解釈・返却
- [x] SQLite検索のサンプル/READMEを整備して使い勝手を確認
- [x] 自動記録のドキュメント整備（tutorial/README）

## Phase 0.4（OTEL/Tempo: F9）

- [ ] OTEL(Tempo)の検索連携を設計・実装
