# CarePoint ClinicLine — Voice AI Receptionist

An end-to-end, real-time conversational voice assistant for a medical clinic. Callers talk naturally with **Maya**, an AI receptionist that checks doctor availability, books appointments, and cancels existing bookings via live function calling.

The frontend is a single-page clinic dashboard with a live appointment ledger, physician slot directory, audio waveform visualizer, and real-time conversation transcripts.

---

## 🏗️ Architecture & Pipeline Flow

```
[Browser Microphone]
        │  (Raw 16 kHz PCM16 over WebSocket /ws)
        ▼
[FastAPI WebSocket Transport]
        │
        ▼
[Silero VAD Processor] ── (Detects speech start/stop boundaries)
        │
        ▼
[ElevenLabs STT Service] ── (Real-time Speech-to-Text transcription)
        │
        ▼
[Live Transcript Tap] ── (Streams transcripts to dashboard UI)
        │
        ▼
[Google Gemini 3.5 Flash Lite] ── (LLM Reasoning + Function Calling)
        │                              │
        │                              ├── check_doctor_availability()
        │                              ├── book_appointment()
        │                              └── cancel_appointment()
        ▼
[ElevenLabs TTS Service] ── (Synthesizes speech via voice 'Sarah')
        │  (Raw 24 kHz PCM16 audio)
        ▼
[FastAPI WebSocket Transport]
        │
        ▼
[Browser Speaker Playback] + [Live Dashboard Ledger Update]
```

---

## 🛠️ Tech Stack

- **Voice Pipeline Framework:** [Pipecat](https://github.com/pipecat-ai/pipecat) (v1.17+)
- **Server & WebSocket Transport:** FastAPI + Uvicorn + WebSockets
- **LLM Reasoning & Function Calling:** Google Gemini (`gemini-3.5-flash-lite`)
- **Voice Activity Detection (VAD):** Silero VAD (neural speech segmentation)
- **Speech-to-Text (STT):** ElevenLabs Scribe STT
- **Text-to-Speech (TTS):** ElevenLabs TTS (`EXAVITQu4vr4xnSDxMaL` / Sarah premade voice)
- **Frontend Dashboard:** Vanilla HTML5, CSS3, JavaScript (Web Audio API, Canvas waveform, REST polling)

---

## 📋 Prerequisites

- **Python 3.10, 3.11, or 3.12** installed
- A **Google Gemini API Key** (Free tier available at [Google AI Studio](https://aistudio.google.com/app/apikey))
- An **ElevenLabs API Key** (Free tier available at [ElevenLabs](https://elevenlabs.io/app/settings/api-keys))
- A modern web browser (Google Chrome, Edge, Safari, or Firefox)
- **Headphones recommended** during calls to avoid microphone feedback/echo

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/Pranav17-R/voice-agent-receptionist.git
cd voice-agent-receptionist
```

### 2. Set Up Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 4. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env     # On Windows: copy .env.example .env
```

Open `.env` in any text editor and fill in your API keys:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
GEMINI_MODEL=gemini-3.5-flash-lite
PORT=8000
```

> **Note:** `EXAVITQu4vr4xnSDxMaL` is the official ElevenLabs "Sarah" premade voice that works on both free and paid accounts without subscription blocks.

### 5. Start the Server

From the project folder (the one that contains `backend/` and `venv/`).

**Windows (PowerShell)** — uses the project virtual environment directly:
```powershell
.\venv\Scripts\python.exe backend\server.py
```

**macOS / Linux** (after `source venv/bin/activate`):
```bash
python backend/server.py
```

You should see:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 6. Open the Dashboard
Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🧪 Interactive Walkthrough (Demo Scenario)

1. **Connect:** Click the green **"Start call"** button on the right phone console and grant microphone access.
2. **Greeting:** Maya greets you: *"Hello, thank you for calling the clinic. I'm Maya. How can I help you today?"*
3. **Provide Identification:** Say:
   > *"Hi Maya, my phone number is 9 8 7 6 5 4 3 2 1 0."*
   - Maya repeats your number digit by digit to confirm. Say *"Yes"*.
4. **Check Availability:** Say:
   > *"Can you check what slots Dr. Asha Rao has open tomorrow?"*
   - Maya checks the live schedule and suggests available times (e.g., 9:00 AM, 10:30 AM).
5. **Book Appointment:** Say:
   > *"Please book the 9:00 AM slot for Priya."*
   - Maya calls `book_appointment()`.
   - **Watch the Dashboard:** Within 1.5 seconds, the new appointment appears in the **Confirmed Appointments** table with an animated row highlight, and a booking card appears in the chat.
6. **Cancel Appointment:** Say:
   > *"Actually, I need to cancel my appointment."*
   - Maya locates the booking by your phone number, confirms cancellation, and the row disappears from the table in real time.
7. **End Call:** Click the red **"End"** button or say goodbye.

---

## 🗂️ Project Directory Structure

```text
voice-doctor-assistant/
├── backend/
│   ├── data.py             # In-memory clinic database (doctors, slots, appointments)
│   │                       # and tool functions (check, book, cancel)
│   ├── server.py           # FastAPI server, Pipecat voice pipeline, REST API & WebSockets
│   └── requirements.txt    # Python dependencies (Pipecat 1.17, FastAPI, Uvicorn, etc.)
├── frontend/
│   └── index.html          # Single-file healthcare dashboard with Web Audio API mic/speaker
├── .env.example            # Environment template with configuration instructions
├── .gitignore              # Ignores .env, virtual environments, caches, and temp files
└── README.md               # Project documentation and evaluation guide
```

---

## ⚙️ Key Technical Features & Implementation Details

- **Pipecat 1.x Universal Aggregator:** Implemented using `LLMContext` and `LLMContextAggregatorPair` for dynamic context accumulation and low-latency tool execution.
- **Custom PCM Serialization:** Custom `PCMSerializer` handles raw 16 kHz PCM16 input from browser `ScriptProcessorNode` and 24 kHz PCM16 output streams to the browser's `AudioContext`.
- **Interruption Handling (Barge-In):** When the caller speaks while Maya is speaking, Silero VAD broadcasts an interruption event that immediately halts active TTS audio output.
- **Zero-Latency Transcript Tap:** Custom `Tap` frame processor intercepts STT and LLM text frames to push live updates over the existing WebSocket connection without secondary HTTP polling.
- **Data Integrity & Validation:** Phone numbers are strictly normalized to 10-digit strings using regex; slot collisions and non-existent doctors are gracefully rejected with fallback suggestions.

---

## 🔒 Security Notice

- Never commit the `.env` file containing live API keys.
- `.env` is listed in `.gitignore` by default.
- Only share `.env.example` with placeholder strings.
