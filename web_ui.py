import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from assistant import NSSFAssistant
from scrapper import load_cache, scrape_all_pages


GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

class AppState:
    def __init__(self):
        self.assistant = None
        self.status = "Starting..."
        self.ready = False
        self.error = ""
        self.lock = threading.Lock()

    def load(self):
        if not GROQ_API_KEY:
            self.error = "GROQ_API_KEY is missing. Set it before starting the web UI."
            self.status = "Missing API key"
            return

        try:
            self.status = "Loading cached NSSF information..."
            context = load_cache()

            if not context.strip():
                self.status = "No cache found. Scraping NSSF website..."
                context = scrape_all_pages()

            if not context.strip():
                self.error = "No NSSF information was loaded."
                self.status = "No data loaded"
                return

            self.status = "Connecting assistant..."
            self.assistant = NSSFAssistant(api_key=GROQ_API_KEY, nssf_context=context)
            self.ready = True
            self.status = "Ready"
        except Exception as exc:
            self.error = str(exc)
            self.status = "Startup failed"

    def ask(self, question):
        if not self.ready or not self.assistant:
            return {"ok": False, "answer": "", "error": "Assistant is still loading."}

        with self.lock:
            answer = self.assistant.ask(question)

        return {"ok": True, "answer": answer, "error": ""}


