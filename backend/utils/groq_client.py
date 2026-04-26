from groq import Groq
import os
import time
from dotenv import load_dotenv

# ✅ LOAD ENV FILE
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=api_key)


def ask_groq(system, user):
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.7,
                max_tokens=600
            )
            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e)
            print(f"[Groq Retry {attempt+1}] Error:", e)

            # ── Rate limit hit ──
            if "429" in error_str or "rate_limit_exceeded" in error_str:
                # Try to extract wait time from error message
                wait_hint = ""
                if "Please try again in" in error_str:
                    try:
                        wait_hint = error_str.split("Please try again in")[1].split(".")[0].strip()
                    except:
                        wait_hint = "a few minutes"

                raise RateLimitError(
                    f"⚠️ Groq API daily token limit reached. Please wait {wait_hint} and try again. "
                    f"You can also upgrade to Groq Dev Tier at https://console.groq.com/settings/billing for higher limits."
                )

            time.sleep(2)

    raise Exception("Groq API failed after 3 retries. Please check your connection and try again.")


class RateLimitError(Exception):
    """Raised when Groq's rate limit is exceeded."""
    pass