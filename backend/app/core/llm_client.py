"""
Thin wrapper around the Gemini free tier for structured-output calls.

Every agent goes through generate_structured() instead of calling the
SDK directly, for two reasons:
1. One place to handle retries on rate-limit errors (the free tier's
   per-minute limit is the single biggest reliability risk in this
   project — see README).
2. One place to enforce "response must validate against this Pydantic
   schema or the call is treated as failed", so agents never have to
   hand-parse JSON themselves.
"""

import json
import logging
import time
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.cache import get_cached, set_cached
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/app/apikey and put it in your .env file."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


class AgentCallError(Exception):
    """Raised when an LLM call fails after all retries, or returns output
    that doesn't validate against the expected schema."""


def generate_structured(
    prompt: str,
    response_schema: type[T],
    system_instruction: str | None = None,
    temperature: float = 0.1,
    max_retries: int = 3,
    agent_name: str = "unnamed_agent",
) -> T:
    """
    Calls Gemini and validates the response against response_schema.

    temperature defaults low (0.1) — moderation verdicts should be
    consistent for the same input, not creative.

    Retries only on rate-limit (429) and transient server errors (5xx).
    Does NOT retry on 4xx errors that indicate a bad request (e.g. 400,
    404) — those won't succeed on retry and would just burn free-tier
    quota.

    Checks the Redis cache (app/core/cache.py) before calling Gemini at
    all, keyed on agent_name + the exact prompt + system_instruction —
    see that module for why content-addressed caching is correct here
    in a way that caching by item ID wouldn't be. A cache hit skips the
    network call entirely; a miss calls Gemini as before and stores the
    result before returning it. Caching is best-effort: any cache
    read/write failure is swallowed by app/core/cache.py itself and
    treated as a miss, never as a reason to fail the request.
    """
    cache_key_parts = (prompt,)
    cached = get_cached(agent_name, response_schema, system_instruction or "", *cache_key_parts)
    if cached is not None:
        return cached

    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=response_schema.model_json_schema(),
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=config,
            )
            raw_text = response.text
            if raw_text is None:
                raise AgentCallError("Gemini returned an empty response (no text content).")

            parsed_json = json.loads(raw_text)
            result = response_schema.model_validate(parsed_json)
            set_cached(agent_name, result, system_instruction or "", *cache_key_parts)
            return result

        except genai_errors.APIError as exc:
            last_error = exc
            is_retryable = exc.code == 429 or (exc.code is not None and 500 <= exc.code < 600)
            if not is_retryable or attempt == max_retries:
                raise AgentCallError(f"Gemini API call failed (code={exc.code}): {exc.message}") from exc
            # Simple exponential backoff — free tier rate limits reset
            # quickly, so this doesn't need to be sophisticated.
            wait_seconds = 2 ** attempt
            logger.warning("Gemini call rate-limited/failed (attempt %d/%d), retrying in %ds", attempt, max_retries, wait_seconds)
            time.sleep(wait_seconds)

        except (json.JSONDecodeError, ValidationError) as exc:
            # The model didn't return valid/schema-conformant JSON. This is
            # rare with response_json_schema enforced server-side, but not
            # impossible — retrying often resolves it since it's usually a
            # one-off formatting slip, not a systematic problem.
            last_error = exc
            if attempt == max_retries:
                raise AgentCallError(f"Gemini response failed schema validation after {max_retries} attempts: {exc}") from exc
            logger.warning("Gemini response failed validation (attempt %d/%d): %s", attempt, max_retries, exc)

    # Should be unreachable, but keeps type checkers happy and fails loudly
    # instead of silently returning None if the loop logic above ever changes.
    raise AgentCallError(f"Gemini call failed after {max_retries} attempts: {last_error}")
