// Drop this into your React app (e.g. src/hooks/useChat.ts).
// It talks to the FastAPI backend, streams answers token-by-token, lets a new
// question interrupt an in-flight one, and keeps the history of asked questions.

import { useRef, useState, useCallback } from "react";

const API = "http://localhost:8000";

export type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
};

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionId = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const send = useCallback(async (question: string) => {
    // INTERRUPTION: if a previous answer is still streaming, abort it so the
    // new question starts cleanly. The backend won't save the aborted turn,
    // so context stays clean.
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;

    setMessages((m) => [
      ...m,
      { role: "user", content: question },
      { role: "assistant", content: "" },
    ]);
    setIsStreaming(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          session_id: sessionId.current,
        }),
        signal: ac.signal,
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by a blank line.
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.replace(/^data: /, "").trim();
          if (!line) continue;
          const data = JSON.parse(line);

          if (data.token) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1].content += data.token;
              return copy;
            });
          }
          if (data.done) {
            sessionId.current = data.session_id;
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1].citations = data.citations;
              return copy;
            });
          }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1].content =
            "Sorry, something went wrong. Please try again.";
          return copy;
        });
      }
    } finally {
      setIsStreaming(false);
    }
  }, []);

  // The list of questions the user has asked — feed this to your sidebar.
  const askedQuestions = messages
    .filter((m) => m.role === "user")
    .map((m) => m.content);

  return { messages, askedQuestions, isStreaming, send };
}

