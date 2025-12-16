#!/usr/bin/env python
"""Simple test client for the Russian to English translation example.

This script demonstrates how to connect to the translation WebSocket server
and test the translation pipeline. It can be used as a starting point for
building a real client application.

Note: This is a basic example. For production use, consider using the
Pipecat client SDKs available for JavaScript, React, iOS, Android, etc.
"""

import asyncio
import sys
import wave
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Error: websockets package not found.")
    print("Install with: pip install websockets")
    sys.exit(1)


async def test_translation_client(
    server_url: str = "ws://localhost:8765",
    audio_file: str = None,
):
    """Connect to the translation server and test audio streaming.
    
    Args:
        server_url: WebSocket URL of the translation server
        audio_file: Optional path to a WAV file to stream (for testing)
    """
    print(f"Connecting to translation server at {server_url}...")
    
    try:
        async with websockets.connect(server_url) as websocket:
            print("✓ Connected to translation server")
            print("  The server will translate Russian speech to English")
            print("  Press Ctrl+C to disconnect")
            print()
            
            if audio_file:
                # If an audio file is provided, stream it to the server
                await stream_audio_file(websocket, audio_file)
            else:
                # Otherwise, just keep the connection open
                print("Note: This test client doesn't capture microphone audio.")
                print("To test with real audio, you'll need to:")
                print("1. Use the Pipecat client SDKs (JavaScript, React, etc.)")
                print("2. Or modify this script to capture microphone audio with pyaudio")
                print()
                
                # Keep connection alive and receive any audio responses
                try:
                    while True:
                        message = await websocket.recv()
                        print(f"Received {len(message)} bytes from server")
                except asyncio.CancelledError:
                    pass
                    
    except websockets.exceptions.ConnectionRefused:
        print(f"✗ Connection refused. Is the server running at {server_url}?")
        print()
        print("Start the server with:")
        print("  python translation-ru-en-websocket.py -t webrtc")
        return 1
    except KeyboardInterrupt:
        print("\n\n✓ Disconnected from server")
        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


async def stream_audio_file(websocket, audio_file_path: str):
    """Stream a WAV file to the server for testing.
    
    Args:
        websocket: WebSocket connection
        audio_file_path: Path to WAV file to stream
    """
    path = Path(audio_file_path)
    if not path.exists():
        print(f"✗ Audio file not found: {audio_file_path}")
        return
        
    print(f"Streaming audio from {audio_file_path}...")
    
    try:
        with wave.open(str(path), 'rb') as wav:
            params = wav.getparams()
            print(f"  Format: {params.nchannels} channel(s), "
                  f"{params.sampwidth * 8}-bit, "
                  f"{params.framerate} Hz")
            
            if params.nchannels != 1:
                print("  Warning: Expected mono audio (1 channel)")
            if params.sampwidth != 2:
                print("  Warning: Expected 16-bit audio")
            if params.framerate != 16000:
                print("  Warning: Expected 16kHz sample rate")
            
            # Stream audio in chunks
            chunk_size = 1024
            chunks_sent = 0
            
            while True:
                data = wav.readframes(chunk_size)
                if not data:
                    break
                    
                await websocket.send(data)
                chunks_sent += 1
                
                # Small delay to simulate real-time streaming
                await asyncio.sleep(chunk_size / params.framerate)
            
            print(f"✓ Sent {chunks_sent} audio chunks")
            
            # Keep receiving responses for a bit
            print("Waiting for translation responses...")
            try:
                await asyncio.wait_for(
                    receive_responses(websocket),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                print("No more responses received")
                
    except Exception as e:
        print(f"✗ Error streaming audio: {e}")


async def receive_responses(websocket):
    """Receive and log responses from the server."""
    try:
        while True:
            message = await websocket.recv()
            print(f"  Received {len(message)} bytes of translated audio")
    except websockets.exceptions.ConnectionClosed:
        pass


def main():
    """Main entry point for the test client."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test client for Russian to English translation server"
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:8765",
        help="WebSocket URL of the translation server (default: ws://localhost:8765)",
    )
    parser.add_argument(
        "--audio",
        help="Optional WAV file to stream (for testing)",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Russian to English Translation Test Client")
    print("=" * 60)
    print()
    
    try:
        result = asyncio.run(test_translation_client(args.url, args.audio))
        sys.exit(result or 0)
    except KeyboardInterrupt:
        print("\n✓ Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
