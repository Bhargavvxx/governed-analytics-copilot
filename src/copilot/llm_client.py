"""
LLM client abstraction -- provider-agnostic wrapper.

Supported providers:
  mock      -- echo back the prompt (for tests / offline dev)
  openai    -- OpenAI ChatCompletion (gpt-4o-mini default)
  anthropic -- Anthropic Messages (claude-3-haiku default)

Configuration is read from Settings (env / .env).
"""
from __future__ import annotations

from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
_ANTHROPIC_DEFAULT_MODEL = "claude-3-haiku-20240307"



def _call_mock(prompt: str) -> str:
    logger.info("LLM mock mode -- returning echo")
    return f"[MOCK] {prompt[:200]}"



def _call_openai(prompt: str) -> str:
    """Call OpenAI ChatCompletion API."""
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "openai_api_key is not set.  "
            "Set OPENAI_API_KEY in your .env file or environment."
        )

    try:
        import openai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "The 'openai' package is not installed.  "
            "Run: pip install openai"
        ) from exc

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=_OPENAI_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful analytics assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=512,
    )
    text = response.choices[0].message.content or ""
    logger.info("OpenAI response (%d chars)", len(text))
    return text



def _call_anthropic(prompt: str) -> str:
    """Call Anthropic Messages API."""
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        raise RuntimeError(
            "anthropic_api_key is not set.  "
            "Set ANTHROPIC_API_KEY in your .env file or environment."
        )

    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "The 'anthropic' package is not installed.  "
            "Run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=_ANTHROPIC_DEFAULT_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else ""
    logger.info("Anthropic response (%d chars)", len(text))
    return text



_PROVIDERS: dict[str, Any] = {
    "mock": _call_mock,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
}


def call_llm(prompt: str, provider: str | None = None) -> str:
    """Send *prompt* to the configured (or overridden) LLM provider.

    Parameters
    ----------
    prompt : str
        The full prompt text.
    provider : str, optional
        Override the provider from settings.  One of: mock, openai, anthropic.
    """
    if provider is None:
        provider = get_settings().llm_provider.lower()

    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise NotImplementedError(
            f"LLM provider '{provider}' is not supported.  "
            f"Choose from: {', '.join(_PROVIDERS)}"
        )

    logger.info("Calling LLM provider=%s  prompt_len=%d", provider, len(prompt))
    return fn(prompt)
