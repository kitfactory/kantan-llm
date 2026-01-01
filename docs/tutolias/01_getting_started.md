# 01. 最短セットアップと基本実行

## シーン

最初の一歩として、できるだけ短い手順で LLM を呼び出し、手元で動作確認したい場面を想定します。

## 使う機能

ここでは `get_llm()` を使って LLM クライアントを取得します。
モデル名から provider を推測してくれるため、最低限の指定で呼び出せます。

## どう使うか

まずは仮想環境を用意し、依存を導入します。
OpenAI を使う場合は API キーを環境変数に設定しておきます。
準備ができたら `get_llm()` でクライアントを取得し、Responses API を呼び出します。

## コード

```bash
uv venv
. .venv/bin/activate
uv pip install -e .
export OPENAI_API_KEY=... 
```

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini")
res = llm.responses.create(input="1行で自己紹介して")
print(res.output_text)
```

## 期待する結果

実行すると応答が返り、例外が出ないことを確認できれば完了です。

## 次の単元

- `docs/tutolias/02_tracing_basics.md`
