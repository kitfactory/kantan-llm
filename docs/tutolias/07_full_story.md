# 07. 記録して分析し、プロンプトを改善する

## シーン

あるLLMの応答品質が安定しないため、まずは記録して分析し、プロンプト改善につなげたい状況を想定します。
一度の実行で終わらせず、記録 → 分析 → 改善 → 再評価という流れを短いストーリーで体験します。

## 使う機能

この単元では、次の機能を使います。

- SQLiteTracer による記録
- judge Span による評価
- `find_failed_judges` による閾値未満の抽出
- `group_failed_by_bucket` による原因の整理

## どう使うか

まずは評価基準となるプロンプトを用意し、LLMの出力を記録します。
次に judge を使って簡易的な評価を付与し、スコアの低いものだけを抽出します。
抽出した結果から、改善対象の傾向を把握し、プロンプトを修正します。
最後に同じ流れでもう一度実行し、改善の効果を確認します。

## コード

### 1) 記録する

```python
from kantan_llm import get_llm
from kantan_llm.tracing import set_trace_processors, trace, custom_span
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
set_trace_processors([tracer])

llm = get_llm("gpt-4.1-mini")

prompt = "次の文章を一行で要約してください。\n\n" \
         "文章: 今日は新しい仕様を確認し、テストを追加して品質を上げた。"

with trace("summary-v1"):
    res = llm.responses.create(input=prompt)
    output = res.output_text
    # 最低限の judge（例: 手動で簡易評価する想定）
    with custom_span(name="judge", data={"rubric": {"score": 0.4, "comment": "短すぎる"}}):
        pass
```

### 2) 分析する（閾値未満を抽出）

```python
from kantan_llm.tracing.analysis import find_failed_judges, group_failed_by_bucket
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
failed = find_failed_judges(tracer, threshold=0.6, limit=200)

bucketed = group_failed_by_bucket(failed)
print({k: len(v) for k, v in bucketed.items()})
```

### 3) プロンプトを改善して再実行する

```python
from kantan_llm import get_llm
from kantan_llm.tracing import trace, custom_span

llm = get_llm("gpt-4.1-mini")

prompt = "次の文章を一行で要約してください。\n" \
         "条件: 具体的な名詞を含め、30文字以内で書く。\n\n" \
         "文章: 今日は新しい仕様を確認し、テストを追加して品質を上げた。"

with trace("summary-v2"):
    res = llm.responses.create(input=prompt)
    output = res.output_text
    with custom_span(name="judge", data={"rubric": {"score": 0.7, "comment": "改善した"}}):
        pass
```

## 期待する結果

- `summary-v1` と `summary-v2` が記録される
- 低スコアの judge を抽出できる
- プロンプト改善後のスコアが上がることを確認できる

## 次の単元

- ここが最後の単元です
