# 06. 補助ユーティリティ（find_failed_judges など）

## シーン

SQLを書かずに、閾値未満の judge を拾って整理したい場面を想定します。
手動で検索条件を組み立てる手間を減らし、改善ループを早く回すための補助です。

## 使う機能

ここでは `find_failed_judges` と `group_failed_by_bucket` を使います。
どちらも Search I/F だけで動くため、SQLiteTracer だけで利用できます。

## どう使うか

まず Search I/F を持つトレーサ（SQLiteTracer）を用意します。
次に `find_failed_judges` で失敗判定を抽出します。
最後に `group_failed_by_bucket` でバケット化し、分布を把握します。

## コード

```python
from kantan_llm.tracing.analysis import find_failed_judges
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
failed = find_failed_judges(tracer, threshold=0.6, limit=200)
```

```python
from kantan_llm.tracing.analysis import group_failed_by_bucket

bucketed = group_failed_by_bucket(failed)
print({k: len(v) for k, v in bucketed.items()})
```

```python
from kantan_llm.tracing import TraceQuery
from kantan_llm.tracing.analysis import find_failed_judges
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
query = TraceQuery(workflow_name="demo", limit=50)
failed = find_failed_judges(tracer, threshold=0.6, limit=200, trace_query=query)
```
