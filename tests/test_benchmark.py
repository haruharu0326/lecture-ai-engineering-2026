import csv
from types import SimpleNamespace

from app import benchmark


def test_run_benchmark_writes_measurements(monkeypatch, tmp_path, capsys):
    requests = []
    response = SimpleNamespace(
        text="回答",
        candidates=[],
        usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5
        ),
    )

    class FakeClient:
        def __init__(self, api_key):
            self.models = SimpleNamespace(
                generate_content=lambda **kwargs: requests.append(kwargs) or response
            )

    monkeypatch.setattr(benchmark.genai, "Client", FakeClient)
    monkeypatch.setattr(benchmark, "get_api_key", lambda: "test-key")
    output = tmp_path / "results.csv"

    benchmark.run_benchmark(
        ["model-a"], ["質問"], output, delay_seconds=0, temperatures=[0.7]
    )

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["model"] == "model-a"
    assert rows[0]["question"] == "質問"
    assert rows[0]["temperature"] == "0.7"
    assert rows[0]["input_tokens"] == "10"
    assert rows[0]["output_tokens"] == "5"
    assert rows[0]["status"] == "ok"
    assert requests[0]["config"].temperature == 0.7
    assert "回答" in capsys.readouterr().out
