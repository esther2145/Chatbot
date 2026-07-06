import speech_recognition as sr
import pyttsx3
import sounddevice as sd
import numpy as np
import io
import wave


# ── Text-to-Speech ────────────────────────────────────────────────────────────

def build_tts_engine():
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)
    engine.setProperty("rate", 165)
    engine.setProperty("volume", 0.95)
    return engine


def speak(engine, text: str):
    print(f"\n[Assistant] 🔊 {text}\n")
    engine.say(text)
    engine.runAndWait()


# ── Speech-to-Text (using sounddevice instead of PyAudio) ────────────────────

def listen(recognizer: sr.Recognizer, timeout: float = 5.0) -> str:
    """
    Record audio using sounddevice (no PyAudio needed),
    then transcribe using Google Speech Recognition.
    """
    SAMPLE_RATE = 16000
    CHANNELS    = 1
    DURATION    = timeout  # max seconds to record

    print("[Voice] 🎙️  Listening... (speak now)")

    try:
        # Record audio as a numpy array
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
        )
        sd.wait()  # wait until recording is done

        # Convert numpy array → WAV bytes in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)          # 16-bit = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(recording.tobytes())
        wav_buffer.seek(0)

        # Feed WAV bytes to SpeechRecognition
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(audio)
        print(f"[Voice] 🗣️  You said: {text}")
        return text

    except sr.UnknownValueError:
        print("[Voice] Could not understand audio.")
        return ""
    except sr.RequestError as e:
        print(f"[Voice] Speech recognition error: {e}")
        return ""
    except Exception as e:
        print(f"[Voice] Recording error: {e}")
        return ""


def get_input_mode() -> str:
    print("\n[Input] Press ENTER to speak, or type your question and press ENTER: ", end="")
    return input().strip()