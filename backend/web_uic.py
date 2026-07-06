import argparse
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from assistant import NSSFAssistant
from scrapper import scrape_all_pages  
from chat_db import init_db, create_session, save_message, get_all_sessions, get_session_messages, delete_session

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


class AppState:
    def __init__(self):
        self.assistant = None
        self.status    = "Starting..."
        self.ready     = False
        self.error     = ""
        self.lock      = threading.Lock()
        self.session_id = None

    def load(self):
        if not GROQ_API_KEY:
            self.error  = "GROQ_API_KEY is missing. Set it before starting."
            self.status = "Missing API key"
            return

        try:
            # ✅ Try cache first, fall back to live scrape
            self.status = "Loading cached NSSF information..."
            from scrapper import load_cache
            raw = load_cache()

            # load_cache returns a dict {"content": "..."} or empty string
            if isinstance(raw, dict):
                context = raw.get("content", "")
            else:
                context = raw or ""

            if not context.strip():
                self.status = "No cache found. Scraping NSSF website..."
                context = scrape_all_pages()

            if not context.strip():
                self.error  = "No NSSF information could be loaded."
                self.status = "No data loaded"
                return

            self.status    = "Connecting to Groq assistant..."
            self.assistant = NSSFAssistant(api_key=GROQ_API_KEY,
                                           nssf_context=context)
            init_db()
            self.session_id = create_session()
            self.ready  = True
            self.status = "Ready"

        except Exception as exc:
            self.error  = str(exc)
            self.status = "Startup failed"

    def ask(self, question: str, session_id: int = None) -> dict:
        if not self.ready or not self.assistant:
            return {"ok": False, "answer": "",
                    "error": "Assistant is still loading. Please wait."}
        with self.lock:
            if session_id:
                self.session_id = session_id
            elif not self.session_id:
                self.session_id = create_session()

            answer = self.assistant.ask(question)
            save_message(self.session_id, "User", question)
            save_message(self.session_id, "Nicky", answer)

        return {"ok": True, "answer": answer, "error": "", "session_id": self.session_id}

    def new_session(self) -> dict:
        with self.lock:
            self.session_id = create_session()
        return {"ok": True, "session_id": self.session_id}


STATE = AppState()


