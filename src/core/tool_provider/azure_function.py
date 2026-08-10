"""AzureFunctionToolProvider — executes a Tool by calling its HTTP-triggered Azure Function
(ops/functions/claims_tools/function_app.py), aligning the Tool Layer with CLAUDE.md §4.2/§5
(PBI-06-01, resolves Architecture Review Finding A-03).

Each Tool name maps to POST {base_url}/api/tools/{tool_name}. The Function's own JSON request/
response contract mirrors ToolRequest/ToolResult exactly (see
ops/functions/claims_tools/function_app.py), so this provider is a thin HTTP transport over the
same contract every InProcessToolProvider call already uses — no business logic lives here, and
none is duplicated from the Tool implementations under src/services/tools/.

Every failure mode (timeout, connection error, non-2xx, malformed body) is normalized into
ToolResult(success=False, error=...) — this provider never raises to its caller, matching
ToolExecutor's own contract (src.tools.executor).

Only imported when TOOL_PROVIDER=azure_functions (src.core.tool_provider.factory), so aiohttp
is never required for the default in-process configuration — same lazy-import pattern as
src.llm.factory/src.rag.factory.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from src.domain.secret_provider import SecretProvider
from src.tools.models import ToolRequest, ToolResult

logger = logging.getLogger(__name__)


class AzureFunctionToolProvider:
    """ToolProvider backend that executes each Tool via its HTTP-triggered Azure Function.

    function_key_secret_name is resolved lazily, once, through secret_provider on first
    execute() call — never read directly from the environment here (CLAUDE.md §9 "Secrets").
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 15.0,
        secret_provider: SecretProvider | None = None,
        function_key_secret_name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._secret_provider = secret_provider
        self._function_key_secret_name = function_key_secret_name
        self._function_key: str | None = None
        self._function_key_resolved = False

    async def execute(self, request: ToolRequest) -> ToolResult[Any]:
        try:
            function_key = await self._resolve_function_key()
        except Exception as exc:  # noqa: BLE001 — secret resolution must degrade to a ToolResult
            logger.warning(
                "azure_function_tool_key_error",
                extra={"tool_name": request.tool_name, "correlation_id": request.correlation_id},
            )
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=f"Could not resolve Azure Function key: {exc}",
                correlation_id=request.correlation_id,
            )

        url = f"{self._base_url}/api/tools/{request.tool_name}"
        headers = {"Content-Type": "application/json"}
        if request.correlation_id:
            headers["X-Correlation-ID"] = request.correlation_id
        params = {"code": function_key} if function_key else None
        payload = {
            "tool_input": request.tool_input,
            "correlation_id": request.correlation_id,
            "conversation_id": request.conversation_id,
            "user_id": request.user_id,
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)

        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(url, json=payload, headers=headers, params=params) as response,
            ):
                body = await response.json(content_type=None)
                if response.status >= 400:
                    error = body.get("error") if isinstance(body, dict) else None
                    return ToolResult(
                        tool_name=request.tool_name,
                        success=False,
                        error=error or f"Azure Function returned HTTP {response.status}",
                        correlation_id=request.correlation_id,
                    )
                return ToolResult[Any].model_validate(body)
        except TimeoutError:
            logger.warning(
                "azure_function_tool_timeout",
                extra={"tool_name": request.tool_name, "correlation_id": request.correlation_id},
            )
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error="Azure Function tool call timed out",
                correlation_id=request.correlation_id,
            )
        except (aiohttp.ClientError, ValueError) as exc:
            logger.warning(
                "azure_function_tool_error",
                extra={
                    "tool_name": request.tool_name,
                    "correlation_id": request.correlation_id,
                    "error": str(exc),
                },
            )
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=f"Azure Function tool call failed: {exc}",
                correlation_id=request.correlation_id,
            )

    async def _resolve_function_key(self) -> str | None:
        if self._function_key_resolved:
            return self._function_key
        if self._secret_provider is not None and self._function_key_secret_name is not None:
            self._function_key = await self._secret_provider.get_secret(
                self._function_key_secret_name
            )
        self._function_key_resolved = True
        return self._function_key
