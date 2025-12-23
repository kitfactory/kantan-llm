# kantan-llm plan（v0.2）

チェックしながら進める（Doneは `[x]`）。

- [x] `docs/concept.md` / `docs/spec.md` / `docs/architecture.md` を要件に合わせて作成
- [x] `get_llm`（推測/上書き/フォールバック）を実装
- [x] 環境変数の仕様をREADMEに明記
- [x] 例外（Error ID）を実装し、READMEの失敗例と文言一致
- [x] 最小テスト（import / 分岐 / 不足エラー）を追加
- [x] `pytest` を通す

## Phase 0.2（Tracer追加: F8）

- [ ] `docs/concept.md` / `docs/spec.md` / `docs/architecture.md` をTracer要件に合わせて更新（合意含む）
- [ ] `kantan_llm.tracing`（Trace/Span/Scope/Tracer I/F）を実装
- [ ] Tracer実装: PrintTracer（色分け）を実装
- [ ] Tracer実装: SQLiteTracer（スキーマ/マイグレーションなしの最小）を実装
- [ ] Tracer実装: OTELTracer（オプション依存、未導入時はE15）を実装
- [ ] `get_llm(..., tracer=...)` を実装し、LLM呼び出しをSpanとして記録
- [ ] テスト: `with trace` 有無でSpanが記録されること
- [ ] テスト: Tracerが例外を投げてもLLM呼び出しが継続すること
