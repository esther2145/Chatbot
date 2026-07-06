type SpeechRecognitionResultCallback = (text: string) => void;
type SpeechCallback = () => void;
type SpeechErrorCallback = (message: string) => void;

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

if (typeof window !== "undefined" && window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}

function pickFemaleVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) =>
      /female|zira|samantha|google us english|jenny|aria|sonia|libby|eva/i.test(
        v.name
      )
    ) || voices.find((v) => v.lang.startsWith("en"))
  );
}

export function speakText(text: string, enabled: boolean = true): void {
  if (!enabled || !window.speechSynthesis) return;

  window.speechSynthesis.cancel();

  const cleanText = text
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/https?:\/\/\S+/g, "");

  const speech = new SpeechSynthesisUtterance(cleanText);
  speech.lang = "en-US";
  speech.rate = 1;
  speech.pitch = 1.1;
  speech.volume = 1;

  const femaleVoice = pickFemaleVoice();
  if (femaleVoice) speech.voice = femaleVoice;

  window.speechSynthesis.speak(speech);
}

// Keep a reference to the active session so a new one can replace it.
let activeRecognition: BrowserSpeechRecognition | null = null;

export function stopListening(): void {
  if (activeRecognition) {
    try {
      activeRecognition.abort();
    } catch {
      /* ignore */
    }
    activeRecognition = null;
  }
}

export function startListening(
  onResult: SpeechRecognitionResultCallback,
  onStart?: SpeechCallback,
  onEnd?: SpeechCallback,
  onError?: SpeechErrorCallback
): void {
  const speechWindow = window as SpeechWindow;

  const Recognition =
    speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;

  if (!Recognition) {
    onError?.("Voice input is not supported. Use Chrome or Edge.");
    return;
  }

  // Interrupt any session already running, so only the latest speech counts.
  stopListening();

  const recognition = new Recognition();
  activeRecognition = recognition;

  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => onStart?.();

  recognition.onresult = (event: any) => {
    const spokenText = event.results[0][0].transcript;
    onResult(spokenText);
  };

  recognition.onerror = (event: any) => {
    if (event.error === "aborted") return; // we interrupted on purpose
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      onError?.("Microphone blocked. Click the icon in the address bar and allow microphone access.");
    } else if (event.error === "no-speech") {
      onError?.("I didn't catch that. Please try speaking again.");
    } else if (event.error === "network") {
      onError?.("Speech service needs an internet connection.");
    } else {
      onError?.("Voice input failed: " + event.error);
    }
  };

  recognition.onend = () => {
    activeRecognition = null;
    onEnd?.();
  };

  recognition.start();
}