# ── HTML page ─────────────────────────────────────────────────────────────────
HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NSSF Uganda Assistant</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&family=Inter:wght@400;500;600&display=swap');

    :root {
      --bg:      #07111F;
      --ember:   #0F2A44;
      --amber:   #2563EB;
      --gold:    #FBBF24;
      --cream:   #F8FAFC;
      --sage:    #22C55E;
      --rose:    #EF4444;
      --slate:   #0B1726;
      --slate2:  #132235;
      --muted:   #94A3B8;
      --border:  #274763;
      --white:   #FFFFFF;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--cream);
      font-family: 'Inter', Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* ── HEADER ── */
    header {
      background: var(--ember);
      padding: 14px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
      border-bottom: 2px solid var(--border);
      flex-shrink: 0;
    }

    .logo {
      background: var(--gold);
      color: var(--bg);
      font-family: 'Nunito', sans-serif;
      font-weight: 900;
      font-size: 15px;
      padding: 8px 14px;
      border-radius: 6px;
      letter-spacing: 0.05em;
      flex-shrink: 0;
    }

    .header-text h1 {
      font-family: 'Nunito', sans-serif;
      font-size: 20px;
      font-weight: 800;
      color: var(--gold);
      line-height: 1;
    }

    #statusEl {
      font-size: 12px;
      color: var(--muted);
      margin-top: 3px;
    }

    .header-right {
      margin-left: auto;
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .dots span {
      display: inline-block;
      width: 11px;
      height: 11px;
      border-radius: 50%;
      margin-left: 5px;
    }

    /* ── TICKER ── */
    .ticker {
      background: var(--slate2);
      border-bottom: 1px solid var(--border);
      overflow: hidden;
      padding: 6px 0;
      flex-shrink: 0;
    }

    .ticker-inner {
      display: inline-block;
      white-space: nowrap;
      animation: ticker 30s linear infinite;
      color: var(--amber);
      font-size: 12px;
    }

    @keyframes ticker {
      from { transform: translateX(100vw); }
      to   { transform: translateX(-100%); }
    }

    /* ── MAIN LAYOUT ── */
    .main {
      display: flex;
      flex: 1;
      min-height: 0;
      overflow: hidden;
    }

    /* ── NICKY SIDEBAR ── */
    .sidebar {
      width: 220px;
      flex-shrink: 0;
      background: var(--ember);
      border-right: 2px solid var(--border);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px 12px;
      gap: 14px;
    }

    .sidebar-label {
      font-family: 'Nunito', sans-serif;
      font-size: 13px;
      font-weight: 800;
      color: var(--gold);
      letter-spacing: 0.08em;
    }

    /* ── STICKMAN SVG ── */
    #nicky { overflow: visible; }

    /* Idle bob */
    #nicky-group { animation: bob 3s ease-in-out infinite; transform-origin: 55px 100px; }
    @keyframes bob { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-5px);} }

    /* Arm wave — triggered by class */
    #arm-l { transform-origin: 43px 52px; }
    #arm-r { transform-origin: 67px 52px; }
    .nicky-wave #arm-l { animation: wave-l 0.5s ease-in-out infinite alternate; }
    .nicky-wave #arm-r { animation: wave-r 0.5s ease-in-out infinite alternate; }
    @keyframes wave-l { from{transform:rotate(0deg);} to{transform:rotate(-35deg);} }
    @keyframes wave-r { from{transform:rotate(0deg);} to{transform:rotate(35deg);}  }

    .nicky-think #arm-r { animation: think 1.2s ease-in-out infinite alternate; }
    @keyframes think { from{transform:rotate(-40deg);} to{transform:rotate(-55deg);} }

    /* Speech bubble */
    .bubble-wrap {
      position: relative;
      background: var(--gold);
      color: var(--bg);
      border-radius: 12px;
      padding: 8px 12px;
      font-family: 'Nunito', sans-serif;
      font-size: 12px;
      font-weight: 800;
      text-align: center;
      width: 160px;
      animation: bob 3s ease-in-out infinite;
    }

    .bubble-wrap::after {
      content: '';
      position: absolute;
      bottom: -9px;
      left: 50%;
      transform: translateX(-50%);
      border: 9px solid transparent;
      border-top-color: var(--gold);
      border-bottom: none;
    }

    .sidebar-tip {
      font-size: 12px;
      color: var(--muted);
      text-align: center;
      line-height: 1.5;
      padding: 0 4px;
    }

    /* ── CHAT AREA ── */
    .chat-col {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
    }

    .chat-header {
      background: var(--slate2);
      border-bottom: 1px solid var(--border);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }

    .chat-header-title {
      font-family: 'Nunito', sans-serif;
      font-weight: 800;
      font-size: 14px;
      color: var(--gold);
    }

    #msgCount {
      font-size: 11px;
      color: var(--muted);
    }

    #chat {
      flex: 1;
      overflow-y: auto;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      background: var(--slate);
    }

    /* Scrollbar */
    #chat::-webkit-scrollbar { width: 6px; }
    #chat::-webkit-scrollbar-track { background: var(--slate); }
    #chat::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

    .message { display: flex; gap: 10px; align-items: flex-end; max-width: 100%; }
    .message.user { flex-direction: row-reverse; }

    .av {
      width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      font-family: 'Nunito', sans-serif; font-weight: 800; font-size: 13px;
    }
    .av.bot  { background: var(--amber); color: var(--bg); }
    .av.user { background: var(--rose);  color: var(--white); }

    .bubble {
      max-width: 72%;
      padding: 10px 15px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.6;
    }
    .bot  .bubble { background: var(--slate2); color: var(--cream); border-bottom-left-radius: 4px; }
    .user .bubble { background: var(--rose);   color: var(--white); border-bottom-right-radius: 4px; }

    .msg-name {
      font-size: 11px; font-weight: 700;
      margin-bottom: 4px;
      color: var(--muted);
    }

    .system-msg {
      color: var(--muted);
      font-style: italic;
      font-size: 13px;
      text-align: center;
      padding: 4px 0;
    }

    /* Typing dots */
    .typing { display: flex; gap: 5px; align-items: center; padding: 2px 0; }
    .typing span {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--muted);
      animation: dot 1.1s infinite;
    }
    .typing span:nth-child(2) { animation-delay: .18s; }
    .typing span:nth-child(3) { animation-delay: .36s; }
    @keyframes dot { 0%,80%,100%{transform:translateY(0);} 40%{transform:translateY(-7px);} }

    /* Message entrance */
    .message { animation: fadeUp 0.25s ease; }
    @keyframes fadeUp { from{opacity:0;transform:translateY(8px);} to{opacity:1;transform:translateY(0);} }

    /* ── WAVEFORM ── */
    .waveform {
      background: var(--bg);
      border-top: 1px solid var(--border);
      height: 46px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 3px;
      padding: 0 18px;
      flex-shrink: 0;
    }

    .wbar {
      width: 4px;
      border-radius: 2px;
      background: var(--border);
      transition: height 0.12s ease, background 0.3s;
    }

    /* ── INPUT FOOTER ── */
    footer {
      background: var(--ember);
      border-top: 2px solid var(--border);
      padding: 14px 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      flex-shrink: 0;
    }

    .input-row {
      display: flex;
      gap: 10px;
      align-items: flex-end;
    }

    .input-wrap {
      flex: 1;
      border: 2px solid var(--gold);
      border-radius: 10px;
      background: var(--slate);
      overflow: hidden;
    }

    textarea {
      width: 100%;
      min-height: 50px;
      max-height: 130px;
      resize: vertical;
      background: transparent;
      color: var(--cream);
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      padding: 12px 14px;
      border: none;
      outline: none;
    }

    textarea::placeholder { color: var(--muted); }

    .btn {
      border: none;
      border-radius: 10px;
      padding: 13px 20px;
      font-family: 'Nunito', sans-serif;
      font-weight: 800;
      font-size: 14px;
      cursor: pointer;
      transition: transform 0.12s, opacity 0.2s;
      flex-shrink: 0;
    }
    .btn:hover:not(:disabled) { transform: scale(1.04); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .btn-send { background: var(--gold); color: var(--bg); }
    .btn-mic  { background: var(--rose); color: var(--white); }
    .btn-mic.listening { background: var(--sage); color: var(--bg); }
    .btn-voice { background: var(--slate2); color: var(--cream); font-size: 12px; padding: 8px 14px; }

    .footer-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .footer-hint { font-size: 11px; color: var(--muted); }

    /* ── PULSE RING around mic ── */
    .mic-wrap { position: relative; display: flex; align-items: center; }
    .pulse-ring {
      position: absolute;
      inset: -6px;
      border-radius: 14px;
      border: 2px solid var(--rose);
      opacity: 0;
      pointer-events: none;
    }
    .mic-wrap.listening .pulse-ring {
      animation: pulse-ring 0.9s ease-out infinite;
    }
    @keyframes pulse-ring {
      0%   { transform: scale(1);    opacity: 0.8; }
      100% { transform: scale(1.35); opacity: 0; }
    }

    /* ── RESPONSIVE ── */
    @media (max-width: 700px) {
      .sidebar { display: none; }
      .input-row { flex-wrap: wrap; }
      .btn { width: 100%; }
    }

    /* ── HISTORY SIDEBAR ── */
    .history-panel {
      width: 240px;
      flex-shrink: 0;
      background: var(--slate2);
      border-right: 2px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .history-header {
      padding: 14px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }

    .history-title {
      font-family: 'Nunito', sans-serif;
      font-size: 13px;
      font-weight: 800;
      color: var(--gold);
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }

    .btn-new {
      width: 100%;
      background: var(--gold);
      color: var(--bg);
      border: none;
      border-radius: 6px;
      padding: 8px 12px;
      font-family: 'Nunito', sans-serif;
      font-weight: 700;
      font-size: 12px;
      cursor: pointer;
    }

    .history-list {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .history-item {
      padding: 10px 10px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      position: relative;
    }

    .history-item:hover {
      background: var(--slate);
      border-color: var(--gold);
    }

    .history-item.active {
      background: var(--amber);
      color: var(--bg);
    }

    .history-item-delete {
      position: absolute;
      top: 4px;
      right: 4px;
      background: transparent;
      border: none;
      color: var(--rose);
      cursor: pointer;
      display: none;
    }

    .history-item:hover .history-item-delete {
      display: block;
    }
  </style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="logo">NSSF</div>
  <div class="header-text">
    <h1>Uganda Assistant</h1>
    <div id="statusEl">Starting up...</div>
  </div>
  <div class="header-right">
    <div class="dots">
      <span style="background:#FF6B6B"></span>
      <span style="background:#FFB627"></span>
      <span style="background:#2ECC71"></span>
    </div>
  </div>
</header>

<!-- HISTORY SIDEBAR -->
<aside class="history-panel">
  <div class="history-header">
    <div class="history-title">📜 History</div>
    <button class="btn-new" onclick="newChat()">+ New Chat</button>
  </div>
  <div class="history-list" id="historyList"></div>
</aside>

<!-- TICKER -->
<div class="ticker">
  <span class="ticker-inner">
    ✦ NSSF Uganda — Securing Your Future &nbsp;|&nbsp;
    Helpline: 0800 100 066 (toll free) &nbsp;|&nbsp;
    Mon–Fri 8am–5pm &nbsp;|&nbsp;
    Visit nssf.or.ug &nbsp;|&nbsp;
    Register online &nbsp;|&nbsp;
    Check your balance via self-service portal ✦ &nbsp;&nbsp;&nbsp;&nbsp;
    ✦ NSSF Uganda — Securing Your Future &nbsp;|&nbsp;
    Helpline: 0800 100 066 (toll free) &nbsp;|&nbsp;
    Mon–Fri 8am–5pm &nbsp;|&nbsp;
    Visit nssf.or.ug ✦
  </span>
</div>

<!-- MAIN -->
<div class="main">

  <!-- NICKY SIDEBAR -->
  <aside class="sidebar">
    <div class="sidebar-label">NICKY</div>

    <div class="bubble-wrap" id="bubble">Hello!<br>Ask me anything!</div>

    <!-- Animated stickman -->
    <svg id="nicky" width="110" height="200" viewBox="0 0 110 200">
      <g id="nicky-group">
        <!-- Head -->
        <circle cx="55" cy="28" r="22" fill="#FFB627" stroke="#C45000" stroke-width="2"/>
        <!-- Eyes -->
        <circle cx="47" cy="24" r="4" fill="#120800"/>
        <circle cx="63" cy="24" r="4" fill="#120800"/>
        <!-- Eye shine -->
        <circle cx="45" cy="22" r="1.5" fill="white"/>
        <circle cx="61" cy="22" r="1.5" fill="white"/>
        <!-- Smile -->
        <path id="mouth" d="M45 34 Q55 42 65 34" fill="none" stroke="#120800" stroke-width="2.5" stroke-linecap="round"/>
        <!-- Blush -->
        <ellipse cx="38" cy="30" rx="6" ry="4" fill="#FF6B6B" opacity="0.45"/>
        <ellipse cx="72" cy="30" rx="6" ry="4" fill="#FF6B6B" opacity="0.45"/>
        <!-- Body -->
        <rect x="37" y="52" width="36" height="44" rx="8" fill="#8B2500" stroke="#C45000" stroke-width="1.5"/>
        <!-- Badge -->
        <rect x="43" y="62" width="24" height="16" rx="3" fill="#FFB627"/>
        <text x="55" y="74" text-anchor="middle" font-size="8" font-weight="900" fill="#120800" font-family="Arial">NSSF</text>
        <!-- Arms -->
        <g id="arm-l">
          <line x1="37" y1="62" x2="12" y2="82" stroke="#FFB627" stroke-width="5" stroke-linecap="round"/>
          <circle cx="10" cy="84" r="6" fill="#FFB627" stroke="#C45000" stroke-width="1.5"/>
        </g>
        <g id="arm-r">
          <line x1="73" y1="62" x2="98" y2="82" stroke="#FFB627" stroke-width="5" stroke-linecap="round"/>
          <circle cx="100" cy="84" r="6" fill="#FFB627" stroke="#C45000" stroke-width="1.5"/>
        </g>
        <!-- Legs -->
        <line x1="55" y1="96" x2="38" y2="140" stroke="#FFB627" stroke-width="5" stroke-linecap="round"/>
        <line x1="55" y1="96" x2="72" y2="140" stroke="#FFB627" stroke-width="5" stroke-linecap="round"/>
        <!-- Shoes -->
        <ellipse cx="34" cy="143" rx="10" ry="6" fill="#8B2500" stroke="#C45000" stroke-width="1.5"/>
        <ellipse cx="76" cy="143" rx="10" ry="6" fill="#8B2500" stroke="#C45000" stroke-width="1.5"/>
      </g>
    </svg>

    <div class="sidebar-tip">
      Ask about NSSF membership, contributions, benefits, employer services, and self-service options.
    </div>
  </aside>

  <!-- CHAT COLUMN -->
  <div class="chat-col">

    <!-- Chat header -->
    <div class="chat-header">
      <span class="chat-header-title">💬 Conversation</span>
      <span id="msgCount">0 messages</span>
    </div>

    <!-- Messages -->
    <div id="chat">
      <div class="message bot">
        <div class="av bot">N</div>
        <div>
          <div class="msg-name">Nicky</div>
          <div class="bubble">Hello! I am loading the latest NSSF Uganda information. You can type a question or press the mic button to speak.</div>
        </div>
      </div>
    </div>

    <!-- Waveform -->
    <div class="waveform" id="waveform"></div>

  </div>
</div>

<!-- INPUT FOOTER -->
<footer>
  <div class="footer-top">
    <span class="footer-hint">Press Enter to send &nbsp;|&nbsp; Shift+Enter for new line</span>
    <button class="btn btn-voice" id="voiceToggle" type="button">🔊 Voice: ON</button>
  </div>
  <div class="input-row">
    <div class="input-wrap">
      <textarea id="question" placeholder="Type your question here..." rows="2"></textarea>
    </div>
    <div class="mic-wrap" id="micWrap">
      <div class="pulse-ring"></div>
      <button class="btn btn-mic" id="micBtn" type="button" disabled>🎙 Speak</button>
    </div>
    <button class="btn btn-send" id="sendBtn" type="button" disabled>Ask Nicky ➤</button>
  </div>
</footer>

<script>
  // ── Elements ────────────────────────────────────────────────────────────────
  const chatEl      = document.getElementById("chat");
  const statusEl    = document.getElementById("statusEl");
  const questionEl  = document.getElementById("question");
  const sendBtn     = document.getElementById("sendBtn");
  const micBtn      = document.getElementById("micBtn");
  const micWrap     = document.getElementById("micWrap");
  const voiceToggle = document.getElementById("voiceToggle");
  const msgCountEl  = document.getElementById("msgCount");
  const bubbleEl    = document.getElementById("bubble");
  const nickyEl     = document.getElementById("nicky");
  const waveformEl  = document.getElementById("waveform");

  // ── State ───────────────────────────────────────────────────────────────────
  let ready        = false;
  let currentSessionId = null;
  let voiceReplies = true;
  let msgCount     = 0;
  let waveAngle    = 0;
  let waveMode     = "idle";   // idle | listening | speaking | thinking

  // ── Waveform ────────────────────────────────────────────────────────────────
  const NUM_BARS = 28;
  const wbars = [];
  for (let i = 0; i < NUM_BARS; i++) {
    const b = document.createElement("div");
    b.className = "wbar";
    b.style.height = "4px";
    waveformEl.appendChild(b);
    wbars.push(b);
  }

  const waveColours = {
    idle:      "#5A2800",
    listening: "#2ECC71",
    speaking:  "#FFB627",
    thinking:  "#C45000",
  };

  function animateWave() {
    waveAngle += 0.14;
    const col = waveColours[waveMode] || waveColours.idle;
    wbars.forEach((b, i) => {
      let h;
      if (waveMode === "listening") {
        h = 5 + Math.abs(Math.sin(waveAngle * 2.2 + i * 0.5)) * 26;
      } else if (waveMode === "speaking") {
        h = 4 + Math.abs(Math.sin(waveAngle + i * 0.45)) * 20;
      } else if (waveMode === "thinking") {
        h = 3 + Math.abs(Math.sin(waveAngle * 0.9 + i * 0.6)) * 14;
      } else {
        h = 2 + Math.abs(Math.sin(waveAngle * 0.4 + i * 0.3)) * 4;
      }
      b.style.height = h + "px";
      b.style.background = col;
    });
    requestAnimationFrame(animateWave);
  }
  animateWave();

  // ── Nicky reactions ─────────────────────────────────────────────────────────
  const bubbleTexts = {
    idle:      ["Hello! Ask me anything!", "I am here to help!", "What would you like to know?", "Ask me about NSSF!"],
    listening: ["I am listening...", "Go ahead, speak!", "Tell me your question!"],
    thinking:  ["Hmm, let me think...", "Checking NSSF knowledge...", "One moment please!"],
    speaking:  ["Here is what I found!", "Hope that helps!", "Great question!"],
  };

  function setNickyState(state) {
    waveMode = state;
    nickyEl.classList.remove("nicky-wave", "nicky-think");
    if (state === "listening") nickyEl.classList.add("nicky-wave");
    if (state === "thinking")  nickyEl.classList.add("nicky-think");
    const texts = bubbleTexts[state] || bubbleTexts.idle;
    bubbleEl.innerHTML = texts[Math.floor(Math.random() * texts.length)];
  }

  // Rotate idle bubble messages
  setInterval(() => {
    if (waveMode === "idle") setNickyState("idle");
  }, 4000);

  // ── Chat helpers ─────────────────────────────────────────────────────────────
  function addMessage(sender, text, kind) {
    // Remove typing indicator if present
    const typing = document.getElementById("_typing");
    if (typing) typing.remove();

    msgCount++;
    msgCountEl.textContent = msgCount + " message" + (msgCount !== 1 ? "s" : "");

    const row = document.createElement("div");
    row.className = "message " + kind;
    row.innerHTML = `
      <div class="av ${kind}">${kind === "bot" ? "N" : "U"}</div>
      <div>
        <div class="msg-name">${sender}</div>
        <div class="bubble">${escapeHtml(text)}</div>
      </div>`;
    chatEl.appendChild(row);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function addSystem(text) {
    const el = document.createElement("div");
    el.className = "system-msg";
    el.textContent = text;
    chatEl.appendChild(el);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "message bot";
    row.id = "_typing";
    row.innerHTML = `
      <div class="av bot">N</div>
      <div>
        <div class="msg-name">Nicky</div>
        <div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>
      </div>`;
    chatEl.appendChild(row);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function escapeHtml(str) {
    return str.replace(/&/g,"&amp;").replace(/</g,"&lt;")
              .replace(/>/g,"&gt;").replace(/\n/g,"<br>");
  }

  // ── TTS ──────────────────────────────────────────────────────────────────────
  function speak(text) {
    if (!voiceReplies || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 1; utt.pitch = 1;
    utt.onstart = () => setNickyState("speaking");
    utt.onend   = () => setNickyState("idle");
    window.speechSynthesis.speak(utt);
  }

  voiceToggle.addEventListener("click", () => {
    voiceReplies = !voiceReplies;
    if (voiceReplies) {
      voiceToggle.textContent = "🔊 Voice: ON";
      addSystem("Voice replies turned on.");
    } else {
      window.speechSynthesis?.cancel();
      voiceToggle.textContent = "🔇 Voice: OFF";
      addSystem("Voice replies turned off.");
    }
  });
  // ── Load chat history ────────────────────────────────────────────────────────
  async function loadHistory() {
    try {
      const res = await fetch("/api/history");
      const sessions = await res.json();
      const historyListEl = document.getElementById("historyList");
      historyListEl.innerHTML = "";
      sessions.forEach(session => {
        const el = document.createElement("div");
        el.className = "history-item";
        if (session.id === currentSessionId) el.classList.add("active");
        const date = new Date(session.updated_at).toLocaleDateString();
        el.innerHTML = `
          <div style="font-weight:600;margin-bottom:2px;">${escapeHtml(session.title.substring(0, 20))}</div>
          <div style="font-size:11px;opacity:0.7;">${date}</div>
          <button class="history-item-delete" onclick="deleteChat(event, ${session.id})">✕</button>
        `;
        el.onclick = () => loadSession(session.id);
        historyListEl.appendChild(el);
      });
    } catch (e) {
      console.error("Failed to load history:", e);
    }
  }


  async function loadSession(sessionId) {
    try {
      const res = await fetch(`/api/session/${sessionId}`);
      const data = await res.json();
      currentSessionId = sessionId;
      chatEl.innerHTML = "";
      msgCount = 0;
      msgCountEl.textContent = "0 messages";
      data.messages.forEach(msg => {
        addMessage(msg.sender, msg.content, msg.sender === "Nicky" ? "bot" : "user");
      });
      loadHistory();
    } catch (e) {
      console.error("Failed to load session:", e);
      addSystem("Failed to load session.");
    }
  }

  async function newChat() {
    chatEl.innerHTML = '';
    msgCount = 0;
    msgCountEl.textContent = "0 messages";
    questionEl.value = "";
    try {
      const res = await fetch("/api/new-session", { method: "POST" });
      const data = await res.json();
      currentSessionId = data.session_id || null;
    } catch (e) {
      console.error("Failed to create new session:", e);
      currentSessionId = null;
    }
    addMessage("Nicky", "Hello! Starting a new conversation. What would you like to know about NSSF?", "bot");
    loadHistory();
  }

  async function deleteChat(event, sessionId) {
    event.stopPropagation();
    if (confirm("Delete this chat?")) {
      try {
        await fetch(`/api/session/${sessionId}`, { method: "DELETE" });
        loadHistory();
        if (currentSessionId === sessionId) newChat();
      } catch (e) {
        console.error("Failed to delete chat:", e);
        addSystem("Failed to delete chat.");
      }
    }
  }

  // ── Status polling ───────────────────────────────────────────────────────────
  async function checkStatus() {
    try {
      const res  = await fetch("/api/status");
      const data = await res.json();
      ready = data.ready;
      statusEl.textContent = data.error
        ? `❌ ${data.status}: ${data.error}`
        : (data.ready ? "● Ready" : `⏳ ${data.status}`);
      sendBtn.disabled = !ready;
      micBtn.disabled  = !ready || !SpeechRecognition;
      if (!ready) setTimeout(checkStatus, 1200);
      else {
        loadHistory();
        newChat();
        setNickyState("idle");
      }
    } catch {
      statusEl.textContent = "Cannot reach local server.";
    }
  }

  // ── Ask question ─────────────────────────────────────────────────────────────
  async function askQuestion(question) {
    const q = question.trim();
    if (!q || !ready) return;

    addMessage("You", q, "user");
    questionEl.value = "";
    sendBtn.disabled = true;
    micBtn.disabled  = true;
    setNickyState("thinking");
    statusEl.textContent = "⏳ Thinking...";
    showTyping();

    try {
      const res  = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: currentSessionId }),
      });
      const data = await res.json();
      if (!data.ok) {
        addSystem(data.error || "Something went wrong.");
        setNickyState("idle");
      } else {
        if (data.session_id) currentSessionId = data.session_id;
        addMessage("Nicky", data.answer, "bot");
        speak(data.answer);
        if (!voiceReplies) setNickyState("idle");
      }
    } catch {
      addSystem("Could not reach the assistant. Is the server running?");
      setNickyState("idle");
    } finally {
      statusEl.textContent = ready ? "● Ready" : "Starting...";
      sendBtn.disabled = false;
      micBtn.disabled  = !SpeechRecognition;
      questionEl.focus();
      loadHistory();
    }
  }

  // ── Send button & Enter key ───────────────────────────────────────────────────
  sendBtn.addEventListener("click", () => askQuestion(questionEl.value));
  questionEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion(questionEl.value);
    }
  });

  // ── Microphone (browser Web Speech API) ──────────────────────────────────────
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      micBtn.textContent = "⏹ Stop";
      micBtn.classList.add("listening");
      micWrap.classList.add("listening");
      setNickyState("listening");
      statusEl.textContent = "🎙 Listening...";
    };

    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      questionEl.value = text;
      askQuestion(text);
    };

    recognition.onerror = () => {
      addSystem("Voice input failed — try typing your question instead.");
      setNickyState("idle");
    };

    recognition.onend = () => {
      micBtn.textContent = "🎙 Speak";
      micBtn.classList.remove("listening");
      micWrap.classList.remove("listening");
      if (ready) statusEl.textContent = "● Ready";
    };

    micBtn.addEventListener("click", () => {
      if (micBtn.classList.contains("listening")) {
        recognition.stop();
      } else {
        recognition.start();
      }
    });

  } else {
    micBtn.disabled = true;
    micBtn.textContent = "No mic";
    addSystem("Voice input works best in Chrome or Edge. Try those browsers for mic support.");
  }

  // ── Boot ─────────────────────────────────────────────────────────────────────
  sendBtn.disabled = true;
  micBtn.disabled  = true;
  checkStatus();
