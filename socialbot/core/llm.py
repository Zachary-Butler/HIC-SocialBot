"""The one place that calls Claude. Ported from the prototype and brought up to the 1.x SDK. It:
  - asks for structured JSON output (replies always match the schema),
  - caches the system prompt server-side (prompt caching) since it repeats across calls,
  - prices every call from the API's own token counts and config.yaml prices,
  - stops calling once the run's budget is spent,
  - saves every response under data/cache/llm/, so a replay with reuse=True is free and identical,
  - retries a safety refusal once on a fallback model, if one is configured.
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import anthropic


class LLMError(Exception):
    pass


@dataclass
class CallRecord:
    purpose: str                 # "news_triage", "slide_copy", ...
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    reused: bool = False         # answer came from the saved cache: no API call, no cost
    fell_back_from: str = ""     # set when a refusal was retried on the fallback model


class LLM:
    def __init__(self, cfg: dict, reuse: bool = False, client=None):
        self.cfg = cfg
        self.reuse = reuse
        self.calls: list[CallRecord] = []
        self.cache_dir = Path(cfg["paths"]["data_dir"]) / "cache" / "llm"
        self._client = client

    @property
    def client(self):
        if self._client is None:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise LLMError("ANTHROPIC_API_KEY is missing from .env")
            self._client = anthropic.Anthropic()
        return self._client

    @property
    def spent(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def cost(self, model: str, usage) -> float:
        prices = (self.cfg["llm"].get("prices_usd_per_mtok") or {}).get(model)
        if not prices:
            raise LLMError(f"No price for {model} under llm.prices_usd_per_mtok in config.yaml")
        return (usage.input_tokens * prices["input"] + usage.output_tokens * prices["output"]
                + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * prices["cache_write"]
                + (getattr(usage, "cache_read_input_tokens", 0) or 0) * prices["cache_read"]) / 1_000_000

    def json_call(self, purpose: str, model: str, system: str, user: str, schema: dict,
                  max_tokens: int = 16000, effort: str | None = None) -> dict:
        effort = effort or self.cfg["llm"].get("effort")
        output_config = {"format": {"type": "json_schema", "schema": schema}}
        if effort:
            output_config["effort"] = effort
        request = {
            "model": model, "max_tokens": max_tokens,
            # The system prompt is the stable prefix (voice, rules, on-ramps): cache it.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": output_config,
        }
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:32]
        cached = self.cache_dir / f"{key}.json"

        if self.reuse:
            if not cached.exists():
                raise LLMError(f"reuse: no saved {purpose} answer for this exact input. "
                               "Run once live first (or settings/prompts changed since).")
            saved = json.loads(cached.read_text(encoding="utf-8"))
            self.calls.append(CallRecord(purpose=purpose, model=model, reused=True))
            return saved["output"]

        budget = float(self.cfg["llm"]["max_cost_per_run_usd"])
        if self.spent >= budget:
            raise LLMError(f"Run budget of ${budget:.2f} reached; skipping {purpose}")

        response, record = self._create(purpose, request)
        if response.stop_reason == "refusal":
            fallback = self.cfg["llm"].get("fallback_model")
            if fallback and fallback != model:
                response, record = self._create(purpose, {**request, "model": fallback})
                record.fell_back_from = model
            if response.stop_reason == "refusal":
                detail = getattr(getattr(response, "stop_details", None), "category", None) or "unspecified"
                raise LLMError(f"Claude declined the {purpose} request (category: {detail})")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"The {purpose} answer was cut off (max_tokens={max_tokens}); send fewer items per call")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError(f"The {purpose} response had no text block")
        output = json.loads(text)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"purpose": purpose, "model": record.model, "output": output,
                                      "usage": asdict(record)}, ensure_ascii=False), encoding="utf-8")
        return output

    def _create(self, purpose: str, request: dict):
        try:
            response = self.client.messages.create(**request)
        except anthropic.AuthenticationError:
            raise LLMError("Claude API rejected the key; check ANTHROPIC_API_KEY in .env")
        except anthropic.RateLimitError:
            raise LLMError("Claude API rate limit hit; wait a minute and try again")
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            raise LLMError("Couldn't reach the Claude API; check the internet connection")
        u = response.usage
        record = CallRecord(purpose=purpose, model=request["model"], input_tokens=u.input_tokens,
                            output_tokens=u.output_tokens,
                            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                            cost_usd=self.cost(request["model"], u))
        self.calls.append(record)
        return response, record

    def summary(self) -> str:
        live = [c for c in self.calls if not c.reused]
        reused = len(self.calls) - len(live)
        tok_in = sum(c.input_tokens + c.cache_read_tokens + c.cache_write_tokens for c in live)
        tok_out = sum(c.output_tokens for c in live)
        cached = sum(c.cache_read_tokens for c in live)
        return (f"{len(live)} Claude call(s), {tok_in:,} in ({cached:,} from cache) / {tok_out:,} out, "
                f"${self.spent:.3f}" + (f", {reused} reused" if reused else ""))
