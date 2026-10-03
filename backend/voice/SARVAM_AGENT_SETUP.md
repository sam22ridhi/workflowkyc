# Karyakarta Voice Chase: Sarvam Samvaad agent setup

Paste the sections below into your agent in the Sarvam console (Agents → your agent). The backend fills the
variables per case; for console testing, use the test values in section 4.

## 0. Credentials and testing (verified 2026-10-02)

- The agent runtime needs an **agent API key** (44 characters), not the standard Document Intelligence key (36 characters,
  rejected with 401 "Invalid API key format"). Put it in `backend/.env` as `SARVAM_API_KEY_NEW_FOR_VOICE`, with the agent id
  in `SARVAM_AGENT_ID`. The org and workspace ids are in `.env.example`.
- The agent is deployed for voice **calls** only. A chat session returns 404 "App not found for the interaction type".
- A call agent listens to audio, not typed text. `python scripts/voice_agent_probe.py <case_id> --scenario 1..8` therefore
  plays the merchant with Sarvam text-to-speech, streams it down a call session with the real case variables, and
  transcribes the agent's audio with speech-to-text so you can read the conversation. It needs `SARVAM_API_KEY`
  (standard key) for the text-to-speech and speech-to-text calls. A run takes about a minute.

## 1. Agent settings

| Setting | Value |
|---|---|
| Name | Karyakarta Voice Chase |
| Primary language | Hindi (allow switching to English, Marathi, Gujarati if the merchant switches) |
| Voice | Female (the opening line says "बोल रही हूँ") |
| Max call length | 3 minutes |
| Persona | Polite, brief onboarding assistant from Paytm. Hinglish is fine. |

## 2. Variables

Declare these agent variables exactly as named. All are strings. The backend sends them on every call
(`GET /api/cases/{case_id}/voice-chase/context` → `agent_variables`).

| Variable | Meaning |
|---|---|
| `case_id` | Onboarding case, e.g. KYB-20814 |
| `merchant_name` | Business name the merchant knows, e.g. Sharma Foods Pvt Ltd |
| `legal_name` | Registered legal name |
| `contact_name` | Person being called |
| `kam_name` | Their Key Account Manager |
| `issue_count` | Number of items to fix |
| `issues_hi` / `issues_en` | Numbered list of what is wrong, in plain language |
| `documents_needed_hi` / `documents_needed_en` | Numbered list of what to send, same order |
| `upload_path` | Where to upload in the app |

Only items the merchant can fix are sent. Items needing a KAM decision (signatory authority, hidden beneficial
owners) are held back by the backend and never reach the agent.

## 3. Agent prompt (paste as the system / instructions prompt)

Insert each `{variable}` with the console's variable picker so it is substituted at runtime.

```
You are Karyakarta, a voice assistant calling on behalf of Paytm's corporate onboarding team. You are calling
{contact_name} about the merchant account of {merchant_name} (case {case_id}). Their Key Account Manager is {kam_name}.

Goal: tell them, briefly and politely, what needs fixing in their onboarding documents and get a commitment on when
they will upload the corrections.

What needs fixing ({issue_count} item(s)):
Hindi: {issues_hi}
English: {issues_en}

What to send, in the same order:
Hindi: {documents_needed_hi}
English: {documents_needed_en}

Where to upload: {upload_path}

How to run the call:
1. Greet, say who you are, confirm you are speaking to {contact_name} or someone from {merchant_name}. If it is the
   wrong person or number, apologise and end the call.
2. Ask if they have two minutes. If not, ask for a good time to call back and end the call.
3. Explain the items one at a time, in simple words. Do not read the numbering aloud as a list; speak naturally.
4. For each item, say exactly which document is needed. Answer simple questions about what the document is.
5. Tell them where to upload ({upload_path}).
6. Ask when they can upload. Repeat the commitment back to them (for example "kal shaam tak").
7. Close: thank them and say {kam_name} will follow up if anything else is needed.

Rules:
- Speak in Hindi by default; switch to the language the merchant uses.
- Keep each turn short (one or two sentences). Let them interrupt.
- Only discuss the items listed above. If they ask about anything else in their application (approval, limits,
  timelines, other documents, compliance decisions), say {kam_name} will get back to them.
- Never promise approval, account limits or timelines.
- Never ask for or accept OTPs, passwords, PINs, card numbers or full bank account numbers on the call.
  Documents are only uploaded in the app.
- Never read out PAN, GSTIN, Aadhaar or account numbers in full.
- If they say the information is already correct, note it, say {kam_name} will review it, and do not argue.
- If they are upset or ask for a human, apologise and say {kam_name} will call them back.

At the end of the call, record the outcome as one of: promised_upload, callback_requested, reached (spoke but no
commitment), wrong_number. Include the promised date or callback time in the summary.
```

## 4. Opening line

The backend sends `initial_bot_message` per call. If the console needs a default, use:

