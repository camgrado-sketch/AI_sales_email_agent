import json
import os
import re

from openai import OpenAI

from email_agent import config


def _get_client():
    kwargs = {}
    if config.LLM_API_KEY:
        kwargs["api_key"] = config.LLM_API_KEY
    if config.LLM_BASE_URL:
        kwargs["base_url"] = config.LLM_BASE_URL
    return OpenAI(**kwargs)


def _is_moonshot():
    return config.LLM_BASE_URL and "moonshot" in config.LLM_BASE_URL


def _maybe_extract_json(text):
    """Extract JSON from markdown code block or plain text."""
    if not text:
        return text
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def complete(system_prompt, user_prompt, response_format=None, temperature=0.7):
    """
    Call the configured LLM and return the text content.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        response_format: Optional OpenAI response_format dict for JSON schema.
        temperature: Sampling temperature.

    Returns:
        The generated message content as a string.

    Raises:
        RuntimeError: If the API call fails or credentials are missing.
    """
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not set in .env")

    client = _get_client()
    # Moonshot API only accepts temperature=1 for some models
    effective_temperature = temperature
    if _is_moonshot():
        effective_temperature = 1.0

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    create_kwargs = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": effective_temperature,
    }
    # Moonshot does not support json_schema response_format
    if response_format and not _is_moonshot():
        create_kwargs["response_format"] = response_format

    try:
        response = client.chat.completions.create(**create_kwargs)
        content = response.choices[0].message.content
        if content is None:
            content = ""
        return content
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}") from e


def complete_json(system_prompt, user_prompt, schema, temperature=0.7):
    """
    Convenience wrapper that forces JSON output via response_format.
    Falls back to prompt-based JSON for Moonshot API.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        schema: JSON schema dict describing the desired output.
        temperature: Sampling temperature.

    Returns:
        Raw JSON string from the model.
    """
    if _is_moonshot():
        schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            f"You MUST respond with a JSON object matching this schema:\n{schema_text}\n"
            "Return ONLY the JSON object. Do not wrap it in markdown code blocks."
        )
        raw = complete(augmented_system, user_prompt, response_format=None, temperature=temperature)
        raw = _maybe_extract_json(raw)
        try:
            json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw}") from e
        return raw

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("name", "response"),
            "strict": True,
            "schema": schema,
        },
    }
    return complete(system_prompt, user_prompt, response_format=response_format, temperature=temperature)
