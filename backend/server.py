"""FastAPI server + Pipecat pipeline: mic PCM -> ElevenLabs STT -> Gemini -> ElevenLabs TTS -> speaker PCM.

Pipecat >=1.0 API:
  - LLMContext  (was OpenAILLMContext)
  - GoogleLLMService.Settings(model=..., system_instruction=...)
  - FunctionSchema / ToolsSchema from pipecat.adapters.schemas.*
  - ElevenLabsSTTService requires aiohttp_session
  - FrameSerializer.serialize / .deserialize are plain async methods
"""
import os, json, datetime as dt, aiohttp, uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    AudioRawFrame, InputAudioRawFrame,
    LLMFullResponseEndFrame, LLMFullResponseStartFrame,
    LLMRunFrame, TextFrame, TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.services.elevenlabs.stt import ElevenLabsSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

import data

load_dotenv()
app = FastAPI()


def system_prompt():
    return (
        f"You are Maya, the phone assistant for a doctor's clinic. Today is {dt.date.today():%A, %Y-%m-%d}.\n"
        "You can check availability, book and cancel appointments using your tools.\n"
        "Speak in short, natural sentences. No lists, no markdown. Offer at most 3 slots at a time.\n"
        "The caller is identified ONLY by the phone number they say. Convert spoken digits to a 10-digit string.\n"
        "Before booking or cancelling, read the number back digit by digit and wait for a clear yes. If no, ask again.\n"
        "Book only after the caller picks a doctor, date and time. Ask for their name when booking.\n"
        "Never invent slots; use check_doctor_availability. After each action, confirm what happened briefly."
    )


TOOLS = ToolsSchema(standard_tools=[
    FunctionSchema(
        "check_doctor_availability",
        "List free slots, optionally filtered by doctor name/speciality and date.",
        {"doctor": {"type": "string", "description": "Doctor name or speciality"},
         "date": {"type": "string", "description": "YYYY-MM-DD"}},
        [],
    ),
    FunctionSchema(
        "book_appointment",
        "Book a slot for the caller.",
        {"doctor": {"type": "string"},
         "date": {"type": "string", "description": "YYYY-MM-DD"},
         "time": {"type": "string", "description": "HH:MM 24h"},
         "phone": {"type": "string", "description": "Caller's confirmed phone number"},
         "patient_name": {"type": "string"}},
        ["doctor", "date", "time", "phone"],
    ),
    FunctionSchema(
        "cancel_appointment",
        "Cancel the caller's appointment found by phone number.",
        {"phone": {"type": "string", "description": "Caller's confirmed phone number"},
         "date": {"type": "string"},
         "time": {"type": "string"}},
        ["phone"],
    ),
])


def make_handler(fn):
    """Wrap a sync data function so it fits Pipecat's async tool-call signature."""
    async def h(params: FunctionCallParams):
        result = fn(**params.arguments)
        await params.result_callback(result)
    return h


class PCMSerializer(FrameSerializer):
    """Browser sends raw 16 kHz PCM16 binary; we send raw 24 kHz PCM16 binary + JSON text events."""

    async def serialize(self, frame):  # noqa: ANN001
        if isinstance(frame, AudioRawFrame):
            return frame.audio
        # Send interruption signal as a JSON text message
        if type(frame).__name__ in ("InterruptionFrame", "StartInterruptionFrame"):
            return json.dumps({"type": "interrupt"})
        return None

    async def deserialize(self, d):  # noqa: ANN001
        if isinstance(d, bytes):
            return InputAudioRawFrame(audio=d, sample_rate=16000, num_channels=1)
        return None


class Tap(FrameProcessor):
    """Forwards user/bot text to the dashboard for the live transcript."""

    def __init__(self, role: str, ws: WebSocket):
        super().__init__()
        self.role = role
        self.ws = ws
        self.buf = ""

    async def _send(self, text: str):
        if text.strip():
            await self.ws.send_text(
                json.dumps({"type": "transcript", "role": self.role, "text": text.strip()})
            )

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if self.role == "user" and isinstance(frame, TranscriptionFrame):
            await self._send(frame.text)
        elif self.role == "bot":
            if isinstance(frame, LLMFullResponseStartFrame):
                self.buf = ""
            elif isinstance(frame, TextFrame):
                self.buf += frame.text
            elif isinstance(frame, LLMFullResponseEndFrame):
                await self._send(self.buf)
                self.buf = ""
        await self.push_frame(frame, direction)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    transport = FastAPIWebsocketTransport(
        ws,
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=PCMSerializer(),
        ),
    )

    async with aiohttp.ClientSession() as session:
        stt = ElevenLabsSTTService(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            aiohttp_session=session,
        )
        tts = ElevenLabsTTSService(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            settings=ElevenLabsTTSService.Settings(
                voice=os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
            ),
        )
        llm = GoogleLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"),
            settings=GoogleLLMService.Settings(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                system_instruction=system_prompt(),
            ),
        )

        for name, fn in [
            ("check_doctor_availability", data.check_doctor_availability),
            ("book_appointment", data.book_appointment),
            ("cancel_appointment", data.cancel_appointment),
        ]:
            llm.register_function(name, make_handler(fn))

        ctx = LLMContext(
            messages=[{"role": "user", "content": "A caller just connected. Greet them briefly."}],
            tools=TOOLS,
        )
        agg = LLMContextAggregatorPair(ctx)

        pipeline = Pipeline([
            transport.input(),
            stt,
            Tap("user", ws),
            agg.user(),
            llm,
            Tap("bot", ws),
            tts,
            transport.output(),
            agg.assistant(),
        ])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
                allow_interruptions=True,
            ),
        )

        @transport.event_handler("on_client_connected")
        async def _on_connected(t, c):
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def _on_disconnected(t, c):
            await task.cancel()

        await PipelineRunner(handle_sigint=False).run(task)


@app.get("/api/doctors")
def get_doctors():
    return [
        {
            **d,
            "slots": [
                {"date": s["date"], "time": s["time"]}
                for s in data.SLOTS
                if s["doctor_id"] == d["id"] and not s["booked"]
            ],
        }
        for d in data.DOCTORS
    ]


@app.get("/api/appointments")
def get_appointments():
    return data.APPOINTMENTS


app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend"), html=True),
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
