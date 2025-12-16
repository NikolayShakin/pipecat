# Real-Time Russian to English Translation Pipeline

This example demonstrates a low-latency, duplex translation pipeline for real-time Russian to English speech translation over WebSocket.

## Features

- **Real-time translation**: Translates Russian speech to English with minimal latency
- **True duplex mode**: User and bot can speak simultaneously
- **Streaming processing**: Interim transcription results trigger immediate translation
- **WebSocket transport**: Designed for local deployment and easy client integration
- **Optimized for speed**: No artificial timers or delays

## Architecture

The pipeline processes audio in the following flow:

```
User Audio (Russian) 
  ↓
Deepgram STT (Russian transcription)
  ↓
OpenAI LLM (Russian → English translation)
  ↓
Deepgram TTS (English synthesis)
  ↓
Bot Audio (English)
```

## Prerequisites

1. **Python 3.10+** (Python 3.12 recommended)
2. **API Keys**:
   - Deepgram API key for STT and TTS
   - OpenAI API key for LLM translation

## Installation

1. Install Pipecat with required dependencies:

```bash
# Using uv (recommended)
uv add "pipecat-ai[deepgram,openai,runner]"

# Or using pip
pip install "pipecat-ai[deepgram,openai,runner]"
```

2. Set up environment variables:

Create a `.env` file in your project directory:

```bash
# Required
DEEPGRAM_API_KEY=your_deepgram_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional - override the default model
OPENAI_MODEL=gpt-4o-mini  # Default: gpt-4o-mini (fastest)
```

## Running the Example

### Local WebSocket Server

Run the translation service as a local WebSocket server:

```bash
python translation-ru-en-websocket.py -t webrtc
```

The server will start and display connection information:
- Default host: `localhost`
- Default port: `8765`
- WebSocket URL: `ws://localhost:8765`

### Daily.co (WebRTC)

For cloud deployment with Daily.co:

```bash
python translation-ru-en-websocket.py -t daily
```

This will create a temporary Daily room for testing.

## Connecting a Client

### JavaScript/Browser Client

```javascript
// Connect to the WebSocket server
const ws = new WebSocket('ws://localhost:8765');

// Get user's microphone
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const mediaRecorder = new MediaRecorder(stream);

// Send audio data to the server
mediaRecorder.ondataavailable = (event) => {
  if (event.data.size > 0) {
    ws.send(event.data);
  }
};

// Receive translated audio from the server
ws.onmessage = (event) => {
  // Play the received audio
  const audioBlob = new Blob([event.data], { type: 'audio/raw' });
  // ... decode and play audio
};

mediaRecorder.start(100); // Send audio chunks every 100ms
```

### Python Client

```python
import asyncio
import websockets
import pyaudio

async def translation_client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Set up audio input/output
        audio = pyaudio.PyAudio()
        
        # Stream Russian audio to the server
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        
        while True:
            data = stream.read(1024)
            await websocket.send(data)
            
            # Receive and play English audio
            response = await websocket.recv()
            # ... play response audio

asyncio.run(translation_client())
```

## Latency Optimization

This example implements several techniques to minimize latency:

### 1. Interim Transcription Results
```python
DeepgramSTTService(
    live_options=LiveOptions(
        interim_results=True,  # Process partial transcripts immediately
    )
)
```

Partial transcripts are sent to the LLM as soon as they're available, rather than waiting for complete utterances.

### 2. Disabled Processing Delays
```python
DeepgramSTTService(
    live_options=LiveOptions(
        smart_format=False,   # No post-processing delay
        punctuate=False,      # No punctuation analysis delay
    )
)
```

Smart formatting and punctuation add latency. For real-time translation, we prioritize speed over formatting.

### 3. Minimal VAD Buffering
```python
TransportParams(
    vad_analyzer=SileroVADAnalyzer(
        params=VADParams(stop_secs=0.1)  # Minimal silence threshold
    )
)
```

VAD (Voice Activity Detection) is configured with minimal `stop_secs` (0.1 seconds) to detect speech boundaries quickly while maintaining duplex operation.

### 4. No Additional Timers

Beyond the minimal VAD configuration, the pipeline doesn't use additional silence detection timers or end-of-utterance delays. Translation begins immediately when text is available.

### 5. Streaming LLM

OpenAI's streaming API is used to start speaking translated text as soon as the first tokens are generated, rather than waiting for the complete translation.

### 6. True Duplex Operation

The pipeline is configured for full-duplex audio:
- User audio is continuously processed while the bot is speaking
- Bot audio continues while the user is speaking
- No turn-taking or blocking behavior

## Configuration Options

### Change Translation Model

For even faster translation (with potentially lower quality):

```bash
OPENAI_MODEL=gpt-4o-mini  # Fastest (default)
```

For higher quality translation (with slightly higher latency):

```bash
OPENAI_MODEL=gpt-4o       # More capable
```

### Change TTS Voice

Edit the example to use a different English voice:

```python
tts = DeepgramTTSService(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    voice="aura-2-helios-en",  # Male voice
    # or "aura-2-helena-en"    # Female voice
    # or "aura-2-andromeda-en" # Female voice
)
```

### Change STT Model

For improved Russian transcription accuracy:

```python
stt = DeepgramSTTService(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    live_options=LiveOptions(
        language="ru",
        model="nova-3-general",  # Latest general model (default)
        # or "nova-2-general"    # Previous generation
    ),
)
```

## Troubleshooting

### "Module not found" errors

Make sure you've installed all required dependencies:

```bash
pip install "pipecat-ai[deepgram,openai,runner]"
```

### High latency

1. Check your network connection to Deepgram and OpenAI
2. Try using a faster OpenAI model (e.g., `gpt-4o-mini`)
3. Ensure `interim_results=True` in STT configuration
4. Verify that `smart_format=False` and `punctuate=False` in STT

### Audio quality issues

1. Try a different Deepgram voice model
2. Increase the audio sample rate if your client supports it
3. Check that audio is being transmitted at consistent intervals

### Translation accuracy issues

1. Upgrade to a more capable model: `OPENAI_MODEL=gpt-4o`
2. Modify the system prompt to provide more context
3. Try Deepgram's `nova-3-general` STT model for better transcription

## Technical Details

### Audio Format

- **Input**: 16-bit PCM, mono, 16kHz (recommended)
- **Output**: 16-bit PCM, mono, 24kHz (Deepgram TTS default)

### Supported Transports

The example works with multiple transport types:

- **WebRTC** (`-t webrtc`): Local WebRTC server with browser client
- **Daily** (`-t daily`): Cloud WebRTC via Daily.co
- **Twilio** (`-t twilio`): Phone integration via Twilio

### Dependencies

- `pipecat-ai[deepgram]`: Deepgram STT and TTS services
- `pipecat-ai[openai]`: OpenAI LLM service
- `pipecat-ai[runner]`: Development runner and transport infrastructure

## Performance Characteristics

- **Average end-to-end latency**: ~500-800ms (network dependent)
- **STT latency**: ~100-200ms (interim results)
- **LLM latency**: ~200-400ms (streaming)
- **TTS latency**: ~100-200ms (streaming)

## License

BSD 2-Clause License (see LICENSE file)

## Support

- [Pipecat Documentation](https://docs.pipecat.ai)
- [Pipecat Discord](https://discord.gg/pipecat)
- [GitHub Issues](https://github.com/pipecat-ai/pipecat/issues)