STATE = AppState()


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NSSF Uganda Web Assistant</title>
  <style>
    :root {
      --bg: #1a0533;
      --panel: #2a1050;
      --panel-2: #351466;
      --border: #5a2ea0;
      --text: #f8f0ff;
      --muted: #c4a8ff;
      --gold: #ffd166;
      --green: #06d6a0;
      --red: #ef476f;
      --pink: #ff4daa;
      --white: #ffffff;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
    }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }

    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 16px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }

    .logo {
      background: #6c2bd9;
      color: var(--white);
      font-weight: 800;
      padding: 8px 12px;
      border-radius: 6px;
      letter-spacing: 0;
    }

    h1 {
      margin: 0;
      color: var(--gold);
      font-size: 22px;
      line-height: 1.15;
    }

    .status {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }

    .mode {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    button {
      border: 0;
      border-radius: 7px;
      padding: 11px 15px;
      font-weight: 700;
      cursor: pointer;
      color: var(--white);
      background: #6c2bd9;
      font-size: 14px;
    }

    button:disabled {
      cursor: wait;
      opacity: 0.65;
    }

    .voice-on {
      background: var(--green);
      color: #0d2b22;
    }

    .voice-off {
      background: #6c2bd9;
      color: var(--white);
    }

    main {
      display: grid;
      grid-template-columns: 230px 1fr;
      min-height: 0;
    }

    .side {
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .avatar {
      height: 220px;
      border-radius: 8px;
      background: var(--panel-2);
      border: 1px solid var(--border);
      display: grid;
      place-items: center;
      text-align: center;
      padding: 14px;
    }

    .avatar-face {
      width: 96px;
      height: 96px;
      border-radius: 50%;
      background: var(--gold);
      color: var(--panel);
      display: grid;
      place-items: center;
      font-size: 42px;
      font-weight: 800;
      margin: 0 auto 14px;
    }

    .tip {
      color: var(--muted);
      line-height: 1.45;
      font-size: 14px;
    }

    .chat-wrap {
      min-height: 0;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .chat {
      min-height: 0;
      flex: 1;
      overflow: auto;
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }

    .message {
      max-width: 820px;
      margin: 0 0 16px;
      line-height: 1.5;
    }

    .name {
      font-weight: 800;
      margin-bottom: 5px;
      font-size: 14px;
    }

    .bot .name {
      color: var(--green);
    }

    .user .name {
      color: var(--pink);
    }

    .system {
      color: var(--muted);
      font-style: italic;
      font-size: 14px;
    }

    footer {
      background: var(--panel);
      border-top: 1px solid var(--border);
      padding: 14px 18px;
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: end;
    }

    textarea {
      width: 100%;
      min-height: 54px;
      max-height: 140px;
      resize: vertical;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg);
      color: var(--text);
      padding: 12px;
      font: 15px Arial, Helvetica, sans-serif;
      outline: none;
    }

    textarea:focus {
      border-color: var(--gold);
    }

    .send {
      background: var(--green);
      color: #0d2b22;
      min-width: 96px;
    }

    .mic {
      background: var(--red);
      min-width: 110px;
    }

    .mic.listening {
      background: var(--gold);
      color: #2a1050;
    }

    @media (max-width: 760px) {
      header {
        align-items: flex-start;
        flex-direction: column;
      }

      main {
        grid-template-columns: 1fr;
      }

      .side {
        display: none;
      }

      footer {
        grid-template-columns: 1fr;
      }

      .send,
      .mic {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <div class="logo">NSSF</div>
        <div>
          <h1>NSSF Assistant</h1>
          <div id="status" class="status">Starting...</div>
        </div>
      </div>
      <div class="mode">
        <button id="voiceToggle" class="voice-on" type="button">Voice replies: ON</button>
      </div>
    </header>

    <main>
      <aside class="side">
        <div class="avatar">
          <div>
            <div class="avatar-face">N</div>
            <strong>Nicky</strong>
            <p class="tip">Ask about NSSF Uganda membership, benefits, contributions, employer services, and self-service options.</p>
          </div>
        </div>
        <p class="tip">Use the microphone for voice input, or type your question below. Spoken replies can be switched off at the top.</p>
      </aside>

      <section class="chat-wrap">
        <div id="chat" class="chat">
          <div class="message bot">
            <div class="name">Nicky</div>
            <div>Hello. I am loading NSSF Uganda information. You can type a question or use the microphone.</div>
          </div>
        </div>
      </section>
    </main>

    <footer>
      <textarea id="question" placeholder="Type your question here..."></textarea>
      <button id="micBtn" class="mic" type="button">Speak</button>
      <button id="sendBtn" class="send" type="button">Send</button>
    </footer>
  </div>

  <script>
    const chat = document.getElementById("chat");
    const statusEl = document.getElementById("status");
    const questionEl = document.getElementById("question");
    const sendBtn = document.getElementById("sendBtn");
    const micBtn = document.getElementById("micBtn");
    const voiceToggle = document.getElementById("voiceToggle");

    let ready = false;
    let voiceReplies = true;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    function addMessage(sender, text, kind) {
      const item = document.createElement("div");
      item.className = `message ${kind}`;
      item.innerHTML = `<div class="name"></div><div></div>`;
      item.children[0].textContent = sender;
      item.children[1].textContent = text;
      chat.appendChild(item);
      chat.scrollTop = chat.scrollHeight;
    }

    function addSystem(text) {
      const item = document.createElement("div");
      item.className = "message system";
      item.textContent = text;
      chat.appendChild(item);
      chat.scrollTop = chat.scrollHeight;
    }

    function speak(text) {
      if (!voiceReplies || !window.speechSynthesis) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1;
      utterance.pitch = 1;
      window.speechSynthesis.speak(utterance);
    }

    async function checkStatus() {
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        ready = data.ready;
        statusEl.textContent = data.error ? `${data.status}: ${data.error}` : data.status;
        sendBtn.disabled = !ready;
        micBtn.disabled = !ready || !SpeechRecognition;
        if (!ready) setTimeout(checkStatus, 1200);
      } catch (error) {
        statusEl.textContent = "Could not connect to the local web server.";
        sendBtn.disabled = true;
        micBtn.disabled = true;
      }
    }

    async function askQuestion(question) {
      const clean = question.trim();
      if (!clean || !ready) return;

      addMessage("You", clean, "user");
      questionEl.value = "";
      sendBtn.disabled = true;
      micBtn.disabled = true;
      statusEl.textContent = "Thinking...";

      try {
        const res = await fetch("/api/ask", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: clean})
        });
        const data = await res.json();
        if (!data.ok) {
          addSystem(data.error || "Something went wrong.");
        } else {
          addMessage("Nicky", data.answer, "bot");
          speak(data.answer);
        }
      } catch (error) {
        addSystem("Could not reach the assistant server.");
      } finally {
        statusEl.textContent = "Ready";
        sendBtn.disabled = false;
        micBtn.disabled = !SpeechRecognition;
        questionEl.focus();
      }
    }

    voiceToggle.addEventListener("click", () => {
      voiceReplies = !voiceReplies;
      if (voiceReplies) {
        voiceToggle.textContent = "Voice replies: ON";
        voiceToggle.className = "voice-on";
        addSystem("Voice replies turned on.");
      } else {
        window.speechSynthesis?.cancel();
        voiceToggle.textContent = "Text replies only";
        voiceToggle.className = "voice-off";
        addSystem("Voice replies turned off.");
      }
    });

    sendBtn.addEventListener("click", () => askQuestion(questionEl.value));
    questionEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        askQuestion(questionEl.value);
      }
    });

    if (SpeechRecognition) {
      recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        micBtn.textContent = "Listening...";
        micBtn.classList.add("listening");
        statusEl.textContent = "Listening...";
      };

      recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        questionEl.value = text;
        askQuestion(text);
      };

      recognition.onerror = () => {
        addSystem("Voice input failed. Try typing your question.");
      };

      recognition.onend = () => {
        micBtn.textContent = "Speak";
        micBtn.classList.remove("listening");
        if (ready) statusEl.textContent = "Ready";
      };

      micBtn.addEventListener("click", () => recognition.start());
    } else {
      micBtn.disabled = true;
      micBtn.textContent = "No mic support";
      addSystem("Voice input works best in Chrome or Edge on localhost.");
    }

    sendBtn.disabled = true;
    micBtn.disabled = true;
    checkStatus();
  </script>
</body>
</html>
"""


class WebUIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(HTML)
            return

        if self.path == "/api/status":
            self._send_json(
                {
                    "ready": STATE.ready,
                    "status": STATE.status,
                    "error": STATE.error,
                }
            )
            return

        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/ask":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            question = payload.get("question", "").strip()

            if not question:
                self._send_json({"ok": False, "answer": "", "error": "Question is empty."})
                return

            self._send_json(STATE.ask(question))
        except Exception as exc:
            self._send_json({"ok": False, "answer": "", "error": str(exc)}, status=500)

    def log_message(self, format, *args):
        print("[WebUI]", format % args)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Run the NSSF browser-based chatbot UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8001, type=int)
    args = parser.parse_args()

    threading.Thread(target=STATE.load, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"[WebUI] Open {url} in your browser.")
    print("[WebUI] Press Ctrl+C here to stop the server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebUI] Stopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
