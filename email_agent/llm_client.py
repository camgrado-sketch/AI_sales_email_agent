import json
import os
import re

from openai import OpenAI

from email_agent import config


def _get_client(model_cfg=None):
    """Build an OpenAI-compatible client for the given model config."""
    if model_cfg is None:
        model_cfg = config.get_active_model()
    if not model_cfg:
        raise RuntimeError("No LLM model configured")

    kwargs = {"api_key": model_cfg.get("api_key", "")}
    base_url = model_cfg.get("base_url", "")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _is_moonshot(model_cfg):
    """Check if the configured endpoint is Moonshot."""
    base_url = (model_cfg or {}).get("base_url", "")
    return bool(base_url and "moonshot" in base_url.lower())


def _maybe_extract_json(text):
    """Extract JSON from markdown code block or plain text."""
    if not text:
        return text
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_usage(response):
    """Extract token usage from an OpenAI-style response."""
    usage = response.usage
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def complete(system_prompt, user_prompt, response_format=None, temperature=None, model_name=None):
    """
    Call the configured LLM and return content + usage.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        response_format: Optional OpenAI response_format dict for JSON schema.
        temperature: Sampling temperature (overrides model config).
        model_name: Optional model config name/identifier override.

    Returns:
        {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}}

    Raises:
        RuntimeError: If the API call fails or credentials are missing.
    """
    model_cfg = config.get_active_model()
    if not model_cfg:
        raise RuntimeError("No LLM model configured")
    if model_name:
        for m in config.load_available_models():
            if m.get("name") == model_name or m.get("model") == model_name:
                model_cfg = m
                break

    if not model_cfg.get("api_key"):
        raise RuntimeError("LLM_API_KEY is not set for the active model")

    client = _get_client(model_cfg)

    effective_temperature = temperature if temperature is not None else model_cfg.get("temperature", 0.7)
    # Moonshot API only accepts temperature=1 for some models
    if _is_moonshot(model_cfg):
        effective_temperature = 1.0

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    create_kwargs = {
        "model": model_cfg.get("model"),
        "messages": messages,
        "temperature": effective_temperature,
    }
    # Moonshot does not support json_schema response_format
    if response_format and not _is_moonshot(model_cfg):
        create_kwargs["response_format"] = response_format

    try:
        response = client.chat.completions.create(**create_kwargs)
        content = response.choices[0].message.content
        if content is None:
            content = ""
        return {"content": content, "usage": _extract_usage(response)}
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}") from e


def complete_json(system_prompt, user_prompt, schema, temperature=None, model_name=None):
    """
    Convenience wrapper that forces JSON output via response_format.
    Falls back to prompt-based JSON for Moonshot API.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        schema: JSON schema dict describing the desired output.
        temperature: Sampling temperature.
        model_name: Optional model identifier override.

    Returns:
        {"content": raw_json_str, "usage": dict}
    """
    model_cfg = config.get_active_model()
    if model_name:
        for m in config.load_available_models():
            if m.get("name") == model_name or m.get("model") == model_name:
                model_cfg = m
                break

    if _is_moonshot(model_cfg):
        schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            f"You MUST respond with a JSON object matching this schema:\n{schema_text}\n"
            "Return ONLY the JSON object. Do not wrap it in markdown code blocks."
        )
        result = complete(augmented_system, user_prompt, response_format=None, temperature=temperature, model_name=model_name)
        raw = _maybe_extract_json(result["content"])
        try:
            json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw}") from e
        return {"content": raw, "usage": result["usage"]}

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("name", "response"),
            "strict": True,
            "schema": schema,
        },
    }
    return complete(system_prompt, user_prompt, response_format=response_format, temperature=temperature, model_name=model_name)
