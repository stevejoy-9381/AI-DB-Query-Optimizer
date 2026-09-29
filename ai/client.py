"""
ai/client.py
Provider-agnostic LLM client interface and implementations for Gemini and OpenAI.
API keys are loaded exclusively from environment variables or st.secrets, never hardcoded.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _get_secret_key(key_name: str) -> str | None:
    """Retrieve secret key from os.environ or streamlit secrets if available."""
    # 1. Environment variable
    val = os.getenv(key_name)
    if val:
        return val.strip()

    # 2. Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key_name in st.secrets:
            return str(st.secrets[key_name]).strip()
    except Exception:
        pass

    return None


class LLMClient(ABC):
    """Abstract provider-agnostic interface for LLM operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider and model."""
        pass

    @abstractmethod
    def generate(self, prompt: str, timeout_seconds: int = 10) -> str:
        """Execute text generation against the LLM provider.

        Args:
            prompt: Text prompt to send to the LLM.
            timeout_seconds: Request timeout in seconds.

        Returns:
            Raw response text from the LLM.

        Raises:
            RuntimeError: If provider request fails or times out.
        """
        pass


class GeminiLLMClient(LLMClient):
    """Google Gemini LLM client via Generative Language REST API."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key or _get_secret_key("GEMINI_API_KEY") or _get_secret_key("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key not found in GEMINI_API_KEY or GOOGLE_API_KEY.")
        self.model = model

    @property
    def name(self) -> str:
        return f"Gemini ({self.model})"

    def generate(self, prompt: str, timeout_seconds: int = 10) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned empty candidate response.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini response missing content parts.")
            return parts[0].get("text", "")
        except requests.RequestException as e:
            logger.error("Gemini API request failed: %s", e)
            raise RuntimeError(f"Gemini API request error: {e}") from e


class OpenAILLMClient(LLMClient):
    """OpenAI LLM client via Chat Completions REST API."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or _get_secret_key("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found in OPENAI_API_KEY.")
        self.model = model

    @property
    def name(self) -> str:
        return f"OpenAI ({self.model})"

    def generate(self, prompt: str, timeout_seconds: int = 10) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a MySQL database performance expert. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI returned no choices.")
            return choices[0].get("message", {}).get("content", "")
        except requests.RequestException as e:
            logger.error("OpenAI API request failed: %s", e)
            raise RuntimeError(f"OpenAI API request error: {e}") from e


class MockLLMClient(LLMClient):
    """Deterministic mock client for testing valid, invalid, and malicious LLM responses."""

    def __init__(self, response_text: str | None = None, name: str = "MockLLM") -> None:
        self._response_text = response_text
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def set_response(self, text: str) -> None:
        self._response_text = text

    def generate(self, prompt: str, timeout_seconds: int = 10) -> str:
        if self._response_text is None:
            return json.dumps({
                "explanation": "Mock LLM analysis: Query is performing well.",
                "issues": ["SELECT * detected"],
                "suggested_query": "SELECT id, name FROM users WHERE id = 1;",
                "suggested_indexes": ["CREATE INDEX idx_users_id ON users(id);"],
                "confidence": 0.95,
            })
        return self._response_text


def get_llm_client(provider: str | None = None) -> LLMClient | None:
    """
    Factory to return an initialized LLM client based on requested provider or available keys.

    Provider resolution order:
    1. Explicit provider argument ('gemini', 'openai', 'mock')
    2. Environment variable / secret `LLM_PROVIDER`
    3. Auto-detection: Gemini if GEMINI_API_KEY present, else OpenAI if OPENAI_API_KEY present.
    """
    selected = (provider or os.getenv("LLM_PROVIDER") or "").strip().lower()

    if selected == "mock":
        return MockLLMClient()

    if selected in ("gemini", "google"):
        try:
            return GeminiLLMClient()
        except ValueError:
            return None

    if selected in ("openai", "gpt"):
        try:
            return OpenAILLMClient()
        except ValueError:
            return None

    # Auto-detection
    if _get_secret_key("GEMINI_API_KEY") or _get_secret_key("GOOGLE_API_KEY"):
        try:
            return GeminiLLMClient()
        except ValueError:
            pass

    if _get_secret_key("OPENAI_API_KEY"):
        try:
            return OpenAILLMClient()
        except ValueError:
            pass

    return None
