import os
import speech_recognition as sr

from scrapper import scrape_all_pages
from assistant import NSSFAssistant
from voice import build_tts_engine, speak, listen, get_input_mode

# --- CONFIGURATION ------------------------------------------------------------

# Option A: Hard-code your key here (not recommended for shared projects)
#GEMINI_API_KEY = "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"  # Replace with your actual Gemini API key
# Option B (recommended): Set environment variable GEMINI_API_KEY and use this:
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# --- MAIN ---------------------------------------------------------------------

def main():
    if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        print("Please set your GROQ API key in main.py or as an environment variable.")
        return

    # 1. Scrape NSSF websitey
    nssf_context = scrape_all_pages()

    if not nssf_context.strip():
        print("No content was scraped. Check your internet connection and try again.")
        return

    # 2. Set up GROQ assistant
    assistant = NSSFAssistant(api_key=GROQ_API_KEY, nssf_context=nssf_context)

    # 3. Set up voice engine and speech recogniser
    tts_engine = build_tts_engine()
    recognizer = sr.Recognizer()

    # 4. Greet the user
    greeting = (
        "Hello! I am your NSSF Uganda assistant. "
        "You can ask me anything about NSSF services, benefits, membership, and more. "
        "Press ENTER to speak, or type your question directly. "
        "Say or type 'quit' to exit."
    )
    speak(tts_engine, greeting)

    # 5. Main conversation loop
    while True:
        user_input = get_input_mode()

        # If user pressed ENTER without typing, use voice
        if user_input == "":
            user_input = listen(recognizer)

        if not user_input:
            speak(tts_engine, "I didn't hear anything. Please try again.")
            continue

        if user_input.lower() in ("quit", "exit", "bye", "goodbye"):
            speak(tts_engine, "Goodbye! Thank you for using the NSSF assistant. Have a great day!")
            break

        # Get answer from Groq
        answer = assistant.ask(user_input)

        # Speak and print the answer
        speak(tts_engine, answer)


if __name__ == "__main__":
    main()
