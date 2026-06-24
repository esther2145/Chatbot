type SpeechRecognitionResultCallback = (text: string) => void;
type SpeechCallback = () => void;
type SpeechErrorCallback = (message: string) => void;

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: any) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
};

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export function speakText(text: string, enabled: boolean = true): void {
  if (!enabled || !window.speechSynthesis) return;

  window.speechSynthesis.cancel();

  const speech = new SpeechSynthesisUtterance(text);
  speech.lang = "en-US";
  speech.rate = 1;
  speech.pitch = 1;
  speech.volume = 1;

  window.speechSynthesis.speak(speech);
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

  const recognition = new Recognition();

  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => onStart?.();

  recognition.onresult = (event: any) => {
    const spokenText = event.results[0][0].transcript;
    onResult(spokenText);
  };

  recognition.onerror = () => {
    onError?.("Voice input failed. Allow microphone access and try again.");
  };

  recognition.onend = () => onEnd?.();

  recognition.start();
}