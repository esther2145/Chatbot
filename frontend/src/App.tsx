import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Check,
  Copy,
  Eraser,
  Headphones,
  Menu,
  MessageSquareText,
  Mic,
  Plus,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { speakText, startListening } from "./utils/speech";
import {
  LiveVoice,
  type CallTranscriptMessage,
} from "./components/LiveVoice";
import "./App.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/$/, "");

type Message = {
  sender: string;
  text: string;
  type: "bot" | "user";
  citations?: string[];
};

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  sessionId: string | null;
};

const popularQuestions = [
  "What is NSSF?",
  "How do I register for NSSF?",
  "How can I check my balance?",
  "How do I submit a claim?",
];

const GREETING: Message = {
  sender: "Nicky",
  text: "Hello! I’m Nicky, your NSSF Uganda digital assistant. I can help with membership, contributions, benefits, claims, and NSSF services.",
  type: "bot",
};

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "New conversation",
    messages: [GREETING],
    sessionId: crypto.randomUUID(),
  };
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const saved = localStorage.getItem("nssf_conversations");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length) return parsed;
      } catch {
        // Ignore invalid local data and start cleanly.
      }
    }
    return [newConversation()];
  });
  const [activeId, setActiveId] = useState(
    () => localStorage.getItem("nssf_active_id") || ""
  );
  const [question, setQuestion] = useState("");
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [liveVoiceOpen, setLiveVoiceOpen] = useState(false);
  const [liveVoiceInstanceId, setLiveVoiceInstanceId] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!conversations.find((conversation) => conversation.id === activeId)) {
      setActiveId(conversations[0].id);
    }
  }, [conversations, activeId]);

  useEffect(() => {
    localStorage.setItem("nssf_conversations", JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    localStorage.setItem("nssf_active_id", activeId);
  }, [activeId]);

  const activeConversation =
    conversations.find((conversation) => conversation.id === activeId) ||
    conversations[0];
  const messages = activeConversation.messages;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();
        setOnline(data.ready === true);
      } catch {
        setOnline(false);
      }
    }
    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => clearInterval(interval);
  }, []);

  function updateActive(updater: (conversation: Conversation) => Conversation) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === activeId ? updater(conversation) : conversation
      )
    );
  }

  async function askQuestion(text?: string) {
    const cleanQuestion = (text ?? question).trim();
    if (!cleanQuestion || loading) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    window.speechSynthesis?.cancel();

    updateActive((conversation) => ({
      ...conversation,
      title:
        conversation.title === "New conversation"
          ? cleanQuestion.slice(0, 42)
          : conversation.title,
      messages: [
        ...conversation.messages,
        { sender: "You", text: cleanQuestion, type: "user" },
      ],
    }));

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: cleanQuestion,
          session_id: activeConversation.sessionId,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Backend request failed with status ${response.status}`);
      }

      const data = await response.json();
      if (controllerRef.current !== controller) return;
      const answer = data.ok
        ? data.answer
        : data.error || "Sorry, I could not answer that question.";

      updateActive((conversation) => ({
        ...conversation,
        sessionId: data.session_id ?? conversation.sessionId,
        messages: [
          ...conversation.messages,
          {
            sender: "Nicky",
            text: answer,
            type: "bot",
            citations: data.citations || [],
          },
        ],
      }));
      speakText(answer, voiceReplies);
    } catch (error: any) {
      if (error.name === "AbortError" || controllerRef.current !== controller) return;
      const errorMessage =
        "I couldn’t complete that request. Please check the backend and try again.";
      updateActive((conversation) => ({
        ...conversation,
        messages: [
          ...conversation.messages,
          { sender: "Nicky", text: errorMessage, type: "bot" },
        ],
      }));
    } finally {
      if (controllerRef.current === controller) setLoading(false);
    }
  }

  function stopGenerating() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setLoading(false);
  }

  function startVoiceInput() {
    startListening(
      (spokenQuestion) => {
        setQuestion(spokenQuestion);
        textareaRef.current?.focus();
      },
      () => setListening(true),
      () => setListening(false),
      (message) => {
        setListening(false);
        alert(message);
      }
    );
  }

  function startNewChat() {
    const conversation = newConversation();
    setConversations((previous) => [conversation, ...previous]);
    setActiveId(conversation.id);
    setSidebarOpen(false);
  }

  function deleteConversation(id: string) {
    setConversations((previous) => {
      const remaining = previous.filter((conversation) => conversation.id !== id);
      if (!remaining.length) {
        const fresh = newConversation();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (id === activeId) setActiveId(remaining[0].id);
      return remaining;
    });
  }

  function clearCurrentChat() {
    updateActive((conversation) => ({
      ...conversation,
      title: "New conversation",
      messages: [GREETING],
      sessionId: null,
    }));
  }

  async function copyText(text: string, index: number) {
    await navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    window.setTimeout(() => setCopiedIndex(null), 1600);
  }

  function saveCallTranscript(
    callMessages: CallTranscriptMessage[],
    voiceSessionId: string
  ) {
    if (!callMessages.length) return;
    const firstUserMessage = callMessages.find(
      (message) => message.role === "user" && message.text.trim()
    );
    const transcriptTitle = (
      firstUserMessage?.text ||
      callMessages.find((message) => message.text.trim())?.text ||
      "Voice conversation"
    )
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 42);

    updateActive((conversation) => ({
      ...conversation,
      sessionId: voiceSessionId || conversation.sessionId,
      title:
        conversation.title === "New conversation"
          ? transcriptTitle
          : conversation.title,
      messages: [
        ...conversation.messages,
        ...callMessages.map<Message>((message) => ({
          sender: message.role === "assistant" ? "Nicky" : "You",
          text: message.text,
          type: message.role === "assistant" ? "bot" : "user",
        })),
      ],
    }));
  }

  return (
    <div className="app-shell">
      {liveVoiceOpen && (
        <LiveVoice
          key={liveVoiceInstanceId}
          apiBase={API_BASE}
          conversationSessionId={activeConversation.sessionId}
          onClose={() => setLiveVoiceOpen(false)}
          onCallComplete={saveCallTranscript}
        />
      )}
      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark">
            <img src="/images/nssf.png.png" alt="NSSF Uganda" />
          </div>
          <div className="brand-copy">
            <strong>NSSF Uganda</strong>
            <span>Digital Assistant</span>
          </div>
          <button
            className="icon-button sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <button className="new-chat-button" onClick={startNewChat}>
          <Plus size={18} />
          New conversation
        </button>

        <div className="conversation-section">
          <div className="section-label">Recent conversations</div>
          <div className="conversation-list">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                className={`conversation-item ${
                  conversation.id === activeId ? "active" : ""
                }`}
                onClick={() => {
                  setActiveId(conversation.id);
                  setSidebarOpen(false);
                }}
              >
                <MessageSquareText size={17} />
                <span>{conversation.title}</span>
                <span
                  role="button"
                  tabIndex={0}
                  className="delete-chat"
                  aria-label="Delete conversation"
                  onClick={(event) => {
                    event.stopPropagation();
                    deleteConversation(conversation.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") deleteConversation(conversation.id);
                  }}
                >
                  <Trash2 size={15} />
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="trust-note">
            <ShieldCheck size={18} />
            <span>Answers grounded in indexed NSSF Uganda information.</span>
          </div>
          <div className="assistant-profile">
            <div className="nicky-avatar">N</div>
            <div>
              <strong>Nicky</strong>
              <span><i className="status-dot" /> Available</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div className="header-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={21} />
            </button>
            <div>
              <div className="eyebrow">NSSF MEMBER SUPPORT</div>
              <h1>How can I help you today?</h1>
            </div>
          </div>
          <div className="header-actions">
            <div className={`service-status ${online ? "is-online" : ""}`}>
              <span />
              {online ? "Service online" : "Connecting"}
            </div>
          </div>
        </header>

        <section className="chat-stage">
          <div className="messages" aria-live="polite">
            {messages.length === 1 && (
              <div className="welcome-panel">
                <div className="welcome-icon"><Sparkles size={22} /></div>
                <h2>Your NSSF questions, clearly answered.</h2>
                <p>
                  Ask about registration, contributions, benefits, claims, or
                  navigating NSSF services.
                </p>
                <div className="suggestion-grid">
                  {popularQuestions.map((item) => (
                    <button key={item} onClick={() => askQuestion(item)}>
                      <span>{item}</span>
                      <ArrowUp size={16} />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <article className={`message-row ${message.type}`} key={index}>
                <div className={`message-avatar ${message.type}`}>
                  {message.type === "bot" ? "N" : "You"}
                </div>
                <div className="message-content">
                  <div className="message-meta">
                    <strong>{message.sender}</strong>
                    {message.type === "bot" && <span>NSSF Digital Assistant</span>}
                  </div>
                  <div className="message-text">{message.text}</div>

                  {message.type === "bot" && message.citations?.length ? (
                    <div className="citation-block">
                      <span>Sources</span>
                      <div>
                        {message.citations.map((url, citationIndex) => (
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            key={`${url}-${citationIndex}`}
                          >
                            {new URL(url).hostname.replace("www.", "")}
                          </a>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {message.type === "bot" && (
                    <button
                      className="copy-button"
                      onClick={() => copyText(message.text, index)}
                    >
                      {copiedIndex === index ? <Check size={15} /> : <Copy size={15} />}
                      {copiedIndex === index ? "Copied" : "Copy"}
                    </button>
                  )}
                </div>
              </article>
            ))}

            {loading && (
              <article className="message-row bot">
                <div className="message-avatar bot">N</div>
                <div className="message-content">
                  <div className="message-meta">
                    <strong>Nicky</strong><span>Reviewing NSSF information</span>
                  </div>
                  <div className="thinking-dots"><i /><i /><i /></div>
                </div>
              </article>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="composer-wrap">
            <div className={`composer ${listening ? "is-listening" : ""}`}>
              <textarea
                ref={textareaRef}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    askQuestion();
                  }
                }}
                placeholder="Message Nicky about NSSF…"
                rows={1}
                aria-label="Your NSSF question"
              />
              <div className="composer-actions">
                <button
                  className="live-voice-launch"
                  onClick={() => {
                    setLiveVoiceInstanceId(crypto.randomUUID());
                    setLiveVoiceOpen(true);
                  }}
                  aria-label="Start live voice call"
                  title="Start a LiveKit voice conversation"
                >
                  <Headphones size={18} />
                  <span>Live voice</span>
                </button>
                <button
                  className={`voice-control ${voiceReplies ? "active" : ""}`}
                  onClick={() => setVoiceReplies((value) => !value)}
                  aria-label={`Turn spoken answers ${voiceReplies ? "off" : "on"}`}
                  title="Toggle spoken answers"
                >
                  {voiceReplies ? <Volume2 size={18} /> : <VolumeX size={18} />}
                  <span>Voice {voiceReplies ? "on" : "off"}</span>
                </button>
                <button
                  className={`composer-icon ${listening ? "listening" : ""}`}
                  onClick={startVoiceInput}
                  aria-label="Speak your question"
                  title="Speak your question"
                >
                  {listening ? <Headphones size={19} /> : <Mic size={19} />}
                </button>
                <button
                  className={`send-button ${loading ? "stop" : ""}`}
                  disabled={!loading && !question.trim()}
                  onClick={() => {
                    if (loading) {
                      stopGenerating();
                    } else {
                      askQuestion();
                    }
                  }}
                  aria-label={loading ? "Stop generating" : "Send question"}
                  title={loading ? "Stop generating" : "Send question"}
                >
                  {loading ? <Square size={17} /> : <ArrowUp size={19} />}
                </button>
              </div>
            </div>
            <div className="composer-footer">
              <span>Nicky can make mistakes. Confirm financial decisions with NSSF.</span>
              <button onClick={clearCurrentChat}><Eraser size={14} /> Clear chat</button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
