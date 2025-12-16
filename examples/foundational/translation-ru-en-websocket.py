#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Real-time Russian to English translation pipeline.

This example demonstrates a low-latency, duplex translation pipeline that:
- Transcribes Russian speech to text using Deepgram STT
- Translates Russian text to English using OpenAI's fastest model
- Synthesizes English speech using Deepgram TTS
- Runs over WebSocket for local deployment

The pipeline is optimized for minimal latency:
- Interim transcription results trigger immediate translation
- No artificial silence timers or waiting periods
- True duplex mode: user and bot can speak simultaneously
"""

import os

from deepgram import LiveOptions
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContext,
    LLMContextAggregatorPair,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

load_dotenv(override=True)


# Transport configuration for different deployment scenarios
# Stores factory functions to avoid early instantiation
# VAD configured with minimal stop_secs for low latency
transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.1)),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.1)),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.1)),
    ),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    """Set up and run the Russian-to-English translation pipeline."""
    logger.info("Starting Russian-to-English translation bot")

    # Configure Deepgram STT for Russian input
    # - Language set to Russian (ru)
    # - Interim results enabled for immediate processing
    # - Smart format disabled to reduce latency
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        live_options=LiveOptions(
            language="ru",  # Russian input
            interim_results=True,  # Enable streaming partial transcripts
            smart_format=False,  # Disable to reduce latency
            punctuate=False,  # Disable to reduce latency
            model="nova-3-general",  # Latest general-purpose model
        ),
    )

    # Configure Deepgram TTS for English output
    # - Using fast streaming voice
    tts = DeepgramTTSService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        voice="aura-2-helios-en",  # English voice
    )

    # Configure OpenAI LLM for translation
    # - Use fastest available model (configurable via env var)
    # - Model defaults to gpt-4o-mini for speed, but can be overridden
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),  # Fast, cost-effective model
    )

    # System message instructs the LLM to translate Russian to English
    # - Focus on speed and accuracy
    # - Avoid adding extra commentary
    messages = [
        {
            "role": "system",
            "content": "You are a real-time Russian to English translator. Your job is to translate Russian speech to English as quickly and accurately as possible. Translate ONLY what the user says, without adding commentary or explanations. Maintain the meaning and tone of the original message. Output natural, fluent English. Be concise and direct. Do not use special characters that can't be spoken.",
        },
    ]

    # Set up LLM context and aggregators for conversation management
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    # Build the translation pipeline
    # Flow: Audio In → STT (Russian) → LLM (Translate) → TTS (English) → Audio Out
    pipeline = Pipeline(
        [
            transport.input(),  # Receive audio from user
            stt,  # Transcribe Russian speech to text
            context_aggregator.user(),  # Add user text to conversation context
            llm,  # Translate Russian text to English
            tts,  # Synthesize English speech
            transport.output(),  # Send audio to user
            context_aggregator.assistant(),  # Add assistant response to context
        ]
    )

    # Create pipeline task with metrics enabled for monitoring
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        """Handle new client connections."""
        logger.info("Client connected to translation service")
        # Send initial greeting in English
        context.add_message(
            {
                "role": "system",
                "content": "Greet the user and let them know you will translate their Russian speech to English.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        """Handle client disconnections."""
        logger.info("Client disconnected")
        await task.cancel()

    # Run the pipeline
    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
