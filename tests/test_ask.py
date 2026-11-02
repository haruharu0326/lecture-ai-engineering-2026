from types import SimpleNamespace

from app import ask
from google.genai import types


def test_ask_prints_input_and_output_token_counts(monkeypatch, capsys):
    response = SimpleNamespace(
        text="回答",
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=8),
    )

    class FakeClient:
        def __init__(self, api_key):
            self.models = SimpleNamespace(generate_content=lambda **kwargs: response)

    monkeypatch.setattr(ask.genai, "Client", FakeClient)
    monkeypatch.setattr(ask, "get_api_key", lambda: "test-key")

    assert ask.ask("質問") == "回答"
    assert "[usage] 入力トークン数: 12, 出力トークン数: 8" in capsys.readouterr().out


def test_generate_preserves_conversation_history():
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            text = f"回答{len(calls)}"
            return SimpleNamespace(
                text=text,
                candidates=[
                    SimpleNamespace(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text=text)]
                        )
                    )
                ],
                usage_metadata=None,
            )

    history = []
    client = SimpleNamespace(models=FakeModels())
    ask.generate(client, "最初の質問", history=history)
    result = ask.generate(client, "続きの質問", history=history)

    assert result.text == "回答2"
    assert [part.role for part in calls[1]["contents"]] == [
        "user",
        "model",
        "user",
    ]
    assert len(history) == 4


def test_generate_passes_temperature_to_api():
    requests = []

    class FakeModels:
        def generate_content(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(text="回答", candidates=[], usage_metadata=None)

    ask.generate(SimpleNamespace(models=FakeModels()), "質問", temperature=0.7)

    assert requests[0]["config"].temperature == 0.7
