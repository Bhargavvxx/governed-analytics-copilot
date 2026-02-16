"""
Unit tests -- LLM client: mock mode + dispatch.
"""
import pytest
from src.copilot.llm_client import call_llm


def test_mock_returns_string():
    result = call_llm("Hello world", provider="mock")
    assert isinstance(result, str)


def test_mock_prefix():
    result = call_llm("Hello world", provider="mock")
    assert result.startswith("[MOCK]")


def test_mock_echoes_prompt():
    prompt = "What is the meaning of life?"
    result = call_llm(prompt, provider="mock")
    assert prompt[:20] in result


def test_unknown_provider_raises():
    with pytest.raises(NotImplementedError, match="not supported"):
        call_llm("hi", provider="banana")


def test_openai_missing_key_raises():
    """Should raise RuntimeError when key is empty."""
    with pytest.raises(RuntimeError, match="openai_api_key"):
        call_llm("hi", provider="openai")


def test_anthropic_missing_key_raises():
    """Should raise RuntimeError when key is empty."""
    with pytest.raises(RuntimeError, match="anthropic_api_key"):
        call_llm("hi", provider="anthropic")


def test_default_provider_is_mock():
    """Settings default to mock -- this should work without any keys."""
    result = call_llm("test")
    assert "[MOCK]" in result
