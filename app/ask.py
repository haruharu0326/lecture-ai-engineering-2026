"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask --chat     # 会話履歴を保って続けて質問する
    uv run python -m app.ask            # 講座に固有の質問を1回する

ツールを持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors
from google.genai import types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


@dataclass
class Generation:
    text: str
    elapsed_seconds: float
    input_tokens: int | None
    output_tokens: int | None


def generate(
    client: genai.Client,
    question: str,
    model: str = MODEL,
    history: list[types.Content] | None = None,
    temperature: float | None = None,
) -> Generation:
    """Generate one response and append a successful turn to the optional history."""
    conversation = history if history is not None else []
    user_message = types.Content(
        role="user", parts=[types.Part.from_text(text=question)]
    )
    request = {"model": model, "contents": [*conversation, user_message]}
    if temperature is not None:
        request["config"] = types.GenerateContentConfig(temperature=temperature)
    started_at = time.perf_counter()
    response = client.models.generate_content(**request)
    elapsed_seconds = time.perf_counter() - started_at
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else None
    output_tokens = usage.candidates_token_count if usage else None
    text = response.text or ""

    if history is not None:
        history.append(user_message)
        candidate_content = response.candidates[0].content if response.candidates else None
        history.append(
            candidate_content
            or types.Content(role="model", parts=[types.Part.from_text(text=text)])
        )

    return Generation(text, elapsed_seconds, input_tokens, output_tokens)


def ask(
    question: str,
    history: list[types.Content] | None = None,
    model: str = MODEL,
    client: genai.Client | None = None,
) -> str:
    client = client or genai.Client(api_key=get_api_key())
    result = generate(client, question, model=model, history=history)
    print(f"[time] 応答時間: {result.elapsed_seconds:.2f} 秒")
    print(
        f"[usage] 入力トークン数: {result.input_tokens if result.input_tokens is not None else '不明'}, "
        f"出力トークン数: {result.output_tokens if result.output_tokens is not None else '不明'}"
    )
    return result.text


def run_chat() -> None:
    """Read prompts until EOF or an explicit quit command, keeping turns in memory."""
    client = genai.Client(api_key=get_api_key())
    history: list[types.Content] = []
    print("会話を開始します。終了するには exit または quit を入力してください。")
    while True:
        try:
            question = input("\n質問> ").strip()
        except EOFError:
            print()
            break
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        try:
            print(ask(question, history=history, client=client))
        except errors.APIError as e:
            print(api_error_message(e.code, e.message))


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?", help="質問（省略時は既定の質問を1回実行）")
    parser.add_argument("--chat", action="store_true", help="会話履歴を保って対話する")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.chat:
        if args.question:
            parser.error("--chat と質問の引数は同時に指定できません")
        try:
            run_chat()
        except errors.APIError as e:
            print(api_error_message(e.code, e.message))
            raise SystemExit(1)
        return

    question = args.question or DEFAULT_QUESTION
    print(f"[質問] {question}\n")
    try:
        print(ask(question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
