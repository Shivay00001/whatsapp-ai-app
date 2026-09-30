#!/usr/bin/env python3
"""
WhatsApp AI Agent webhook server (stdlib only).

Endpoints:
  GET  /webhook   Meta WhatsApp Cloud API verification (hub.verify_token vs VERIFY_TOKEN)
  POST /webhook   Meta WhatsApp inbound -> agent -> Graph API send (if WHATSAPP_TOKEN
                  + WHATSAPP_PHONE_ID set) else logs the reply (dry-run)
  POST /twilio    Twilio-compatible inbound (x-www-form-urlencoded) -> TwiML reply
  POST /api/chat  {"sender": "...", "text": "..."} -> {"reply","lead","booking",...}
  GET  /api/status -> {"llm": "...", "sessions": N}
  GET  /           demo.html chat UI

Run:  python3 webhook.py   (env: PORT, VERIFY_TOKEN, WHATSAPP_TOKEN, WHATSAPP_PHONE_ID,
      LLM_PROVIDER / LLM_MODEL / LLM_API_KEY, BUSINESS_NAME, AGENT_NAME)
"""
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent import WhatsAppAgent, llm_status

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "visionquantech123")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))

agent = WhatsAppAgent()


def send_whatsapp(to, body):
    """Send via Meta Graph API. Returns True on real send, False on dry-run/failure."""
    if not (WHATSAPP_TOKEN and PHONE_ID):
        print("[DRY-RUN] to=%s reply=%.120s" % (to, body.replace("\n", " ")), flush=True)
        return False
    url = "https://graph.facebook.com/v19.0/%s/messages" % PHONE_ID
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": "Bearer " + WHATSAPP_TOKEN,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print("[SEND] to=%s status=%s" % (to, resp.status), flush=True)
        return True
    except Exception as e:
        print("[SEND-FAIL] to=%s err=%s" % (to, e), flush=True)
        return False


def handle_meta_payload(data):
    """Parse Meta webhook JSON -> list of (sender, text). Ignores statuses/errors."""
    out = []
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    sender = msg.get("from", "")
                    text = (msg.get("text") or {}).get("body", "")
                    if sender and text:
                        out.append((sender, text))
    except Exception as e:
        print("[PARSE-ERR]", e, flush=True)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "WQAgent/1.0"

    def log_message(self, fmt, *args):  # quieter logs
        print("[HTTP] " + fmt % args, flush=True)

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json")

    # ------------------------------------------------------------- GET ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path == "/webhook":  # Meta verification handshake
            mode = qs.get("hub.mode", [""])[0]
            token = qs.get("hub.verify_token", [""])[0]
            challenge = qs.get("hub.challenge", [""])[0]
            if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
                return self._send(200, challenge)
            return self._send(403, "verification failed")

        if path == "/api/status":
            return self._json(200, {"llm": llm_status(),
                                    "sessions": len(agent.sessions),
                                    "whatsapp_live": bool(WHATSAPP_TOKEN and PHONE_ID)})

        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "demo.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send(404, "demo.html not found")

        return self._send(404, "not found")

    # ------------------------------------------------------------ POST ---
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")

        if path == "/webhook":  # Meta WhatsApp inbound
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                return self._send(400, "bad json")
            for sender, text in handle_meta_payload(data):
                result = agent.handle_message(sender, text)
                send_whatsapp(sender, result["reply"])
            return self._send(200, "ok")

        if path == "/twilio":  # Twilio inbound (form-encoded)
            form = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
            sender = form.get("From", [""])[0]
            text = form.get("Body", [""])[0]
            result = agent.handle_message(sender or "twilio", text)
            twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                     "<Response><Message>%s</Message></Response>") % (
                         result["reply"].replace("&", "&amp;")
                         .replace("<", "&lt;").replace(">", "&gt;"))
            return self._send(200, twiml, "text/xml; charset=utf-8")

        if path == "/api/chat":  # demo / testing API
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                return self._send(400, "bad json")
            sender = str(data.get("sender", "demo-user"))
            text = str(data.get("text", ""))
            return self._json(200, agent.handle_message(sender, text))

        return self._send(404, "not found")


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("WhatsApp AI Agent on :%d  |  %s" % (PORT, llm_status()), flush=True)
    print("Demo: http://localhost:%d/   API: POST /api/chat" % PORT, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
