# WhatsApp AI Agent 🤖

A working WhatsApp business agent: human-like chat in **English / Hindi / Hinglish**,
**lead qualification** (name → need → budget → timeline), **FAQ handling**, and
**appointment booking** with confirmation summary. Stdlib only — no pip installs.

## Quick start

```bash
cd whatsapp-ai-agent
python3 webhook.py
```

Open the demo: **http://localhost:8000/** — chat in the UI and watch the lead
panel (name / need / budget / timeline + booking) fill live as you talk.

Try: `Namaste` → `Mera naam Rahul hai` → `Mujhe website chahiye` →
`Budget 20000 tak hai` → `Next week tak chahiye` → `Haan` → `kal` →
`shaam 5 baje` → `haan`

## How it works

- `agent.py` — the brain. Per-sender sessions (language, lead, booking, stage,
  history). Detects English/Hindi/Hinglish and mirrors it. Replies come from a
  free LLM via `llm_provider.chat()` when configured; otherwise a complete
  rule-based scripted flow handles greeting → qualification → FAQs → booking.
  Lead extraction (regex/date/time parsers) runs identically in both modes.
- `webhook.py` — stdlib `http.server`:
  - `GET /webhook` — Meta WhatsApp Cloud API verification (`VERIFY_TOKEN`)
  - `POST /webhook` — Meta inbound messages → agent → sends reply via Graph API
    (only if `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_ID` are set, else dry-run logs)
  - `POST /twilio` — Twilio WhatsApp inbound (form-encoded) → TwiML reply
  - `POST /api/chat` — `{"sender": "...", "text": "..."}` →
    `{"reply": ..., "lead": {...}, "booking": {...}, "language": ..., "stage": ...}`
  - `GET /api/status` — LLM mode + session count
  - `GET /` — the demo chat UI
- `demo.html` — single-file chat UI + live lead panel, talks to `/api/chat`.
- `llm_provider.py` — shared free-LLM client (Groq / Gemini / Mistral /
  OpenRouter / Ollama), OpenAI-compatible, stdlib only.

## Free LLM setup (optional but recommended)

Without a key the agent runs fully in rule-based mode. With a free key, replies
become LLM-generated (extraction still rule-based, so it's reliable).

```bash
# Groq — free tier, no credit card: https://console.groq.com
export LLM_PROVIDER=groq
export LLM_MODEL=openai/gpt-oss-120b   # or: gpt-oss-20b, qwen/qwen3.8-27b
export LLM_API_KEY=gsk_your_key_here
python3 webhook.py
```

Alternatives (all have free tiers, no card — see
`~/workspace/research/2026-09-28-free-llm-api-landscape.md`):
`LLM_PROVIDER=gemini` (AI Studio), `mistral` (La Plateforme),
`openrouter` (`:free` models), `ollama` (local, no key).

## Connect real WhatsApp — honest notes

**Meta WhatsApp Cloud API (recommended, free to start):**
1. Create a Meta developer account → new app → add the WhatsApp product.
2. You get a **test number instantly** — webhook works in sandbox right away.
3. For production (your own number, customers messaging you): you need a
   WhatsApp Business Account, an approved **display name**, and Meta's review.
   Messaging itself has a free tier (roughly 1,000 free conversations/month);
   beyond that Meta charges per conversation.
4. Point Meta's webhook at `https://YOUR-SERVER/webhook` with callback URL +
   verify token = your `VERIFY_TOKEN`, subscribe to `messages`.
5. Set `WHATSAPP_TOKEN` (permanent access token) and `WHATSAPP_PHONE_ID`.

**Twilio alternative:** Twilio's WhatsApp sandbox works for testing; production
needs Twilio's WhatsApp approval too. Point Twilio's inbound webhook at
`https://YOUR-SERVER/twilio`.

This app never claims to bypass Meta/Twilio approval — anyone telling you
otherwise is selling something.

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | server port |
| `VERIFY_TOKEN` | `visionquantech123` | Meta webhook verify token (change it!) |
| `WHATSAPP_TOKEN` | _(unset)_ | Meta Graph API token — enables real sends |
| `WHATSAPP_PHONE_ID` | _(unset)_ | Meta phone number ID |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | _(unset)_ | free LLM (Groq etc.) |
| `BUSINESS_NAME` / `AGENT_NAME` | `VisionQuantech` / `Arjun` | branding |

## Test

```bash
python3 -m py_compile agent.py webhook.py llm_provider.py
PORT=8765 python3 webhook.py &
# Meta verification handshake:
curl "localhost:8765/webhook?hub.mode=subscribe&hub.verify_token=visionquantech123&hub.challenge=CHALLENGE"
# chat API:
curl -s localhost:8765/api/chat -H 'Content-Type: application/json' \
  -d '{"sender":"u1","text":"Namaste"}'
```

Every advertised feature runs — no stubs, no placeholders.
