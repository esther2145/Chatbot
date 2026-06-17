import time
from groq import Groq

MAX_CONTEXT_CHARS = 80_000

SYSTEM_PROMPT = """
You are a helpful, friendly, and knowledgeable assistant specialising in
the National Social Security Fund (NSSF) of Uganda.

You answer questions ONLY based on the NSSF Uganda website content provided
to you below. If a question falls outside the provided content, politely say
you don't have that information and suggest the user visits www.nssf.or.ug
or calls NSSF directly on 0800 100 066.

Keep your answers clear, concise, and easy to understand — the user may be
listening via text-to-speech, so avoid using bullet symbols, markdown, or
special characters. Use plain sentences instead.

NSSF WEBSITE CONTENT:
{nssf_context}
"""


class NSSFAssistant:
    def __init__(self, api_key: str, nssf_context: str):
        if not api_key:
            raise ValueError(
                "Groq API key is missing. "
                "Please set the GROQ_API_KEY environment variable."
            )

        self.client = Groq(api_key=api_key)

        trimmed = nssf_context[:MAX_CONTEXT_CHARS]
        self.system_prompt = SYSTEM_PROMPT.format(nssf_context=trimmed)

        # Groq doesn't maintain session history like Gemini
        # so we keep it ourselves
        self.history = []

        print("[Assistant] ✅ Groq assistant ready.")

    def ask(self, question: str) -> str:
        if not question.strip():
            return "I didn't catch that. Could you please repeat your question?"

        # Add user question to history
        self.history.append({"role": "user", "content": question})

        max_retries = 5
        wait_seconds = 15

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[Assistant] Sending question to Groq (attempt {attempt})...")
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",  # best free Groq model
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        *self.history,
                    ],
                    max_tokens=1024,
                )
                answer = response.choices[0].message.content.strip()

                # Save assistant reply to history
                self.history.append({"role": "assistant", "content": answer})

                # Keep history from growing too large (last 10 exchanges)
                if len(self.history) > 20:
                    self.history = self.history[-20:]

                return answer

            except Exception as e:
                error_msg = str(e)
                print(f"[Assistant] ❌ Error: {type(e).__name__}: {error_msg[:120]}")

                if "429" in error_msg and attempt < max_retries:
                    print(f"[Assistant] ⏳ Rate limited — waiting {wait_seconds}s then retrying...")
                    time.sleep(wait_seconds)
                    wait_seconds *= 2
                else:
                    break

        return "I'm sorry, I'm currently over my usage limit. Please try again in a few minutes."