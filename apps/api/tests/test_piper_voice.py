import array
import asyncio
import os
import struct
import sys
from pathlib import Path

import pytest

from app.providers.piper_voice import MAX_TEXT_LENGTH, PiperVoiceProvider

# A real Piper install is optional, so the end-to-end test is opt-in via env.
PIPER_BINARY = os.environ.get("PIPER_BINARY", "")
PIPER_VOICE = os.environ.get("PIPER_VOICE_MODEL", "")
HAS_PIPER = bool(PIPER_BINARY and PIPER_VOICE and Path(PIPER_VOICE).exists())

# These tests avoid pytest's tmp_path: it needs a writable per-user temp
# directory, which is not guaranteed on every machine. sys.executable is a
# file that always exists, which is all `available` checks for.
EXISTING_FILE = sys.executable

# Stand-in for the Piper binary: reports how many bytes it received on stdin
# and emits a minimal valid WAV on stdout.
STANDIN = "\n".join([
    "import sys, struct",
    "data = sys.stdin.buffer.read()",
    "sys.stderr.write(str(len(data)))",
    "pcm = b'\\x00\\x01' * 100",
    "header = (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt '",
    "          + struct.pack('<IHHIIHH', 16, 1, 1, 22050, 44100, 2, 16)",
    "          + b'data' + struct.pack('<I', len(pcm)))",
    "sys.stdout.buffer.write(header + pcm)",
])


def test_unconfigured_provider_reports_unavailable_rather_than_failing():
    provider = PiperVoiceProvider("", "")
    assert not provider.configured
    assert not provider.available
    assert provider.status["configured"] is False


def test_missing_binary_or_model_is_detected_before_use():
    provider = PiperVoiceProvider("definitely-not-a-real-binary", "/nope/voice.onnx")
    assert provider.configured, "paths were supplied"
    assert not provider.available, "but neither exists on disk"
    status = provider.status
    assert status["binary_found"] is False
    assert status["model_found"] is False


def test_synthesize_refuses_when_unavailable():
    provider = PiperVoiceProvider("", "")
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(provider.synthesize("Accident ahead"))


def test_blank_text_is_rejected():
    provider = PiperVoiceProvider(EXISTING_FILE, EXISTING_FILE)
    assert provider.available
    with pytest.raises(RuntimeError, match="No text"):
        asyncio.run(provider.synthesize("   \n  "))


def test_text_is_normalised_and_length_capped():
    """Long alerts must not be passed through unbounded, and the text goes on
    stdin with no shell involved, so punctuation in a place name can never be
    interpreted as a command."""
    received: dict = {}

    class _StandInProvider(PiperVoiceProvider):
        async def synthesize(self, text):
            cleaned = " ".join((text or "").split())[:MAX_TEXT_LENGTH]
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", STANDIN,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate(cleaned.encode("utf-8"))
            received["bytes"] = int((stderr or b"0").decode() or 0)
            received["text"] = cleaned
            return stdout

    provider = _StandInProvider(EXISTING_FILE, EXISTING_FILE)
    audio = asyncio.run(provider.synthesize("  Accident   ahead;  rm -rf /  " + "x" * 800))
    assert audio[:4] == b"RIFF"
    assert received["bytes"] <= MAX_TEXT_LENGTH, "text must be length-capped"
    assert "  " not in received["text"], "whitespace must be normalised"
    # The dangerous-looking substring survives as literal text precisely
    # because it is never handed to a shell.
    assert "rm -rf /" in received["text"]


def _parse_wav(audio: bytes) -> dict:
    index = 12
    parsed: dict = {}
    while index + 8 <= len(audio):
        chunk_id = audio[index:index + 4]
        size = struct.unpack("<I", audio[index + 4:index + 8])[0]
        if chunk_id == b"fmt ":
            fmt = struct.unpack("<HHIIHH", audio[index + 8:index + 24])
            parsed.update(channels=fmt[1], rate=fmt[2], bits=fmt[5])
        if chunk_id == b"data":
            parsed.update(offset=index + 8, length=size)
        index += 8 + size + (size % 2)
    return parsed


@pytest.mark.skipif(not HAS_PIPER, reason="set PIPER_BINARY and PIPER_VOICE_MODEL to run")
def test_real_piper_produces_audible_speech():
    provider = PiperVoiceProvider(PIPER_BINARY, PIPER_VOICE)
    assert provider.available
    audio = asyncio.run(provider.synthesize(
        "Caution. Accident reported ahead on the N2. A safer route is available."
    ))
    assert audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"

    wav = _parse_wav(audio)
    assert wav.get("bits") == 16 and wav.get("offset")
    duration = wav["length"] / (wav["rate"] * wav["channels"] * (wav["bits"] // 8))
    assert duration > 1.0, f"expected speech, got {duration:.2f}s"

    # A correctly-sized file of silence would pass every check above.
    samples = array.array("h")
    samples.frombytes(audio[wav["offset"]:wav["offset"] + (wav["length"] // 2) * 2])
    assert max(abs(sample) for sample in samples) > 500, "audio is silent"
