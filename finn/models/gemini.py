"""One Gemini model, explicit per-run budget, versioned cache; no paid fallback."""
from time import monotonic
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import BaseModel

from finn.config import Settings
from finn.domain import fingerprint, utc_now
from finn.storage import Store


class ModelError(RuntimeError):
    pass


class BudgetExceeded(ModelError):
    pass


def provider_schema(schema):
    """Reduce optional-state complexity; retain strict semantic checks in Pydantic."""
    definitions = schema.get("$defs", {})

    def convert(value):
        if isinstance(value, list):
            return [convert(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return convert(definitions[value["$ref"].split("/")[-1]])
        result = {key: convert(item) for key, item in value.items() if key not in {"$defs", "additionalProperties", "title", "default", "format", "minLength", "maxLength", "minimum", "maximum", "maxItems"}}
        if "properties" in result:
            result["required"] = list(result["properties"])
        return result

    return convert(schema)


class Gemini:
    def __init__(self, settings: Settings, store: Store, max_calls: int):
        self.settings, self.store, self.max_calls = settings, store, max_calls
        self.calls, self.cache_hits = 0, 0

    def structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        key = fingerprint({"prompt": prompt, "schema": schema.model_json_schema(), "model": self.settings.gemini_model, "config": "json-temperature0-v3"})
        cached = self.store.get("model-json-v1", key)
        if cached is not None:
            self.cache_hits += 1
            return schema.model_validate(cached)
        if self.calls >= self.max_calls:
            raise BudgetExceeded("Model-call budget reached; remaining documents are explicitly unprocessed")
        if not self.settings.api_key:
            raise ModelError("Configure GEMINI_API_KEY in .env before extraction")
        self.calls += 1
        start = monotonic()
        usage = {"model": self.settings.gemini_model, "created_at": utc_now(), "cache_key": key}
        try:
            with genai.Client(api_key=self.settings.api_key, http_options=types.HttpOptions(timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
                response = client.models.generate_content(model=self.settings.gemini_model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=provider_schema(schema.model_json_schema()), temperature=0, max_output_tokens=8192))
            if not response.text:
                raise ModelError("Gemini returned no structured text")
            result = schema.model_validate_json(response.text)
            usage["status"] = "success"
            usage["tokens"] = response.usage_metadata.model_dump(mode="json") if response.usage_metadata else {}
            self.store.put("model-json-v1", key, result.model_dump(mode="json"))
            return result
        except ModelError:
            usage["status"] = "failed"
            raise
        except Exception as exc:
            usage["status"] = "failed"
            # Provider messages may contain sensitive request details; never forward them.
            code = getattr(exc, "code", None)
            raise ModelError(f"Gemini extraction failed ({type(exc).__name__}, code={code}); check quota, schema or model access") from None
        finally:
            usage["seconds"] = round(monotonic() - start, 3)
            self.store.put("model-usage-v1", uuid4().hex, usage)
