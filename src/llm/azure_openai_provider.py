"""AzureOpenAIProvider: production-shaped Azure OpenAI adapter.

Prefers Microsoft Entra ID (DefaultAzureCredential) authentication, since the `openai` SDK's
AsyncAzureOpenAI client natively supports it via azure_ad_token_provider. API-key auth, if
explicitly enabled via configuration, is obtained only through the existing SecretProvider
abstraction — never read directly from os.environ here.

Never exercised by the test suite against real Azure — MockLLMProvider is the default and
only provider the tests actually call (see src/llm/factory.py). This file is the only place
in the codebase that imports the openai/azure-identity SDKs.
"""

from __future__ import annotations

from typing import cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam

from src.domain.secret_provider import SecretProvider
from src.llm.exceptions import (
    LLMConfigurationError,
    LLMContentSafetyError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.llm.models import LLMRequest, LLMResponse, LLMUsage

_PROVIDER_NAME = "azure_openai"
_ENTRA_ID_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIProvider:
    """LLMProvider implementation backed by Azure OpenAI."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        secret_provider: SecretProvider | None = None,
        api_key_secret_name: str | None = None,
    ) -> None:
        if not endpoint:
            raise LLMConfigurationError(
                "AZURE_OPENAI_ENDPOINT must be set for the azure_openai provider"
            )
        if not deployment:
            raise LLMConfigurationError(
                "AZURE_OPENAI_DEPLOYMENT must be set for the azure_openai provider"
            )

        self._endpoint = endpoint
        self._deployment = deployment
        self._api_version = api_version
        self._secret_provider = secret_provider
        self._api_key_secret_name = api_key_secret_name
        self._client: AsyncAzureOpenAI | None = None
        self._credential_close: object | None = None

    async def _get_client(self) -> AsyncAzureOpenAI:
        if self._client is not None:
            return self._client

        if self._secret_provider is not None and self._api_key_secret_name:
            api_key = await self._secret_provider.get_secret(self._api_key_secret_name)
            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._endpoint,
                api_key=api_key,
                api_version=self._api_version,
            )
        else:
            from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            self._credential_close = credential
            token_provider = get_bearer_token_provider(credential, _ENTRA_ID_SCOPE)
            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self._api_version,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential_close is not None:
            await self._credential_close.close()  # type: ignore[attr-defined]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = await self._get_client()
        model = request.settings.model or self._deployment

        try:
            # cast: request.messages' role is typed as str (from LLMMessageRole.value), so
            # mypy cannot structurally narrow these dicts to the specific TypedDict variant
            # openai's SDK expects per role. The values are always one of "system"/"user"/
            # "assistant", which are all valid roles for this call — verified at runtime by
            # LLMMessageRole's own enum membership, not asserted blindly here.
            messages = cast(
                "list[ChatCompletionMessageParam]",
                [
                    {"role": message.role.value, "content": message.content}
                    for message in request.messages
                ],
            )
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.settings.temperature,
                max_tokens=request.settings.max_output_tokens,
                timeout=request.settings.timeout_seconds,
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError(_PROVIDER_NAME) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(_PROVIDER_NAME, str(exc)) from exc
        except APIConnectionError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except APIStatusError as exc:
            if "content_filter" in str(exc).lower():
                raise LLMContentSafetyError(_PROVIDER_NAME, str(exc)) from exc
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc

        choice = completion.choices[0]
        usage = completion.usage
        return LLMResponse(
            text=choice.message.content or "",
            model=completion.model,
            usage=LLMUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            correlation_id=request.correlation_id,
        )