</script>
</body>
</html>
"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class WebUIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(HTML)
        elif self.path == "/api/status":
            self._send_json({
                "ready":  STATE.ready,
                "status": STATE.status,
                "error":  STATE.error,
            })
        else:
            if self.path == "/api/history":
                  sessions = get_all_sessions()
                  self._send_json(sessions)
                  return
            if self.path.startswith("/api/session/"):
                try:
                    session_id = int(self.path.split("/")[-1])
                    messages = get_session_messages(session_id)
                    self._send_json({"messages": messages})
                    return
                except:
                    self.send_error(400) 
                    return

            self.send_error(404)
    def do_DELETE(self):
        if self.path.startswith("/api/session/"):
            try:
                session_id = int(self.path.split("/")[-1])
                delete_session(session_id)
                self._send_json({"ok": True})
                return
            except:
                  self.send_error(400)
                  return
        self.send_error(404)


    def do_POST(self):
        if self.path == "/api/new-session":
            self._send_json(STATE.new_session())
            return

        if self.path != "/api/ask":
            self.send_error(404)
            return
        try:
            length   = int(self.headers.get("Content-Length", "0"))
            raw      = self.rfile.read(length).decode("utf-8")
            payload  = json.loads(raw or "{}")
            question = payload.get("question", "").strip()
            session_id = payload.get("session_id")
            if session_id is not None:
                session_id = int(session_id)
            if not question:
                self._send_json({"ok": False, "answer": "",
                                 "error": "Question is empty."})
                return
            self._send_json(STATE.ask(question, session_id=session_id))
        except Exception as exc:
            self._send_json({"ok": False, "answer": "",
                             "error": str(exc)}, status=500)

    def log_message(self, fmt, *args):
        print("[WebUI]", fmt % args)

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


# ── Entry point ───────────────────────────────────────────────────────────────

def make_server(host, preferred_port):
    for port in range(preferred_port, preferred_port + 20):
        try:
            return ThreadingHTTPServer((host, port), WebUIHandler)
        except OSError:
            continue
    raise OSError(f"No free port found from {preferred_port} to {preferred_port + 19}.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the NSSF Uganda browser-based assistant.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8002, type=int)
    args = parser.parse_args()

    # Load data in background
    threading.Thread(target=STATE.load, daemon=True).start()

    server = make_server(args.host, args.port)
    host, port = server.server_address
    url = f"http://{host}:{port}"
    print(f"\n[WebUI] Server running at {url}")
    print("[WebUI] Opening browser automatically...")
    print("[WebUI] Press Ctrl+C to stop.\n")

    # Auto-open browser after short delay
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebUI] Stopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

