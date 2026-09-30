"""End-to-end harness for voice mode without LiveKit Cloud.

Runs the project's REAL `voice_agent.voice_session` against a local LiveKit
server, replacing only the cloud speech services with local stand-ins:

- FakeSTT: after ~1.5 s of microphone audio it "hears" one question.
- FakeTTS: speaks a tone (with 3-5 kHz content so level meters react) whose
  length matches the text.
- Turn detection: "stt" (end of speech from FakeSTT) instead of the cloud model.

Dispatch by agent name, AppLLM -> API -> model, agent attributes, the interrupt
RPC, the greeting and synced transcripts are all production code.

Run from the project's agent/ folder:
    env LIVEKIT_URL=ws://127.0.0.1:7880 LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret \
        VOICE_NOISE_CANCELLATION=false API_URL=http://127.0.0.1:8000 \
        .venv/bin/python <skill>/assets/testing/voice_e2e_agent.py start
"""

import math
import os
import struct
import sys
import types

sys.path.insert(0, os.getcwd())  # the project's agent/ folder

from livekit.agents import (  # noqa: E402
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    cli,
    inference,
    stt,
    tts,
    utils,
)

import voice_agent  # noqa: E402

QUESTION = "What is AI?"
RATE = 24000


class FakeSTT(stt.STT):
    def __init__(self) -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))

    async def _recognize_impl(self, buffer, *, language=NOT_GIVEN, conn_options=None):
        raise NotImplementedError

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return FakeSTTStream(stt=self, conn_options=conn_options)


class FakeSTTStream(stt.RecognizeStream):
    async def _run(self) -> None:
        seconds, said = 0.0, False
        kinds = stt.SpeechEventType
        async for frame in self._input_ch:
            if isinstance(frame, self._FlushSentinel):
                continue
            seconds += frame.samples_per_channel / frame.sample_rate
            if said or seconds < 1.5:
                continue
            said = True
            self._event_ch.send_nowait(stt.SpeechEvent(type=kinds.START_OF_SPEECH))
            for text, kind in (
                ("What is", kinds.INTERIM_TRANSCRIPT),
                (QUESTION, kinds.FINAL_TRANSCRIPT),
            ):
                alt = stt.SpeechData(language="en", text=text, confidence=0.99)
                self._event_ch.send_nowait(stt.SpeechEvent(type=kind, alternatives=[alt]))
            self._event_ch.send_nowait(stt.SpeechEvent(type=kinds.END_OF_SPEECH))


class FakeTTS(tts.TTS):
    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False), sample_rate=RATE, num_channels=1
        )

    def synthesize(self, text, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return FakeChunked(tts=self, input_text=text, conn_options=conn_options)


def tone(i: int) -> int:
    t = i / RATE
    return int(
        2500 * math.sin(2 * math.pi * 220 * t)
        + 2500 * math.sin(2 * math.pi * 3100 * t)
        + 2000 * math.sin(2 * math.pi * 5300 * t)
    )


class FakeChunked(tts.ChunkedStream):
    async def _run(self, output_emitter) -> None:
        output_emitter.initialize(
            request_id=utils.shortuuid(), sample_rate=RATE, num_channels=1, mime_type="audio/pcm"
        )
        n = int(RATE * max(0.8, len(self._input_text) * 0.07))
        output_emitter.push(struct.pack(f"<{n}h", *(tone(i) for i in range(n))))
        output_emitter.flush()


voice_agent.inference = types.SimpleNamespace(
    STT=lambda **_: FakeSTT(),
    TTS=lambda **_: FakeTTS(),
    TurnDetector=lambda **_: "stt",
    LLM=inference.LLM,
)

if __name__ == "__main__":
    cli.run_app(voice_agent.server)
