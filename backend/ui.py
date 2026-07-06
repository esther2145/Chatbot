import tkinter as tk
import threading
import queue
import math
import os

from scrapper import scrape_all_pages
from assistant import NSSFAssistant
from voice import build_tts_engine, listen
import speech_recognition as sr

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ── Palette ────────────────────────────────────────────────────────────────────
SKY    = "#1A0533"
PURPLE = "#6C2BD9"
PINK   = "#FF4DAA"
GOLD   = "#FFD166"
GREEN  = "#06D6A0"
RED    = "#EF476F"
CARD   = "#2A1050"
CARD2  = "#351466"
BORDER = "#5A2EA0"
TEXT   = "#F8F0FF"
MUTED  = "#C4A8FF"
WHITE  = "#FFFFFF"

BUBBLE_MESSAGES = {
    "idle":      ["Hello! Ask me anything!", "I am here to help!",
                  "What would you like to know?", "Ask me about NSSF!"],
    "listening": ["I am listening...", "Go ahead, speak!", "Tell me your question!"],
    "thinking":  ["Hmm, let me think...", "Checking NSSF knowledge...", "One moment please!"],
    "speaking":  ["Here is what I found!", "Hope that helps!", "Great question!"],
}


class NSSFApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NSSF Uganda Assistant")
        self.geometry("860x700")
        self.minsize(760, 620)
        self.configure(bg=SKY)

        self.msg_queue        = queue.Queue()
        self.tts_engine       = build_tts_engine()
        self.recognizer       = sr.Recognizer()
        self.assistant        = None
        self.is_listening     = False
        self.wave_angle       = 0.0
        self.wave_mode        = "idle"
        self.arm_angle        = 0.0
        self.arm_dir          = 1
        self.arm_animating    = False
        self._placeholder_active = True
        self.voice_output_var = tk.BooleanVar(value=True)

        self._build_ui()

        # Draw stickman AFTER window is visible so canvas has real dimensions
        self.update_idletasks()
        self._draw_stickman()

        self._start_init_thread()
        self.after(50,   self._poll_queue)
        self.after(50,   self._animate_wave)
        self.after(80,   self._animate_stickman)
        self.after(3500, self._cycle_bubble)

    # ──────────────────────────────────────────────────────────────────────────
    #  UI BUILD  —  bottom items packed FIRST so they always stay visible
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):

        # ── TOP BAR ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=CARD)
        topbar.pack(fill="x", side="top")

        inner_top = tk.Frame(topbar, bg=CARD, pady=12, padx=20)
        inner_top.pack(fill="x")

        tk.Label(inner_top, text="  NSSF  ", bg=PURPLE, fg=WHITE,
                 font=("Arial", 13, "bold"), padx=4, pady=5
                 ).pack(side="left", padx=(0, 14))

        title_frame = tk.Frame(inner_top, bg=CARD)
        title_frame.pack(side="left")
        tk.Label(title_frame, text="Uganda Assistant",
                 bg=CARD, fg=GOLD,
                 font=("Arial", 17, "bold")).pack(anchor="w")
        self.sub_label = tk.Label(title_frame, text="● Connecting...",
                                  bg=CARD, fg=MUTED, font=("Arial", 10))
        self.sub_label.pack(anchor="w")

        for colour in [RED, GOLD, GREEN]:
            tk.Label(inner_top, text="●", bg=CARD, fg=colour,
                     font=("Arial", 16)).pack(side="right", padx=2)

        # ── TICKER — packed to bottom FIRST ──────────────────────────────────
        ticker_frame = tk.Frame(self, bg=CARD2, pady=5)
        ticker_frame.pack(fill="x", side="bottom")
        self.ticker_lbl = tk.Label(
            ticker_frame,
            text=("★  NSSF Uganda — Securing Your Future  |  "
                  "Helpline: 0800 100 066 (toll free)  |  "
                  "Mon–Fri 8am–5pm  |  Visit nssf.or.ug  ★     ") * 2,
            bg=CARD2, fg=GOLD, font=("Arial", 10))
        self.ticker_lbl.pack()
        self._animate_ticker()

        # ── INPUT AREA — packed to bottom SECOND ─────────────────────────────
        input_outer = tk.Frame(self, bg=CARD, pady=12)
        input_outer.pack(fill="x", side="bottom")

        input_inner = tk.Frame(input_outer, bg=CARD, padx=14)
        input_inner.pack(fill="x")

        # Mic row
        mic_row = tk.Frame(input_inner, bg=CARD)
        mic_row.pack(fill="x", pady=(0, 8))

        self.mic_btn = tk.Button(
            mic_row, text="🎙  Speak",
            font=("Arial", 11, "bold"),
            bg=RED, fg=WHITE, relief="flat",
            padx=18, pady=8, cursor="hand2",
            command=self._toggle_mic,
            activebackground="#C0392B", activeforeground=WHITE)
        self.mic_btn.pack(side="left", padx=(0, 12))

        self.voice_lbl = tk.Label(mic_row,
                                  text="Press the mic button or type below",
                                  bg=CARD, fg=MUTED, font=("Arial", 10))
        self.voice_lbl.pack(side="left")

        self.voice_output_btn = tk.Button(
            mic_row,
            text="Voice replies: ON",
            command=self._toggle_voice_output,
            bg=GREEN,
            fg="#0D2B22",
            activebackground=CARD,
            activeforeground=WHITE,
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Arial", 10, "bold"),
        )
        self.voice_output_btn.pack(side="right")

        # Entry row
        entry_row = tk.Frame(input_inner, bg=CARD)
        entry_row.pack(fill="x")

        entry_bg = tk.Frame(entry_row, bg=BORDER, padx=2, pady=2)
        entry_bg.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.txt_entry = tk.Entry(
            entry_bg, bg=SKY, fg=MUTED,
            font=("Arial", 13), relief="flat",
            insertbackground=GOLD, bd=0)
        self.txt_entry.pack(fill="x", ipady=9, padx=4)
        self.txt_entry.insert(0, "Type your question here...")
        self.txt_entry.bind("<Return>",   lambda e: self._send_text())
        self.txt_entry.bind("<FocusIn>",  self._entry_focus_in)
        self.txt_entry.bind("<FocusOut>", self._entry_focus_out)

        tk.Button(
            entry_row, text="Send  ➤",
            font=("Arial", 12, "bold"),
            bg=GREEN, fg="#0D2B22", relief="flat",
            padx=20, pady=10, cursor="hand2",
            command=self._send_text,
            activebackground="#04B589", activeforeground="#0D2B22"
        ).pack(side="right")

        # ── MAIN CONTENT — packed last, fills remaining space ─────────────────
        content = tk.Frame(self, bg=SKY)
        content.pack(fill="both", expand=True, side="top")

        # Left: stickman
        left_panel = tk.Frame(content, bg=CARD, width=180)
        left_panel.pack(side="left", fill="y")
        left_panel.pack_propagate(False)

        self.stick_canvas = tk.Canvas(left_panel, bg=CARD,
                                      width=180, highlightthickness=0)
        self.stick_canvas.pack(fill="both", expand=True)

        # Right: chat + waveform
        right_panel = tk.Frame(content, bg=SKY)
        right_panel.pack(side="left", fill="both", expand=True)

        # Waveform — packed to bottom of right panel first
        wave_frame = tk.Frame(right_panel, bg=SKY, height=44)
        wave_frame.pack(fill="x", side="bottom", padx=14, pady=(0, 4))
        wave_frame.pack_propagate(False)
        self.wave_canvas = tk.Canvas(wave_frame, bg=SKY, highlightthickness=0)
        self.wave_canvas.pack(fill="both", expand=True)

        # Chat box — fills remaining space in right panel
        chat_frame = tk.Frame(right_panel, bg=SKY)
        chat_frame.pack(fill="both", expand=True, padx=14, pady=(12, 6))

        self.chat_box = tk.Text(
            chat_frame, bg=CARD2, fg=TEXT,
            font=("Arial", 12), wrap=tk.WORD,
            state="disabled", relief="flat",
            padx=14, pady=12, cursor="arrow",
            spacing1=4, spacing3=4)

        scrollbar = tk.Scrollbar(chat_frame, command=self.chat_box.yview,
                                 bg=CARD2, troughcolor=CARD2,
                                 relief="flat", bd=0)
        self.chat_box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_box.pack(side="left", fill="both", expand=True)

        self.chat_box.tag_configure("bot_name",
                                    foreground=GREEN,
                                    font=("Arial", 11, "bold"))
        self.chat_box.tag_configure("bot_text",
                                    foreground=TEXT,
                                    font=("Arial", 12))
        self.chat_box.tag_configure("user_name",
                                    foreground=PINK,
                                    font=("Arial", 11, "bold"))
        self.chat_box.tag_configure("user_text",
                                    foreground="#FFD0EE",
                                    font=("Arial", 12))
        self.chat_box.tag_configure("sys_text",
                                    foreground=MUTED,
                                    font=("Arial", 10, "italic"))

        self._add_msg("Nicky",
                      "Hello! I am your NSSF Uganda assistant. "
                      "Loading the latest NSSF information — please wait a moment.",
                      "bot")

    # ──────────────────────────────────────────────────────────────────────────
    #  PLACEHOLDER
    # ──────────────────────────────────────────────────────────────────────────

    def _entry_focus_in(self, event):
        if self._placeholder_active:
            self.txt_entry.delete(0, "end")
            self.txt_entry.config(fg=TEXT)
            self._placeholder_active = False

    def _entry_focus_out(self, event):
        if self.txt_entry.get().strip() == "":
            self.txt_entry.insert(0, "Type your question here...")
            self.txt_entry.config(fg=MUTED)
            self._placeholder_active = True

    # ──────────────────────────────────────────────────────────────────────────
    #  STICKMAN
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_stickman(self):
        c = self.stick_canvas
        c.delete("all")
        cx  = 90
        top = 30

        # Speech bubble
        bx, by = cx - 54, top
        c.create_rectangle(bx, by, bx + 108, by + 44,
                           fill=GOLD, outline="")
        c.create_polygon(cx - 7, by + 44, cx + 7, by + 44, cx, by + 58,
                         fill=GOLD, outline="")
        self.bubble_txt = c.create_text(
            cx, by + 22, text="Hello!\nAsk me anything!",
            font=("Arial", 8, "bold"), fill=CARD,
            width=100, justify="center")

        # Head
        hy = top + 80
        c.create_oval(cx - 24, hy, cx + 24, hy + 48,
                      fill=GOLD, outline="#F4A817", width=2)
        c.create_oval(cx - 14, hy + 12, cx - 6,  hy + 20, fill=CARD)
        c.create_oval(cx + 6,  hy + 12, cx + 14, hy + 20, fill=CARD)
        self.mouth_id = c.create_arc(
            cx - 11, hy + 24, cx + 11, hy + 38,
            start=200, extent=140,
            style="arc", outline=CARD, width=2.5)
        c.create_oval(cx - 25, hy + 22, cx - 15, hy + 30,
                      fill=PINK, outline="", stipple="gray50")
        c.create_oval(cx + 15, hy + 22, cx + 25, hy + 30,
                      fill=PINK, outline="", stipple="gray50")

        # Body
        sy = hy + 50
        c.create_rectangle(cx - 18, sy, cx + 18, sy + 56,
                           fill=PURPLE, outline="")
        c.create_text(cx, sy + 28, text="NSSF",
                      font=("Arial", 9, "bold"), fill=GOLD)

        # Arms
        self.arm_l = c.create_line(cx - 18, sy + 10, cx - 46, sy + 36,
                                   fill=GOLD, width=5, capstyle="round")
        self.arm_r = c.create_line(cx + 18, sy + 10, cx + 46, sy + 36,
                                   fill=GOLD, width=5, capstyle="round")
        c.create_oval(cx - 50, sy + 32, cx - 38, sy + 44, fill=GOLD, outline="")
        c.create_oval(cx + 38, sy + 32, cx + 50, sy + 44, fill=GOLD, outline="")

        # Legs
        ly = sy + 56
        c.create_line(cx, ly, cx - 22, ly + 60,
                      fill=GOLD, width=5, capstyle="round")
        c.create_line(cx, ly, cx + 22, ly + 60,
                      fill=GOLD, width=5, capstyle="round")
        c.create_oval(cx - 32, ly + 54, cx - 10, ly + 68, fill=PURPLE, outline="")
        c.create_oval(cx + 10, ly + 54, cx + 32, ly + 68, fill=PURPLE, outline="")

        # Save arm anchors for animation
        self._arm_ox  = cx - 18;  self._arm_oy  = sy + 10
        self._arm_ox2 = cx + 18;  self._arm_oy2 = sy + 10

    # ──────────────────────────────────────────────────────────────────────────
    #  ANIMATIONS
    # ──────────────────────────────────────────────────────────────────────────

    def _animate_stickman(self):
        if self.arm_animating:
            self.arm_angle += self.arm_dir * 4
            if self.arm_angle > 28 or self.arm_angle < -28:
                self.arm_dir *= -1
            rad = math.radians(self.arm_angle)
            ex  = self._arm_ox  - 28 * math.cos(rad + math.pi / 4)
            ey  = self._arm_oy  + 26 * math.sin(rad + math.pi / 4)
            self.stick_canvas.coords(self.arm_l,
                                     self._arm_ox, self._arm_oy, ex, ey)
            ex2 = self._arm_ox2 + 28 * math.cos(rad + math.pi / 4)
            ey2 = self._arm_oy2 - 26 * math.sin(rad + math.pi / 4)
            self.stick_canvas.coords(self.arm_r,
                                     self._arm_ox2, self._arm_oy2, ex2, ey2)
        self.after(65, self._animate_stickman)

    def _animate_wave(self):
        c = self.wave_canvas
        c.delete("all")
        w = c.winfo_width() or 500
        n, bw, gap = 32, 4, 3
        start_x = max(4, (w - n * (bw + gap)) // 2)
        self.wave_angle += 0.14

        col = {"idle": BORDER, "listening": GREEN,
               "speaking": GOLD, "thinking": PURPLE}.get(self.wave_mode, BORDER)

        for i in range(n):
            x = start_x + i * (bw + gap)
            if self.wave_mode == "listening":
                h = 5 + abs(math.sin(self.wave_angle * 2.2 + i * 0.5)) * 26
            elif self.wave_mode == "speaking":
                h = 4 + abs(math.sin(self.wave_angle + i * 0.45)) * 20
            elif self.wave_mode == "thinking":
                h = 3 + abs(math.sin(self.wave_angle * 0.8 + i * 0.6)) * 14
            else:
                h = 3 + abs(math.sin(self.wave_angle * 0.4 + i * 0.3)) * 4
            cy = 22
            c.create_rectangle(x, cy - h / 2, x + bw, cy + h / 2,
                                fill=col, outline="")
        self.after(50, self._animate_wave)

    def _animate_ticker(self):
        txt = self.ticker_lbl.cget("text")
        self.ticker_lbl.config(text=txt[1:] + txt[0])
        self.after(85, self._animate_ticker)

    def _set_bubble(self, state):
        import random
        msgs = BUBBLE_MESSAGES.get(state, BUBBLE_MESSAGES["idle"])
        self.stick_canvas.itemconfig(self.bubble_txt, text=random.choice(msgs))

    def _cycle_bubble(self):
        if self.wave_mode == "idle":
            self._set_bubble("idle")
        self.after(3800, self._cycle_bubble)

    # ──────────────────────────────────────────────────────────────────────────
    #  CHAT HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _add_msg(self, sender, text, kind):
        self.chat_box.configure(state="normal")
        icon     = "🟢" if kind == "bot" else "🩷"
        name_tag = "bot_name"  if kind == "bot" else "user_name"
        text_tag = "bot_text"  if kind == "bot" else "user_text"
        self.chat_box.insert("end", f"\n{icon} {sender}\n", name_tag)
        self.chat_box.insert("end", f"{text}\n",             text_tag)
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def _add_sys(self, txt):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"  ⏳ {txt}\n", "sys_text")
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def _set_status(self, txt, colour=MUTED):
        self.sub_label.config(text=f"● {txt}", fg=colour)

    def _toggle_voice_output(self):
        enabled = not self.voice_output_var.get()
        self.voice_output_var.set(enabled)
        if enabled:
            self.voice_output_btn.config(
                text="Voice replies: ON",
                bg=GREEN,
                fg="#0D2B22",
                activebackground="#04B589",
            )
            self._add_sys("Voice replies turned on.")
        else:
            self.voice_output_btn.config(
                text="Text replies only",
                bg=PURPLE,
                fg=WHITE,
                activebackground=BORDER,
            )
            self._add_sys("Voice replies turned off. Answers will appear as text only.")

    # ──────────────────────────────────────────────────────────────────────────
    #  INIT THREAD
    # ──────────────────────────────────────────────────────────────────────────

    def _start_init_thread(self):
        threading.Thread(target=self._init_worker, daemon=True).start()

    def _init_worker(self):
        self.msg_queue.put(("sys", "Connecting to NSSF Uganda website..."))
        context = scrape_all_pages()
        if context.strip():
            self.assistant = NSSFAssistant(GROQ_API_KEY, context)
            self.msg_queue.put(("status", ("Connected to nssf.or.ug ✓", GREEN)))
            self.msg_queue.put(("msg", ("Nicky",
                "I have loaded the latest NSSF information and I am ready to help! "
                "Ask me anything about membership, contributions, benefits, "
                "or employer services.", "bot")))
            self.msg_queue.put(("bubble", "idle"))
        else:
            self.msg_queue.put(("status", ("Website offline — retrying...", GOLD)))
            self.msg_queue.put(("msg", ("Nicky",
                "The NSSF website is currently unavailable. "
                "I will keep retrying. If cached data exists I can still help!", "bot")))

    # ──────────────────────────────────────────────────────────────────────────
    #  QUEUE POLL
    # ──────────────────────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                kind, data = self.msg_queue.get_nowait()
                if kind == "msg":
                    self._add_msg(*data)
                elif kind == "sys":
                    self._add_sys(data)
                elif kind == "status":
                    self._set_status(*data)
                elif kind == "bubble":
                    self._set_bubble(data)
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    # ──────────────────────────────────────────────────────────────────────────
    #  VOICE
    # ──────────────────────────────────────────────────────────────────────────

    def _toggle_mic(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.mic_btn.config(bg=PURPLE, text="⏹  Stop")
        self.voice_lbl.config(text="Listening — speak now...", fg=GREEN)
        self.wave_mode = "listening"
        self.arm_animating = True
        self._set_bubble("listening")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        text = listen(self.recognizer)
        self.is_listening = False
        self.wave_mode = "idle"
        self.after(0, lambda: self.mic_btn.config(bg=RED, text="🎙  Speak"))
        self.after(0, lambda: self.voice_lbl.config(
            text="Press the mic button or type below", fg=MUTED))
        if text:
            self.after(0, lambda: self._process_q(text))
        else:
            self.arm_animating = False
            self._set_bubble("idle")

    # ──────────────────────────────────────────────────────────────────────────
    #  TEXT SEND
    # ──────────────────────────────────────────────────────────────────────────

    def _send_text(self):
        txt = self.txt_entry.get().strip()
        if not txt or self._placeholder_active:
            return
        self.txt_entry.delete(0, "end")
        self._placeholder_active = True
        self.txt_entry.insert(0, "Type your question here...")
        self.txt_entry.config(fg=MUTED)
        self._process_q(txt)

    # ──────────────────────────────────────────────────────────────────────────
    #  PROCESS QUESTION
    # ──────────────────────────────────────────────────────────────────────────

    def _process_q(self, question):
        if not self.assistant:
            self._add_msg("You", question, "user")
            self._add_sys("Still loading NSSF data — please wait a moment.")
            return

        self._add_msg("You", question, "user")
        self._add_sys("Nicky is thinking...")
        self.wave_mode = "thinking"
        self.arm_animating = True
        self._set_bubble("thinking")
        self.voice_lbl.config(text="Thinking...", fg=GOLD)
        self._set_status("Thinking...", GOLD)
        speak_reply = self.voice_output_var.get()

        def worker():
            answer = self.assistant.ask(question)
            self.msg_queue.put(("msg", ("Nicky", answer, "bot")))
            if speak_reply:
                self.msg_queue.put(("bubble", "speaking"))
                self.wave_mode = "speaking"
                self.after(0, lambda: self.voice_lbl.config(
                    text="Speaking answer...", fg=GREEN))
                self.after(0, lambda: self._set_status("Speaking...", GREEN))
                self.tts_engine.say(answer)
                self.tts_engine.runAndWait()
            self.wave_mode = "idle"
            self.arm_animating = False
            self.msg_queue.put(("bubble", "idle"))
            self.after(0, lambda: self.voice_lbl.config(
                text="Press the mic button or type below", fg=MUTED))
            self.after(0, lambda: self._set_status("Ready", GREEN))

        threading.Thread(target=worker, daemon=True).start()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = NSSFApp()
    app.mainloop()
