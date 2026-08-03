import os

from openai import OpenAI

from email_agent import config


def _get_client():
    kwargs = {}
    if config.LLM_API_KEY:
        kwargs["api_key"] = config.LLM_API_KEY
    if config.LLM_BASE_URL:
        kwargs["base_url"] = config.LLM_BASE_URL
    return OpenAI(**kwargs)


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
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}") from e


def complete_json(system_prompt, user_prompt, schema, temperature=0.7):
    """
    Convenience wrapper that forces JSON output via response_format.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        schema: JSON schema dict describing the desired output.
        temperature: Sampling temperature.

    Returns:
        Raw JSON string from the model.
    """
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("name", "response"),
            "strict": True,
            "schema": schema,
        },
    }
    return complete(system_prompt, user_prompt, response_format=response_format, temperature=temperature)
