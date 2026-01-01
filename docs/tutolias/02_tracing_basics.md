# 02. Trace/Span の基本と PrintTracer

## シーン

LLM 呼び出しの入力と出力を、その場で確認したいときがあります。
この単元では保存はせず、まずは表示だけで状況を把握する方法を見ます。

## 使う機能

ここでは PrintTracer を使います。
`get_llm()` で tracer を指定しない場合、デフォルトで PrintTracer が利用されます。
また、`with trace` を使うと複数の呼び出しを同じ Trace にまとめられます。

## どう使うか

まずは何も指定せず `get_llm()` を呼び、入力と出力が表示されることを確認します。
次に `with trace` の内側で複数回呼び出し、同じ Trace にまとめられることを体感します。

## コード

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini")
res = llm.responses.create(input="hello")
print(res.output_text)
```

```python
from kantan_llm import get_llm
from kantan_llm.tracing import trace

llm = get_llm("gpt-4.1-mini")
with trace("workflow"):
    llm.responses.create(input="first")
    llm.responses.create(input="second")
```

## 注意点

PrintTracer は入力と出力のみを表示します。
usage などの付帯情報は表示しません。

## 次の単元

- `docs/tutolias/03_sqlite_tracing.md`
