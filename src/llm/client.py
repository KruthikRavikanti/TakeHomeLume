from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ):
        load_dotenv()
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        system: str | None = None,
        format_json: bool = False,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if system is not None:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        endpoint = f"{self.base_url}/api/generate"
        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Make sure Ollama is installed and running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"Ollama request timed out after {self.timeout} seconds.") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama request failed with status {response.status_code}: {response.text}\n"
                f"Model {self.model} may not be installed. Run: ollama pull {self.model}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Ollama returned a non-JSON response.") from exc

        if "response" not in data:
            raise RuntimeError('Ollama response JSON did not contain a "response" field.')

        return str(data["response"])


def get_default_llm_client() -> OllamaClient:
    return OllamaClient()
