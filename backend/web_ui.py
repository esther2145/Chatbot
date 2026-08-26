import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        _reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from assistant import NSSFAssistant
from scrapper import load_cache, scrape_all_pages

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

AZURE_CHAT_API_KEY = os.getenv("AZURE_CHAT_API_KEY", "").strip()
AZURE_CHAT_ENDPOINT = os.getenv("AZURE_CHAT_ENDPOINT", "").strip()
AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_CHAT_DEPLOYMENT", "").strip()
AZURE_CHAT_API_VERSION = os.getenv("AZURE_CHAT_API_VERSION", "2024-12-01-preview").strip()


class AppState:
    def __init__(self):
        self.assistant = None
        self.status = "Starting..."
        self.ready = False
        self.error = ""
        self.lock = threading.Lock()

    def load(self):
        if not AZURE_CHAT_API_KEY:
            self.status = "Missing API key"
            self.error = "AZURE_CHAT_API_KEY is missing. Add it to backend/.env"
            return

        if not AZURE_CHAT_ENDPOINT:
            self.status = "Missing endpoint"
            self.error = "AZURE_CHAT_ENDPOINT is missing. Add it to backend/.env"
            return

        if not AZURE_CHAT_DEPLOYMENT:
            self.status = "Missing deployment"
            self.error = "AZURE_CHAT_DEPLOYMENT is missing. Add it to backend/.env"
            return

        try:
            self.status = "Loading cached NSSF information..."
            context = load_cache()

            if not context.strip():
                self.status = "Scraping NSSF website..."
                context = scrape_all_pages()

            if not context.strip():
                self.status = "No data loaded"
                self.error = "No NSSF information was loaded."
                return

            self.status = "Connecting assistant..."
            self.assistant = NSSFAssistant(
                api_key=AZURE_CHAT_API_KEY,
                endpoint=AZURE_CHAT_ENDPOINT,
                deployment=AZURE_CHAT_DEPLOYMENT,
                api_version=AZURE_CHAT_API_VERSION,
                nssf_context=context,
            )

            self.ready = True
            self.status = "Ready"

        except Exception as exc:
            self.status = "Startup failed"
            self.error = str(exc)
            traceback.print_exc()

    def ask(self, question):
        if not self.ready or not self.assistant:
            return {
                "ok": False,
                "answer": "",
                "error": "Assistant is still loading.",
            }

        with self.lock:
            answer = self.assistant.ask(question)

        return {
            "ok": True,
            "answer": answer,
            "error": "",
        }


STATE = AppState()


class WebUIHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/status":
            self._send_json({
                "ready": STATE.ready,
                "status": STATE.status,
                "error": STATE.error,
            })
            return

        self._send_json({"ok": True, "message": "NSSF backend is running"})

    def do_POST(self):
        if self.path != "/api/ask":
            self._send_json(
                {"ok": False, "answer": "", "error": "Endpoint not found"},
                status=404,
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            question = payload.get("question", "").strip()

            if not question:
                self._send_json(
                    {"ok": False, "answer": "", "error": "Question is empty"},
                    status=400,
                )
                return

            self._send_json(STATE.ask(question))

        except Exception as exc:
            self._send_json(
                {"ok": False, "answer": "", "error": str(exc)},
                status=500,
            )

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if self.path == "/api/status" and str(args[1]) == "200":
            return
        print("[Backend]", format % args)


def main():
    print(
        "web_ui.py is retired. It served port 8001 with an old Groq-based "
        "prototype and kept stealing the port from the real backend "
        "(backend/app/main.py), which the frontend actually talks to.\n\n"
        "Start the real backend instead, from the project root:\n"
        "  docker compose up -d qdrant backend\n",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()