from tradingagents.llm_clients.openai_client import OpenAIClient


def test_aicode_uses_chat_completions_not_responses(monkeypatch):
    monkeypatch.setenv("AICODE_API_KEY", "aicode-key")

    llm = OpenAIClient("gpt-5.5", provider="aicode").get_llm()

    assert llm.model_name == "gpt-5.5"
    assert str(llm.openai_api_base) == "https://aicode.cat"
    assert getattr(llm, "use_responses_api", None) is None
    assert llm.streaming is True


def test_aicode_api_key_falls_back_to_openai_api_key(monkeypatch):
    monkeypatch.delenv("AICODE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-compatible-key")

    llm = OpenAIClient("gpt-5.5", provider="aicode").get_llm()

    assert llm.openai_api_key.get_secret_value() == "openai-compatible-key"


def test_aicode_requires_api_key(monkeypatch):
    monkeypatch.delenv("AICODE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        OpenAIClient("gpt-5.5", provider="aicode").get_llm()
    except ValueError as error:
        assert "AICODE_API_KEY" in str(error)
    else:
        raise AssertionError("Expected missing aicode API key error")


def test_aicode_allows_streaming_override(monkeypatch):
    monkeypatch.setenv("AICODE_API_KEY", "aicode-key")

    llm = OpenAIClient("gpt-5.5", provider="aicode", streaming=False).get_llm()

    assert llm.streaming is False
