"""Compare Gemini models on a question set and save per-request measurements to CSV.

Example:
    uv run python -m app.benchmark --models gemini-3.5-flash-lite gemini-3.1-flash \\
      --questions "LoRAとは？" "RAGとは？" --temperatures 0 0.7 1 \\
      --runs 3 --output benchmark.csv
"""

import argparse
import csv
import time
from pathlib import Path

from google import genai
from google.genai import errors

from app.ask import generate
from app.config import MODEL, api_error_message, get_api_key


def run_benchmark(
    models: list[str],
    questions: list[str],
    output: Path,
    delay_seconds: float = 5.0,
    runs: int = 1,
    temperatures: list[float | None] | None = None,
) -> None:
    client = genai.Client(api_key=get_api_key())
    output.parent.mkdir(parents=True, exist_ok=True)
    temperature_values = temperatures if temperatures is not None else [None]
    columns = [
        "model",
        "question",
        "temperature",
        "run",
        "elapsed_seconds",
        "input_tokens",
        "output_tokens",
        "status",
        "error",
    ]
    request_count = len(models) * len(questions) * len(temperature_values) * runs
    completed = 0
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for model in models:
            for question in questions:
                for temperature in temperature_values:
                    for run in range(1, runs + 1):
                        label = "モデル既定" if temperature is None else temperature
                        print(
                            f"[model] {model} [temperature] {label} "
                            f"[run] {run} [質問] {question}"
                        )
                        try:
                            result = generate(
                                client,
                                question,
                                model=model,
                                temperature=temperature,
                            )
                            writer.writerow(
                                {
                                    "model": model,
                                    "question": question,
                                    "temperature": "" if temperature is None else temperature,
                                    "run": run,
                                    "elapsed_seconds": f"{result.elapsed_seconds:.3f}",
                                    "input_tokens": result.input_tokens,
                                    "output_tokens": result.output_tokens,
                                    "status": "ok",
                                    "error": "",
                                }
                            )
                            print(
                                f"  {result.elapsed_seconds:.2f} 秒 / "
                                f"入力 {result.input_tokens if result.input_tokens is not None else '不明'} / "
                                f"出力 {result.output_tokens if result.output_tokens is not None else '不明'} tokens"
                            )
                            print(f"  {result.text}")
                        except errors.APIError as e:
                            writer.writerow(
                                {
                                    "model": model,
                                    "question": question,
                                    "temperature": "" if temperature is None else temperature,
                                    "run": run,
                                    "elapsed_seconds": "",
                                    "input_tokens": "",
                                    "output_tokens": "",
                                    "status": f"error_{e.code}",
                                    "error": e.message,
                                }
                            )
                            file.flush()
                            print(api_error_message(e.code, e.message))
                            if e.code == 429:
                                print("無料枠などのレート制限に達したため、残りの比較を中止しました。")
                                return
                        file.flush()
                        completed += 1
                        if completed < request_count and delay_seconds:
                            time.sleep(delay_seconds)
    print(f"比較結果: {output}（{completed}/{request_count} 件）")


def main() -> None:
    parser = argparse.ArgumentParser(description="複数モデル・質問の応答時間とトークン数を比較する")
    parser.add_argument(
        "--models",
        nargs="+",
        default=[MODEL],
        help="比較するモデル名（省略時は AIE_MODEL のモデル）",
    )
    parser.add_argument("--questions", nargs="+", required=True, help="比較する質問")
    parser.add_argument("--output", type=Path, default=Path("benchmark.csv"), help="出力 CSV")
    parser.add_argument(
        "--runs", type=int, default=1, help="各モデル・質問の繰り返し回数（既定: 1）"
    )
    parser.add_argument(
        "--temperatures",
        type=float,
        nargs="+",
        help="比較する temperature（省略時はモデル既定値）。対応範囲はモデルごとに異なります",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="API呼び出し間隔（秒、既定: 5）。分あたりの上限を超えにくくするための待機時間",
    )
    args = parser.parse_args()
    if args.delay < 0:
        parser.error("--delay は0以上を指定してください")
    if args.runs < 1:
        parser.error("--runs は1以上を指定してください")
    if args.temperatures and any(
        temperature < 0 or temperature > 2 for temperature in args.temperatures
    ):
        parser.error("--temperatures は0から2の範囲で指定してください")
    run_benchmark(
        args.models,
        args.questions,
        args.output,
        args.delay,
        args.runs,
        args.temperatures,
    )


if __name__ == "__main__":
    main()
