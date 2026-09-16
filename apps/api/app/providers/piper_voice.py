"""Local neural speech synthesis via Piper.

Piper is a small VITS model exported to ONNX: a 22MB binary plus a ~63MB voice
runs comfortably on CPU at roughly a third of real time, which makes it viable
on the kind of hardware this app might actually be deployed on. That is the
whole reason it is here -- RoadSignal's other optional engine needs a 12.8GB
container image for the same job.

Licensing note: this targets the MIT-licensed Piper (rhasspy/piper). The newer
OHF-Voice/piper1-gpl fork is GPL-3.0, which would impose copyleft obligations
on this MIT project, so it is deliberately not used.

The binary is invoked with no shell and the text is written to stdin, so route
names and place names can never be interpreted as shell syntax.
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

MAX_TEXT_LENGTH = 400


class PiperVoiceProvider:
    """Synthesises WAV audio using a local Piper binary and voice model."""

    def __init__(self, binary: str, voice_model: str, timeout_seconds: float = 30.0):
        self.binary = (binary or "").strip()
        self.voice_model = (voice_model or "").strip()
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.binary and self.voice_model)

    def _resolved_binary(self) -> str | None:
        if not self.binary:
            return None
        if Path(self.binary).exists():
            return self.binary
        return shutil.which(self.binary)

    @property
    def available(self) -> bool:
        """Both the executable and the model must be present on disk. Reported
        rather than assumed so the UI can offer the engine only when it works."""
        return bool(self._resolved_binary()) and Path(self.voice_model).exists()

    @property
    def status(self) -> dict:
        return {
            "configured": self.configured,
            "available": self.available,
            "voice_model": Path(self.voice_model).name if self.voice_model else "",
            "binary_found": bool(self._resolved_binary()),
            "model_found": bool(self.voice_model) and Path(self.voice_model).exists(),
        }

    async def synthesize(self, text: str) -> bytes:
        """Return WAV bytes for `text`, or raise RuntimeError."""
        if not self.available:
            raise RuntimeError("Piper is not configured on this server")
        cleaned = " ".join((text or "").split())[:MAX_TEXT_LENGTH]
        if not cleaned:
            raise RuntimeError("No text to speak")

        binary = self._resolved_binary()
        # Piper writes the WAV to stdout when asked for "-", keeping this
        # stateless: no temp files to clean up or leak between requests.
        process = await asyncio.create_subprocess_exec(
            binary, "--model", self.voice_model, "--output_file", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(cleaned.encode("utf-8")),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError("Piper timed out")

        if process.returncode != 0 or not stdout:
            detail = (stderr or b"").decode("utf-8", "replace").strip().splitlines()
            raise RuntimeError(f"Piper failed: {detail[-1] if detail else 'no audio produced'}")
        if stdout[:4] != b"RIFF":
            raise RuntimeError("Piper returned data that is not a WAV stream")
        return stdout
