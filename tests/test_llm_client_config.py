import requests
import pytest

from src.llm.client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaClient,
    get_default_llm_client,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_ollama_client_uses_default_config(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    client = OllamaClient()

    assert client.base_url == DEFAULT_OLLAMA_BASE_URL
    assert client.model == DEFAULT_OLLAMA_MODEL


def test_ollama_client_accepts_explicit_config():
    client = OllamaClient(base_url="http://example.test:11434/", model="custom-model", timeout=5)

    assert client.base_url == "http://example.test:11434"
    assert client.model == "custom-model"
    assert client.timeout == 5


def test_get_default_llm_client_returns_ollama_client():
    assert isinstance(get_default_llm_client(), OllamaClient)


def test_generate_can_be_mocked_without_network(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(payload={"response": '{"hello": "world"}'})

    monkeypatch.setattr("src.llm.client.requests.post", fake_post)

    client = OllamaClient(base_url="http://localhost:11434", model="llama3.1:8b", timeout=10)
    response = client.generate("Return JSON.", temperature=0.1, system="Be precise.", format_json=True)

    assert response == '{"hello": "world"}'
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 10
    assert captured["json"] == {
        "model": "llama3.1:8b",
        "prompt": "Return JSON.",
        "stream": False,
        "options": {"temperature": 0.1},
        "system": "Be precise.",
        "format": "json",
    }


def test_generate_connection_error_has_helpful_message(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr("src.llm.client.requests.post", fake_post)

    client = OllamaClient(base_url="http://localhost:11434")

    with pytest.raises(RuntimeError) as exc_info:
        client.generate("hello")

    message = str(exc_info.value)
    assert "Could not connect to Ollama at http://localhost:11434" in message
    assert "Make sure Ollama is installed and running" in message


def test_generate_non_200_includes_model_pull_hint(monkeypatch):
    def fake_post(url, json, timeout):
        return FakeResponse(status_code=404, text="model not found")

    monkeypatch.setattr("src.llm.client.requests.post", fake_post)

    client = OllamaClient(model="llama3.1:8b")

    with pytest.raises(RuntimeError) as exc_info:
        client.generate("hello")

    message = str(exc_info.value)
    assert "status 404" in message
    assert "model not found" in message
    assert "ollama pull llama3.1:8b" in message
