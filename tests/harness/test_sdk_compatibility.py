from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import override

import anyio
from agents import (
    Agent,
    AgentOutputSchemaBase,
    Handoff,
    Model,
    ModelProvider,
    ModelResponse,
    ModelSettings,
    ModelTracing,
    RunConfig,
    Runner,
    Tool,
    Usage,
)
from agents.items import TResponseInputItem, TResponseStreamEvent
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from openai.types.responses.response_prompt_param import ResponsePromptParam


class _OfflineModel(Model):
    @override
    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> ModelResponse:
        del (
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id,
            conversation_id,
            prompt,
        )
        return ModelResponse(
            output=[
                ResponseOutputMessage(
                    id="message-1",
                    content=[
                        ResponseOutputText(
                            annotations=[],
                            logprobs=[],
                            text="offline result",
                            type="output_text",
                        )
                    ],
                    role="assistant",
                    status="completed",
                    type="message",
                )
            ],
            usage=Usage(),
            response_id="response-1",
        )

    @override
    def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        del (
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id,
            conversation_id,
            prompt,
        )
        message = "streaming is not used by this compatibility test"
        raise AssertionError(message)


@dataclass(frozen=True, slots=True)
class _OfflineProvider(ModelProvider):
    model: Model

    @override
    def get_model(self, model_name: str | None) -> Model:
        del model_name
        return self.model


async def _run_offline_agent() -> str:
    agent = Agent[None](name="compatibility", model="offline")
    result = await Runner.run(
        agent,
        "respond without network access",
        run_config=RunConfig(
            model_provider=_OfflineProvider(_OfflineModel()),
            tracing_disabled=True,
        ),
    )
    return result.final_output_as(str, raise_if_incorrect_type=True)


def test_runner_supports_default_usage_with_pinned_openai() -> None:
    # Given the normal SDK context and Usage defaults with an offline provider
    # When Runner executes one model turn
    result = anyio.run(_run_offline_agent)

    # Then the compatible OpenAI client models accept the SDK defaults
    assert result == "offline result"
