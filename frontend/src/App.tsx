import { useEffect, useState } from "react";
import {
  Mic,
  Send,
  Volume2,
  CircleHelp,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import { speakText, startListening } from "./utils/speech";
import "./App.css";

const API_BASE = "http://127.0.0.1:8001";

type Message = {
  sender: string;
  text: string;
  type: "bot" | "user";
};

const popularQuestions = [
  "How do I register for NSSF?",
  "What are NSSF benefits?",
  "How do I check my balance?",
  "How do I submit a claim?",
];

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "Nicky",
      text: "Hello! I am Nicky, your NSSF Uganda assistant. Ask me about membership, benefits, contributions, claims, or NSSF services.",
      type: "bot",
    },
  ]);

  const [question, setQuestion] = useState("");
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(false);

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

  async function askQuestion(text?: string) {
    const cleanQuestion = (text ?? question).trim();

    if (!cleanQuestion || loading) return;

    setMessages((previous) => [
      ...previous,
      {
        sender: "You",
        text: cleanQuestion,
        type: "user",
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: cleanQuestion,
        }),
      });

      const data = await response.json();

      const answer = data.ok
        ? data.answer
        : data.error || "Sorry, I could not answer that question.";

      setMessages((previous) => [
        ...previous,
        {
          sender: "Nicky",
          text: answer,
          type: "bot",
        },
      ]);

      speak(answer);
    } catch {
      const errorMessage =
        "I could not connect to the chatbot backend. Make sure Python is running.";

      setMessages((previous) => [
        ...previous,
        {
          sender: "Nicky",
          text: errorMessage,
          type: "bot",
        },
      ]);

      speak(errorMessage);
    } finally {
      setLoading(false);
    }
  }

  function startVoiceInput() {
    startListening(
      (spokenQuestion: string) => {
        setQuestion(spokenQuestion);
        askQuestion(spokenQuestion);
      },
      () => setListening(true),
      () => setListening(false),
      (errorMessage: string) => {
        setListening(false);
        alert(errorMessage);
      }
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <img className="logo" src="/images/nssf.png" alt="NSSF Uganda" />

        <div className="sidebar-content">
          <h1>NSSF Assistant</h1>
          <p>
            Get quick answers about NSSF Uganda services, membership, benefits,
            contributions, and claims.
          </p>
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

            <span className={online ? "online" : "offline"}>
              {online ? "Online" : "Connecting..."}
            </span>
          </div>

          <div className="messages">
            {messages.map((message, index) => (
              <div className={`message ${message.type}`} key={index}>
                <strong>{message.sender}</strong>
                <p>{message.text}</p>
              </div>
            ))}

            {loading && (
              <div className="message bot">
                <strong>Nicky</strong>
                <p>Thinking...</p>
              </div>
            )}
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
              disabled={loading}
            >
              <Mic size={25} />
            </button>

            <button
              className="send-button"
              onClick={() => askQuestion()}
              disabled={loading}
            >
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