from utils.groq_client import ask_groq
import json

def extract_skills(job_description: str, resume: str):
    system = """
You are an expert technical recruiter and skill analyst.

Extract required skills and break them into subskills.

Return ONLY valid JSON in this format:

{
  "skills": [
    {
      "name": "Python",
      "subskills": ["OOP", "Async Programming", "Error Handling"]
    }
  ]
}
"""

    user = f"""
Job Description:
{job_description}

Resume:
{resume}
"""

    raw = ask_groq(system, user)

    # 🔥 Clean markdown if present
    if "```" in raw:
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]

    raw = raw.strip()

    # 🔥 Robust JSON parsing
    try:
        data = json.loads(raw)
    except Exception as e:
        print("❌ JSON PARSE ERROR")
        print("RAW OUTPUT:\n", raw)
        raise ValueError("Invalid JSON from LLM")

    # 🔥 Safety fallback
    if "skills" not in data:
        return {
            "skills": []
        }

    return data