import { useEffect, useMemo, useRef, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { Headphones, Mic, PhoneOff, Square, X } from "lucide-react";
import "@livekit/components-styles";

type Credentials = {
  serverUrl: string;
  participantToken: string;
  roomName: string;
  sessionId: string;
};

type LiveVoiceProps = {
  apiBase: string;
  conversationSessionId: string | null;
  onClose: () => void;
  onCallComplete: (messages: CallTranscriptMessage[], sessionId: string) => void;
};

export type CallTranscriptMessage = {
  role: "user" | "assistant";
  text: string;
};

export function LiveVoice({
  apiBase,
  conversationSessionId,
  onClose,
  onCallComplete,
}: LiveVoiceProps) {
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const transcriptRef = useRef<CallTranscriptMessage[]>([]);

  function finishCall() {
    if (transcriptRef.current.length) {
      onCallComplete(transcriptRef.current, credentials?.sessionId || "");
    }
    transcriptRef.current = [];
    setCredentials(null);
  }

  function closeDialog() {
    finishCall();
    onClose();
  }

  async function connect() {
    setConnecting(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/livekit/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: conversationSessionId }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Could not start a LiveKit session.");
      }
      setCredentials(data);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not connect to LiveKit."
      );
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="live-voice-backdrop" role="presentation">
      <section
        className="live-voice-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-voice-title"
      >
        <button
          className="live-voice-close"
          onClick={closeDialog}
          aria-label="Close live voice"
        >
          <X size={20} />
        </button>

        {!credentials ? (
          <>
            <div className="live-voice-orb">
              <Headphones size={31} />
            </div>
            <h2 id="live-voice-title">Talk with Nicky</h2>
            <p>
              Start a secure LiveKit audio session. Your browser will ask for
              microphone permission.
            </p>
            {error && <div className="live-voice-error">{error}</div>}
            <button
              className="live-voice-primary"
              onClick={connect}
              disabled={connecting}
            >
              <Mic size={18} />
              {connecting ? "Connecting…" : "Start live voice"}
            </button>
          </>
        ) : (
          <LiveKitRoom
            key={credentials.roomName}
            serverUrl={credentials.serverUrl}
            token={credentials.participantToken}
            connect
            audio
            video={false}
            onDisconnected={finishCall}
            onError={(roomError) => setError(roomError.message)}
          >
            <ActiveVoiceCall
              error={error}
              onEnd={finishCall}
              onTranscriptChange={(messages) => {
                transcriptRef.current = messages;
              }}
            />
          </LiveKitRoom>
        )}
      </section>
    </div>
  );
}

function ActiveVoiceCall({
  error,
  onEnd,
  onTranscriptChange,
}: {
  error: string;
  onEnd: () => void;
  onTranscriptChange: (messages: CallTranscriptMessage[]) => void;
}) {
  const transcriptions = useTranscriptions();
  const { agent, state } = useVoiceAssistant();
  const room = useRoomContext();
  const [stopping, setStopping] = useState(false);
  const [interruptError, setInterruptError] = useState("");

  async function stopAgentSpeaking() {
    if (!agent?.identity || stopping) return;
    setStopping(true);
    setInterruptError("");
    try {
      await room.localParticipant.performRpc({
        destinationIdentity: agent.identity,
        method: "interrupt_agent",
        payload: "",
      });
    } catch {
      setInterruptError("Nicky could not be stopped. Please try again.");
    } finally {
      setStopping(false);
    }
  }

  const messages = useMemo<CallTranscriptMessage[]>(
    () =>
      transcriptions
        .map((item) => ({
          role:
            item.participantInfo.identity === agent?.identity
              ? ("assistant" as const)
              : ("user" as const),
          text: item.text.trim(),
        }))
        .filter((item) => item.text),
    [agent?.identity, transcriptions]
  );

  useEffect(() => {
    onTranscriptChange(messages);
  }, [messages, onTranscriptChange]);

  const stateLabel: Record<string, string> = {
    connecting: "Connecting to Nicky…",
    initializing: "Preparing voice session…",
    listening: "Listening…",
    thinking: "Checking NSSF information…",
    speaking: "Nicky is speaking",
    disconnected: "Disconnected",
  };

  return (
    <div className="live-voice-active">
      <div className={`live-voice-pulse state-${state}`}>
        <span />
        <Headphones size={32} />
      </div>
      <h2 id="live-voice-title">Live with Nicky</h2>
      <div className={`live-agent-state state-${state}`}>
        {stateLabel[state] || state}
      </div>
      {error && <div className="live-voice-error">{error}</div>}
      {interruptError && (
        <div className="live-voice-error">{interruptError}</div>
      )}

      <div className="live-transcript" aria-live="polite">
        {messages.length ? (
          messages.map((message, index) => (
            <div className={`live-transcript-line ${message.role}`} key={index}>
              <strong>{message.role === "assistant" ? "Nicky" : "You"}</strong>
              <span>{message.text}</span>
            </div>
          ))
        ) : (
          <div className="live-transcript-empty">
            Your call transcript will appear here.
          </div>
        )}
      </div>

      <div className="live-voice-controls">
        {(state === "speaking" || state === "thinking") && (
          <button
            className="live-voice-stop-speaking"
            onClick={stopAgentSpeaking}
            disabled={stopping || !agent?.identity}
          >
            <Square size={16} />
            {stopping ? "Stopping…" : "Stop speaking"}
          </button>
        )}
        <TrackToggle source={Track.Source.Microphone}>
          <Mic size={18} />
          Microphone
        </TrackToggle>
        <button className="live-voice-hangup" onClick={onEnd}>
          <PhoneOff size={18} />
          End
        </button>
      </div>
      <RoomAudioRenderer />
    </div>
  );
}
