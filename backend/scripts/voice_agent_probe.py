"""Talk to the Sarvam Samvaad voice agent as a scripted merchant, using the real case context, and read what it says.

    python scripts/voice_agent_probe.py KYB-20814                  # scenario 1 (merchant agrees, promises upload)
    python scripts/voice_agent_probe.py KYB-20814 --scenario 4     # see SCENARIOS below
    python scripts/voice_agent_probe.py KYB-20814 --say "हाँ बोलिए" --say "कल भेज दूँगा"

Your agent is deployed for voice CALLS, so it answers in audio. The probe keeps an (empty) audio line open, sends each
merchant line as speech, records the agent's audio for every turn and transcribes it with Sarvam speech-to-text
(SARVAM_API_KEY) so the conversation can be read. The scripted merchant speaks too: each line is turned into
speech with Sarvam text-to-speech and streamed down the line (a call agent ignores typed text). Use --mode chat only if the agent has the chat channel enabled.
The Sarvam keys are read from backend/.env and never printed.
"""
import argparse
import asyncio
import base64
import io
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import SecretStr  # noqa: E402
from sarvam_conv_ai_sdk import AsyncSamvaadAgent, InteractionConfig, InteractionType  # noqa: E402
from sarvam_conv_ai_sdk.messages.types import UserIdentifierType  # noqa: E402
from sarvamai import SarvamAI  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app import config, voice_agent  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import Case  # noqa: E402

SCENARIOS = {
    1: ["हाँ बोलिए", "ठीक है, मैं कल शाम तक अपलोड कर दूँगा"],
    2: ["अभी मैं busy हूँ, बाद में बात करें"],
    3: ["Can we talk in English please?", "Okay, I will upload them tomorrow."],
    4: ["हाँ बोलिए", "मेरा अकाउंट कब approve होगा?"],
    5: ["हाँ बोलिए", "क्या मैं OTP बता दूँ?"],
    6: ["हाँ", "Navi Mumbai ही हमारा सही पता है"],
    7: ["ये रॉन्ग नंबर है, यहाँ कोई Sharma नहीं रहता"],
    8: ["हाँ बोलिए", "Director वाला issue क्या है? सिग्नेटरी के बारे में बताइए"],
}
MAX_STT_SECONDS = 25


def transcribe(pcm: bytes, rate: int) -> str:
    """Speech-to-text for one turn of the agent's audio (16-bit mono PCM)."""
    if len(pcm) < rate * 2 * 0.3:
        return ""
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        return "(set SARVAM_API_KEY to transcribe the agent's audio)"
    client = SarvamAI(api_subscription_key=key)
    step = rate * 2 * MAX_STT_SECONDS
    out = []
    for i in range(0, len(pcm), step):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm[i:i + step])
        buf.seek(0)
        r = client.speech_to_text.transcribe(file=("agent.wav", buf, "audio/wav"), model="saaras:v3", mode="transcribe", language_code="unknown")
        out.append((r.transcript or "").strip())
    return " ".join(x for x in out if x)


def synthesize(text: str) -> bytes:
    """The scripted merchant's voice: Sarvam text-to-speech as 16 kHz mono PCM (so the agent hears speech, not text)."""
    client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY", ""))
    lang = "en-IN" if text.isascii() else "hi-IN"
    r = client.text_to_speech.convert(text=text, language_code=lang, speaker="aditya", model="bulbul:v3",
                                      speech_sample_rate=16000, output_audio_codec="wav")
    pcm = b""
    for chunk in r.audios:
        raw = base64.b64decode(chunk)
        if raw[:4] == b"RIFF":
            with wave.open(io.BytesIO(raw)) as w:
                raw = w.readframes(w.getnframes())
        pcm += raw
    return pcm


