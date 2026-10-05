# V-CIP pre-interview agent: Sarvam console setup

A SECOND Sarvam Samvaad agent, separate from the Voice Chase agent, because it has a different prompt and different variables.
RBI requires an authorised official to do the video-based customer identification and sign it off. This agent only prepares: it asks a few randomized Hindi
liveness questions and the answers are recorded. It never decides, never says whether the answers were right, and never mentions approval.

## 1. Create the agent (Sarvam console)

| Setting | Value |
|---|---|
| Name | Karyakarta V-CIP pre-interview |
| Channel | **Voice (call)**. Phone calling uses the same connected Twilio number as Voice Chase |
| Primary language | Hindi (switch to English if the person does) |
| Voice | Female, same as the chase agent |
| Max call length | 3 minutes |

Then in `backend/.env`: `SARVAM_VCIP_AGENT_ID=<its id>` (and `SARVAM_VCIP_AGENT_VERSION=<n>` if not the same as `SARVAM_AGENT_VERSION`). The API key and the Twilio
connection are the ones already set for Voice Chase. Restart the backend after editing `.env`.

## 2. Variables

All strings, sent by the backend on every call (`GET /api/cases/{id}/voice-chase/context?kind=vcip`):

| Variable | Meaning |
|---|---|
| `case_id`, `merchant_name`, `contact_name` | Who is being called |
| `question_count` | Always 3 |
| `question_1_hi`, `question_2_hi`, `question_3_hi` | The three questions, exactly as to be spoken (one is always a random number to repeat back; the others are picked at random from: today's day, this month, the company's full name, the person's own name, the date of birth when an ID is on file) |

The expected answers are shown to the compliance officer and are **not** sent to the agent, so it cannot hint or correct.

## 3. Prompt (paste as the instructions; insert variables with the variable picker)

```
You are Karyakarta, a voice assistant calling on behalf of Paytm's corporate onboarding team. You are calling {contact_name} about the merchant account of
{merchant_name} (case {case_id}). This is a short preparation for a video KYC with an authorised Paytm official. You are NOT the official.

Goal: ask {question_count} simple questions, one at a time, and listen to the answers. Nothing else.

The questions, in this order:
1. {question_1_hi}
2. {question_2_hi}
3. {question_3_hi}

How to run the call:
1. Greet, say who you are, and confirm you are speaking to {contact_name}. If it is the wrong person or number, apologise and end the call.
2. Say this is a short check before the video KYC and that you will ask {question_count} easy questions. Ask if they can start now. If not, ask for a better time and end.
3. Ask each question exactly as written above, one at a time, in Hindi. Wait for the answer. Do not rephrase the random number: say it exactly as written, once, slowly.
4. After each answer say only "ठीक है, धन्यवाद" and move to the next question. Do NOT say whether the answer was correct. Do NOT repeat the answer back.
5. After the last question, thank them and say that an authorised official will contact them on video shortly. End the call.

Rules:
- Speak Hindi; switch to English only if the person does.
- Keep every turn short.
- Never say or imply the person passed, failed, was approved or was rejected.
- Never ask for or accept OTPs, PINs, card numbers, account numbers, Aadhaar numbers or passwords.
- Do not discuss documents, limits, timelines or anything outside the questions. If asked, say the authorised official will explain.
- If the person repeats a question back to you, asks you to repeat, or did not hear, repeat the question once. A random number may be repeated once only.
- If the person is upset or asks for a human, apologise and say the official will call them.
```

## 4. Opening line

The backend sends it per call (`initial_bot_message`), for example:

```
नमस्ते Anil Sharma, मैं पेटीएम से कार्यकर्ता बोल रही हूँ। यह आपके वीडियो केवाईसी से पहले की एक छोटी सी बातचीत है, बस 3 आसान सवाल। क्या अभी हम शुरू कर सकते हैं?
```

## 5. Test it (no phone needed)

```
python scripts/voice_agent_probe.py KYB-20814 --kind vcip --scenario 1
```

plays a scripted merchant over a call session using the real questions, and prints the agent's transcribed words. Run it a few times: the number to repeat and the other
two questions must differ between runs. Check that the agent never says an answer was right or wrong.

| # | Merchant does | Agent should |
|---|---|---|
| 1 | Answers all three | Asks them in order, says only "ठीक है, धन्यवाद", closes saying an official will contact them |
| 2 | Says "I am busy" | Asks for a better time and ends |
| 3 | Asks "was that right?" | Does not say; says the official will explain |
| 4 | Offers an OTP | Refuses |
| 5 | Asks about limits or approval | Says the official will explain |
| 6 | Says wrong number | Apologises and ends |

## 6. How it connects

Compliance presses **Start pre-interview call** in the V-CIP card (number box, same validation as Voice Chase) → `POST /api/cases/{id}/action {vcip_call}` → the backend
hands `{case_id, to_number, kind: "vcip"}` to n8n → the *Karyakarta - Voice chase* workflow gets the V-CIP context, calls with the V-CIP agent, waits and polls Sarvam until
the call ends, and records the transcript on the V-CIP record. It is not stored in Cognee. The officer then reviews the questions with the expected answers, the transcript, the
owner selfie and the ID document side by side, and signs off in one click.

**Not automated:** face matching. No face-recognition model is integrated, and the card says so. The officer compares the faces.
