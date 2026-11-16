import os
import time
import requests
from typing import Dict, List, Optional, Any
from src.config import (
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_FALLBACK_MODEL, OPENROUTER_BASE_URL
)

class OpenRouterClient:
    """Handles communication with the OpenRouter LLM API with automated fallbacks and retries."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 12,
    ):
        self.api_key = api_key if api_key else OPENROUTER_API_KEY
        self.model = model if model else OPENROUTER_MODEL
        self.fallback_model = fallback_model if fallback_model else OPENROUTER_FALLBACK_MODEL
        self.base_url = base_url if base_url else OPENROUTER_BASE_URL
        self.timeout = timeout

    def is_configured(self) -> bool:
        """Checks if a valid API key is present."""
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """
        Sends chat completion request to OpenRouter with automatic model fallback.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "OpenRouter API key is not configured in .env.",
                "content": "",
                "model_used": None,
            }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "HTTP-Referer": "https://ashian-spatial-ai.local",
            "X-Title": "Ashian Spatial AI Assistant",
            "Content-Type": "application/json",
        }

        # Try primary model, then fallback model
        models_to_try = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models_to_try.append(self.fallback_model)

        last_error = ""

        for candidate_model in models_to_try:
            payload = {
                "model": candidate_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            for attempt in range(2):
                try:
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout
                    )

                    if response.status_code == 200:
                        data = response.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content", "")
                            return {
                                "success": True,
                                "content": content,
                                "model_used": candidate_model,
                                "raw_data": data,
                            }
                    elif response.status_code in (429, 503):
                        # Rate limit or server busy - wait briefly and retry or try fallback
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        time.sleep(1.5)
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        break
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    time.sleep(1.0)

        return {
            "success": False,
            "error": f"OpenRouter API request failed: {last_error}",
            "content": "",
            "model_used": None,
        }
