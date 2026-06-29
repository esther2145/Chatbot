import { useEffect, useState, useRef } from "react";
import {
  Mic,
  Send,
  Volume2,
  CircleHelp,
  Sparkles,
  ShieldCheck,
  Plus,
  Trash2,
  Copy,
  Eraser,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { speakText, startListening } from "./utils/speech";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

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
  "What are NSSF benefits?",
  "How do I check my balance?",
  "How do I submit a claim?",
];

const GREETING: Message = {
  sender: "Nicky",
  text: "Hello! I am Nicky, your NSSF Uganda assistant. Ask me about membership, benefits, contributions, claims, or NSSF services.",
  type: "bot",
};

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "New Chat",
    messages: [GREETING],
    sessionId: null,
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
        /* ignore corrupt data */
      }
    }
    return [newConversation()];
  });

  const [activeId, setActiveId] = useState<string>(
    () => localStorage.getItem("nssf_active_id") || ""
  );

  const [question, setQuestion] = useState("");
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!conversations.find((c) => c.id === activeId)) {
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
    conversations.find((c) => c.id === activeId) || conversations[0];
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
    const interval = setInterval(checkBackend, 3000);
    return () => clearInterval(interval);
  }, []);

  function speak(answer: string) {
    speakText(answer, voiceReplies);
  }

  function updateActive(updater: (c: Conversation) => Conversation) {
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? updater(c) : c))
    );
  }

  async function askQuestion(text?: string) {
    const cleanQuestion = (text ?? question).trim();
    if (!cleanQuestion) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    window.speechSynthesis?.cancel();

    updateActive((c) => ({
      ...c,
      title: c.title === "New Chat" ? cleanQuestion.slice(0, 40) : c.title,
      messages: [
        ...c.messages,
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

      const data = await response.json();
      if (controllerRef.current !== controller) return;

      const answer = data.ok
        ? data.answer
        : data.error || "Sorry, I could not answer that question.";

      updateActive((c) => ({
        ...c,
        sessionId: data.session_id ?? c.sessionId,
        messages: [
          ...c.messages,
          {
            sender: "Nicky",
            text: answer,
            type: "bot",
            citations: data.citations || [],
          },
        ],
      }));

      speak(answer);
    } catch (err: any) {
      if (err.name === "AbortError") return;
      if (controllerRef.current !== controller) return;
      const errorMessage =
        "I could not connect to the chatbot backend. Make sure the backend is running.";
      updateActive((c) => ({
        ...c,
        messages: [
          ...c.messages,
          { sender: "Nicky", text: errorMessage, type: "bot" },
        ],
      }));
      speak(errorMessage);
    } finally {
      if (controllerRef.current === controller) setLoading(false);
    }
  }

  function startVoiceInput() {
    startListening(
      (spokenQuestion: string) => {
        // Fill the input box with spoken text; user reviews then sends.
        setQuestion(spokenQuestion);
      },
      () => setListening(true),
      () => setListening(false),
      (errorMessage: string) => {
        setListening(false);
        alert(errorMessage);
      }
    );
  }

  function startNewChat() {
    const conv = newConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }

  function deleteConversation(id: string) {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id);
      if (filtered.length === 0) {
        const fresh = newConversation();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (id === activeId) setActiveId(filtered[0].id);
      return filtered;
    });
  }

  function clearCurrentChat() {
    updateActive((c) => ({ ...c, messages: [GREETING], sessionId: null }));
  }

  function copyText(text: string) {
    navigator.clipboard.writeText(text);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <img className="logo" src="/images/nssf.png.png" alt="NSSF Uganda" />

        <div className="sidebar-content">
          <h1>NSSF Assistant</h1>

          <button
            onClick={startNewChat}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.12)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "10px",
              marginTop: "10px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.3)",
              background: "transparent",
              color: "white",
              cursor: "pointer",
              transition: "background 0.15s ease",
            }}
          >
            <Plus size={18} /> New Chat
          </button>

          <div style={{ marginTop: "12px", maxHeight: "240px", overflowY: "auto" }}>
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => setActiveId(c.id)}
                onMouseEnter={(e) => {
                  if (c.id !== activeId)
                    e.currentTarget.style.background = "rgba(255,255,255,0.1)";
                }}
                onMouseLeave={(e) => {
                  if (c.id !== activeId)
                    e.currentTarget.style.background = "transparent";
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "6px",
                  padding: "8px 10px",
                  marginBottom: "4px",
                  borderRadius: "8px",
                  cursor: "pointer",
                  transition: "background 0.15s ease",
                  background:
                    c.id === activeId ? "rgba(255,255,255,0.15)" : "transparent",
                }}
              >
                <span
                  style={{
                    color: "white",
                    fontSize: "0.85rem",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {c.title}
                </span>
                <Trash2
                  size={15}
                  color="rgba(255,255,255,0.7)"
                  style={{ cursor: "pointer", transition: "color 0.15s ease" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "#ff6b6b")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "rgba(255,255,255,0.7)")
                  }
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="assistant-card">
          <div className="avatar">N</div>
          <div>
            <strong>Nicky</strong>
            <span>Online Assistant</span>
          </div>
        </div>

        <div className="sidebar-footer">
          <ShieldCheck size={18} />
          <span>Answers based on NSSF Uganda website information.</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="top">
          <div>
            <h2>How can I help you today?</h2>
            <p>Ask a question by typing or using your microphone.</p>
          </div>

          <button
            className="voice-toggle"
            onClick={() => setVoiceReplies((previous) => !previous)}
          >
            <Volume2 size={20} />
            Voice replies: {voiceReplies ? "ON" : "OFF"}
          </button>
        </header>

        <section className="popular">
          <h3>
            <Sparkles size={22} />
            Popular questions
          </h3>

          <div className="question-buttons">
            {popularQuestions.map((item) => (
              <button
                key={item}
                onClick={() => askQuestion(item)}
                className="question-chip"
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <section className="chat-card">
          <div className="chat-header">
            <div>
              <CircleHelp size={25} />
              <strong>Chat with Nicky</strong>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button
                onClick={clearCurrentChat}
                title="Clear this chat"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  color: "#555",
                  fontSize: "0.8rem",
                }}
              >
                <Eraser size={16} /> Clear
              </button>
              <span className={online ? "online" : "offline"}>
                {online ? "Online" : "Connecting..."}
              </span>
            </div>
          </div>

          <div className="messages">
            {messages.map((message, index) => (
              <div className={`message ${message.type}`} key={index}>
                <strong>{message.sender}</strong>
                <div className="message-text">
                  <ReactMarkdown
                    components={{
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                </div>

                {message.type === "bot" &&
                  message.citations &&
                  message.citations.length > 0 && (
                    <div style={{ marginTop: "8px", fontSize: "0.78rem" }}>
                      <strong>Sources:</strong>
                      <ul style={{ margin: "4px 0 0", paddingLeft: "18px" }}>
                        {message.citations.map((url, i) => (
                          <li key={i}>
                            <a href={url} target="_blank" rel="noopener noreferrer">
                              {url}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                {message.type === "bot" && (
                  <button
                    onClick={() => copyText(message.text)}
                    title="Copy answer"
                    style={{
                      marginTop: "6px",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      color: "#777",
                      fontSize: "0.75rem",
                    }}
                  >
                    <Copy size={14} /> Copy
                  </button>
                )}
              </div>
            ))}

            {loading && (
              <div className="message bot">
                <strong>Nicky</strong>
                <p>Thinking...</p>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  askQuestion();
                }
              }}
              placeholder="Type your NSSF question here..."
            />

            <button
              className={`mic-button ${listening ? "listening" : ""}`}
              onClick={startVoiceInput}
            >
              <Mic size={25} />
            </button>

            <button className="send-button" onClick={() => askQuestion()}>
              <Send size={23} />
              Send
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;