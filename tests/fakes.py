"""Stand-ins for external services. No network."""

import json
from types import SimpleNamespace


class FakeClaude:
    """Replaces anthropic.Anthropic(): returns canned JSON answers in order and records requests."""

    def __init__(self, *answers: dict, stop_reason: str = "end_turn", input_tokens: int = 2000,
                 output_tokens: int = 500, cache_read: int = 0):
        self.answers = list(answers)
        self.stop_reason = stop_reason
        self.tokens = (input_tokens, output_tokens, cache_read)
        self.requests: list[dict] = []
        self.messages = self

    def create(self, **request):
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        stop = self.stop_reason if not isinstance(answer, dict) or "__stop__" not in answer else answer["__stop__"]
        body = {k: v for k, v in answer.items() if k != "__stop__"} if isinstance(answer, dict) else answer
        return SimpleNamespace(
            stop_reason=stop,
            stop_details=SimpleNamespace(category="general_harms") if stop == "refusal" else None,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(body))],
            usage=SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1],
                                  cache_creation_input_tokens=0, cache_read_input_tokens=self.tokens[2]))