async def run(case_id: str, said: list[str], wait: float, mode: str) -> dict:
    if not config.SARVAM_AGENT_ID or not config.SARVAM_AGENT_API_KEY:
        raise SystemExit("Set SARVAM_AGENT_ID and SARVAM_API_KEY_NEW_FOR_VOICE in backend/.env")
    with Session(engine) as s:
        ctx = voice_agent.context(s, s.get(Case, case_id))
    phases: list[bytearray] = [bytearray()]       # agent audio per turn: phase 0 = greeting, i = reply to merchant line i
    rate = {"hz": 16000}
    text_turns: list[dict] = []
    events: list[str] = []

    async def on_audio(msg):
        phases[-1].extend(base64.b64decode(msg.audio_base64))
        rate["hz"] = msg.sample_rate or rate["hz"]

    async def on_text(msg):
        t = getattr(msg, "text", None) or getattr(msg, "content", "")
        if t:
            text_turns.append({"role": "agent(text)", "text": t})

    async def on_transcript(msg):
        text_turns.append({"role": getattr(msg.role, "value", str(msg.role)), "text": msg.content})

    async def on_event(ev):
        events.append(getattr(ev.type, "value", str(ev.type)))

    cfg = InteractionConfig(
        org_id=config.SARVAM_ORG_ID, workspace_id=config.SARVAM_WORKSPACE_ID, app_id=config.SARVAM_AGENT_ID,
        user_identifier=f"probe-{case_id}", user_identifier_type=UserIdentifierType.CUSTOM,
        interaction_type=InteractionType.CALL if mode == "call" else InteractionType.CHAT, sample_rate=16000,
        agent_variables=ctx["agent_variables"], initial_language_name=ctx["initial_language_name"],
        initial_bot_message=ctx["initial_bot_message"],
    )
    agent = AsyncSamvaadAgent(api_key=SecretStr(config.SARVAM_AGENT_API_KEY), config=cfg, text_callback=on_text,
                              transcript_callback=on_transcript, event_callback=on_event,
                              audio_callback=on_audio if mode == "call" else None)
    await agent.start()
    await agent.wait_for_connect()
    silence = bytes(3200)                         # 100 ms of 16 kHz mono PCM: keeps the 'phone line' open, as a real call would

    async def open_line():
        while True:
            await agent.send_audio(silence)
            await asyncio.sleep(0.1)

    line_task = asyncio.create_task(open_line()) if mode == "call" else None
    await asyncio.sleep(wait + 4)                 # greeting
    for merchant_line in said:
        phases.append(bytearray())
        if mode == "call":
            speech = await asyncio.to_thread(synthesize, merchant_line)
            line_task.cancel()                       # replace the silence stream with the merchant speaking
            for i in range(0, len(speech), 3200):
                await agent.send_audio(speech[i:i + 3200].ljust(3200, bytes(1)))
                await asyncio.sleep(0.1)             # real time, like a phone line
            line_task = asyncio.create_task(open_line())
        else:
            await agent.send_text(merchant_line)
        await asyncio.sleep(wait)
    if line_task:
        line_task.cancel()
    await agent.stop()

    conversation = []
    for i, audio in enumerate(phases):
        if i > 0:
            conversation.append({"role": "merchant(scripted, spoken via TTS)", "text": said[i - 1]})
        heard = await asyncio.to_thread(transcribe, bytes(audio), rate["hz"]) if mode == "call" else ""
        conversation.append({"role": "agent(heard via speech-to-text)", "text": heard or "(no speech received)",
                             "audio_seconds": round(len(audio) / (rate["hz"] * 2), 1)})
    return {"interaction_id": agent.get_interaction_id(), "variables_sent": sorted(ctx["agent_variables"]),
            "conversation": conversation, "text_messages": text_turns, "events": sorted(set(events))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--scenario", type=int, default=1, choices=sorted(SCENARIOS))
    ap.add_argument("--say", action="append", help="merchant line (repeatable); overrides --scenario")
    ap.add_argument("--mode", choices=["call", "chat"], default="call", help="session type the agent is deployed for (yours: call)")
    ap.add_argument("--wait", type=float, default=10.0, help="seconds to wait for the agent after each message")
    ap.add_argument("--record", action="store_true",
                    help="send the conversation to n8n (karyakarta-voice-result) so it is recorded on the case and stored in Cognee; labelled as a rehearsal")
    a = ap.parse_args()
    result = asyncio.run(run(a.case_id, a.say or SCENARIOS[a.scenario], a.wait, a.mode))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if a.record:
        record(a.case_id, result, None if a.say else a.scenario)


OUTCOME_BY_SCENARIO = {1: "promised_upload", 2: "callback_requested", 7: "wrong_number"}


def record(case_id: str, result: dict, scenario: int | None) -> None:
    """Report the rehearsal exactly as Sarvam's call-completed callback will: to the n8n result webhook."""
    import httpx

    if not config.N8N_VOICE_WEBHOOK_URL:
        raise SystemExit("Set N8N_VOICE_WEBHOOK_URL in backend/.env to use --record")
    url = config.N8N_VOICE_WEBHOOK_URL.replace("karyakarta-voice-chase", "karyakarta-voice-result")
    transcript = [{"role": "merchant" if t["role"].startswith("merchant") else "agent", "text": t["text"]}
                  for t in result["conversation"] if t["text"] != "(no speech received)"]
    payload = {
        "case_id": case_id, "outcome": OUTCOME_BY_SCENARIO.get(scenario, "reached"), "call_id": result["interaction_id"],
        "summary": "REHEARSAL, not a real call: the live Sarvam agent spoke with a scripted merchant (voice by text-to-speech). "
                   f"Scenario {scenario or 'custom'}.",
        "transcript": transcript,
    }
    r = httpx.post(url, json=payload, timeout=15)
    print(f"recorded via n8n: HTTP {r.status_code} ({len(transcript)} turns)")


if __name__ == "__main__":
    main()
