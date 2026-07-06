import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv
from assistant import NSSFAssistant
from scrapper import load_cache, scrape_all_pages

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()


class AppState:
    def __init__(self):
        self.assistant = None
        self.status = "Starting..."
        self.ready = False
        self.error = ""
        self.lock = threading.Lock()

    def load(self):
        if not GROQ_API_KEY:
            self.status = "Missing API key"
            self.error = "GROQ_API_KEY is missing. Add it to backend/.env"
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
                api_key=GROQ_API_KEY,
                nssf_context=context,
            )

            self.ready = True
            self.status = "Ready"

        except Exception as exc:
            self.status = "Startup failed"
            self.error = str(exc)

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
        print("[Backend]", format % args)


def main():
    parser = argparse.ArgumentParser(description="Run NSSF chatbot backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8001, type=int)
    args = parser.parse_args()

    threading.Thread(target=STATE.load, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    url = f"http://{args.host}:{args.port}"

    print(f"Backend running at {url}")
    print(f"Status endpoint: {url}/api/status")

    server.serve_forever()


if __name__ == "__main__":
    main()