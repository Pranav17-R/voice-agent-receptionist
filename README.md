# Clinic line: voice appointment assistant

Caller speaks to **Maya**, an AI agent that checks doctor availability, books and cancels appointments.
The caller is identified only by the phone number they say; Maya reads it back before booking or cancelling.

**LLM:** Google Gemini (`gemini-2.5-flash`, free quota). **STT/TTS:** ElevenLabs. **Framework:** Pipecat. **VAD:** Silero.

## Run
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env                              # add GOOGLE_API_KEY and ELEVENLABS_API_KEY
python server.py
```
Open http://localhost:8000, click **Start call**, allow the microphone. Use headphones to avoid echo.

## Pipeline
Browser mic (16 kHz PCM over WebSocket) -> Pipecat `FastAPIWebsocketTransport` + Silero VAD -> ElevenLabs STT ->
Gemini with 3 registered tools -> ElevenLabs TTS -> browser speaker (24 kHz PCM).
A small `Tap` processor sends transcript lines to the dashboard. The dashboard polls `/api/doctors` and
`/api/appointments` every 1.5 s, so bookings and cancellations appear live and trigger row highlights and confirmation cards.

## Files
- `backend/server.py`: pipeline, tool schemas, WebSocket and REST endpoints
- `backend/data.py`: in-memory doctors, slots and the three tool functions
- `frontend/index.html`: dashboard and phone-style call screen (plain HTML/JS)
