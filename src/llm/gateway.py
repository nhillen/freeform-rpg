"""
LLM Gateway - Provider-agnostic interface for LLM interactions.

Handles structured output generation with schema validation.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import jsonschema


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    content: dict
    raw_text: str
    model: str
    usage: dict
    latency_ms: float


@dataclass
class LLMError:
    """Error from an LLM call."""
    error_type: str
    message: str
    retryable: bool


class LLMGateway(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def run_structured(
        self,
        prompt: str,
        input_data: dict,
        schema: dict,
        options: Optional[dict] = None
    ) -> LLMResponse:
        """
        Run a prompt with structured output.

        Args:
            prompt: The prompt template with {{placeholders}}
            input_data: Data to inject into placeholders
            schema: JSON schema for output validation
            options: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with parsed content

        Raises:
            LLMError: If the call fails after retries
        """
        pass

    def _render_prompt(self, template: str, data: dict) -> str:
        """Render a prompt template with data."""
        result = template
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2)
            result = result.replace(placeholder, str(value))
        return result

    def _validate_output(self, output: dict, schema: dict) -> None:
        """Validate output against JSON schema."""
        jsonschema.validate(instance=output, schema=schema)


class ClaudeGateway(LLMGateway):
    """Claude API implementation of LLM Gateway."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Import anthropic lazily to allow module to load without it installed
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def run_structured(
        self,
        prompt: str,
        input_data: dict,
        schema: dict,
        options: Optional[dict] = None
    ) -> LLMResponse:
        """Run a prompt and get structured JSON output."""
        options = options or {}

        # Render the prompt template
        rendered_prompt = self._render_prompt(prompt, input_data)

        # Add JSON instruction to system prompt
        system_prompt = (
            "You are an AI assistant that outputs valid JSON only. "
            "Do not include any text before or after the JSON object. "
            "Do not use markdown code blocks. Output raw JSON only."
        )

        # Add schema to prompt
        schema_instruction = f"\n\nYour output must conform to this JSON schema:\n{json.dumps(schema, indent=2)}"
        full_prompt = rendered_prompt + schema_instruction

        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=options.get("max_tokens", 4096),
                    temperature=options.get("temperature", 0.7),
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": full_prompt}
                    ]
                )

                latency_ms = (time.time() - start_time) * 1000

                # Extract text content
                raw_text = response.content[0].text

                # Parse JSON
                try:
                    content = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    # Try to extract JSON from markdown code blocks
                    content = self._extract_json(raw_text)

                # Validate against schema
                self._validate_output(content, schema)

                return LLMResponse(
                    content=content,
                    raw_text=raw_text,
                    model=response.model,
                    usage={
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    },
                    latency_ms=latency_ms
                )

            except jsonschema.ValidationError as e:
                last_error = LLMError(
                    error_type="validation_error",
                    message=f"Output failed schema validation: {e.message}",
                    retryable=True
                )
            except json.JSONDecodeError as e:
                last_error = LLMError(
                    error_type="parse_error",
                    message=f"Failed to parse JSON: {e}",
                    retryable=True
                )
            except Exception as e:
                error_str = str(e)
                retryable = "rate_limit" in error_str.lower() or "timeout" in error_str.lower()
                last_error = LLMError(
                    error_type="api_error",
                    message=error_str,
                    retryable=retryable
                )

            if attempt < self.max_retries - 1 and last_error.retryable:
                time.sleep(self.retry_delay * (attempt + 1))

        raise Exception(f"LLM call failed after {self.max_retries} attempts: {last_error.message}")

    def _extract_json(self, text: str) -> dict:
        """Try to extract JSON from text that might have markdown formatting."""
        # Try to find JSON in code blocks
        import re
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
            r"\{[\s\S]*\}"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    json_str = match.group(1) if "```" in pattern else match.group(0)
                    return json.loads(json_str)
                except (json.JSONDecodeError, IndexError):
                    continue

        raise json.JSONDecodeError("No valid JSON found in response", text, 0)


class MockGateway(LLMGateway):
    """Mock gateway for testing without API calls."""

    def __init__(self, responses: Optional[dict] = None):
        """
        Initialize mock gateway.

        Args:
            responses: Dict mapping prompt substrings to response dicts
        """
        self.responses = responses or {}
        self.call_log: list[dict] = []

    def set_response(self, prompt_contains: str, response: dict) -> None:
        """Set a mock response for prompts containing a string."""
        self.responses[prompt_contains] = response

    def run_structured(
        self,
        prompt: str,
        input_data: dict,
        schema: dict,
        options: Optional[dict] = None
    ) -> LLMResponse:
        """Return mock response based on prompt content."""
        rendered = self._render_prompt(prompt, input_data)

        self.call_log.append({
            "prompt": prompt,
            "input_data": input_data,
            "schema": schema,
            "rendered": rendered
        })

        # Find matching response
        for key, response in self.responses.items():
            if key in rendered:
                self._validate_output(response, schema)
                return LLMResponse(
                    content=response,
                    raw_text=json.dumps(response),
                    model="mock",
                    usage={"input_tokens": 0, "output_tokens": 0},
                    latency_ms=0
                )

        # Return empty response matching schema if no match
        raise Exception(f"No mock response configured for prompt containing: {rendered[:100]}...")


def load_schema(schema_name: str) -> dict:
    """Load a JSON schema from the schemas directory."""
    schema_path = Path(__file__).parent.parent / "schemas" / f"{schema_name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with open(schema_path) as f:
        return json.load(f)


def create_gateway(provider: str = "claude", **kwargs) -> LLMGateway:
    """Factory function to create an LLM gateway."""
    if provider == "claude":
        return ClaudeGateway(**kwargs)
    elif provider == "mock":
        return MockGateway(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