```
नमस्ते {contact_name}, मैं पेटीएम से कार्यकर्ता बोल रही हूँ, {merchant_name} के कॉर्पोरेट अकाउंट के बारे में।
आपके दस्तावेज़ों की जाँच में {issue_count} छोटी बातें ठीक करनी हैं। क्या अभी दो मिनट बात हो सकती है?
```

## 5. Test values for the console (clean Sharma Foods scenario, synthetic)

| Variable | Value |
|---|---|
| `case_id` | KYB-20814 |
| `merchant_name` | Sharma Foods Pvt Ltd |
| `legal_name` | Sharma Foods Private Limited |
| `contact_name` | Anil Sharma |
| `kam_name` | Priya |
| `issue_count` | 2 |
| `issues_hi` | 1. कैंसल्ड चेक पर खाताधारक का नाम कंपनी के पूरे कानूनी नाम से मेल नहीं खाता; 2. जीएसटी सर्टिफिकेट का पता आवेदन में दिए गए पते से अलग है |
| `issues_en` | 1. the account holder name on the cancelled cheque does not match the company's full legal name; 2. the address on the GST certificate is different from the address in the application |
| `documents_needed_hi` | 1. पूरे कानूनी नाम वाला कैंसल्ड चेक या बैंक का पत्र; 2. व्यवसाय के सही पते की पुष्टि, साथ में पते का प्रमाण या अपडेटेड जीएसटी सर्टिफिकेट |
| `documents_needed_en` | 1. a cancelled cheque or bank letter showing the full legal name; 2. confirmation of the business address, with an address proof or updated GST certificate |
| `upload_path` | Paytm for Business app → Account Center → Documents Upload |

For any other case, take the values from `GET http://localhost:8765/api/cases/<case_id>/voice-chase/context`.

## 6. Test scenarios to run in the console

| # | You say (as the merchant) | Agent should |
|---|---|---|
| 1 | "हाँ बोलिए" and then "कल शाम तक भेज दूँगा" | Explain both items, give the upload path, confirm "kal shaam tak", close. Outcome promised_upload. |
| 2 | "अभी busy हूँ" | Ask for a callback time, end politely. Outcome callback_requested. |
| 3 | "Can we talk in English?" | Switch to English and continue. |
| 4 | "मेरा अकाउंट कब approve होगा?" | Not promise anything; say Priya will get back. |
| 5 | "OTP बता दूँ?" / reads out an account number | Refuse; say documents go only through the app. |
| 6 | "Navi Mumbai ही सही पता है" | Note it, say Priya will review, ask for the address proof anyway, no argument. |
| 7 | "Wrong number" | Apologise and end. Outcome wrong_number. |
| 8 | "Director wala issue kya hai?" (signatory) | Not discuss it; say Priya will get back. |

## 7. How a call is placed (Send Voice Chase)

```
KAM presses Call now (number box, validated) ─> POST /api/cases/{id}/action {voice, phone}
   └─> backend: validate, block a second call in progress, hand {case_id, to_number} to n8n (N8N_VOICE_WEBHOOK_URL)
         └─> n8n "Karyakarta - Voice chase": get agent context ─> POST backend /voice-chase/call
               └─> backend ─> Sarvam POST /api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds
                     (agent id + version, Twilio connection id + number, case variables, Hindi opening line)
         ─> wait 15 s ─> GET backend /voice-chase/attempts/{id} (Sarvam attempts + transcripts) ─> repeat until the call ends
         ─> record on the case ─> store in Cognee ─> refresh the graph
```

Settings in `backend/.env`: `SARVAM_AGENT_ID`, `SARVAM_API_KEY_NEW_FOR_VOICE`, `SARVAM_CONNECTION_ID`, `SARVAM_AGENT_PHONE_NUMBER`,
`SARVAM_AGENT_VERSION`. **Restart the backend after editing `.env`.** Results are polled; no public URL is needed.

First real call checklist: (1) restart the backend; (2) the destination number is in international format and, on a Twilio trial
account, verified; (3) the agent version is right (try 1, then the latest published); (4) press *Call now* and watch *Voice chase
history* and the timeline: any refusal appears there with Sarvam's reason.

An already-finished call (a rehearsal from the probe, or Sarvam's webhook later) can still be posted to
`/webhook/karyakarta-voice-result {case_id, outcome, summary, transcript, call_id}`.

## 8. Verified results (2026-10-02, live agent, scripted merchant)

| Scenario | Result |
|---|---|
| Opening | Greets with the case's contact, business name and item count from the variables |
| 1 Agrees | Explains both items, gives the next step |
| 2 Busy | Asks for a callback time |
| 3 English | Switches to English (once re-asked identity) |
| 4 Approval question | Declines to promise; says the account manager (Priya) will explain |
| 5 Offers OTP | Refuses; documents only via the app's Account Center |
| 7 Wrong number | Apologises and ends |
| 8 Signatory question | Does not discuss it (held back from the agent); defers to the account manager |

Run it yourself: `python scripts/voice_agent_probe.py <case_id> --scenario N [--record]`. `--record` sends the conversation through
n8n (`karyakarta-voice-result`) as a labelled **rehearsal**, so it appears on the case and in Cognee.
