from utils.groq_client import ask_groq

def evaluate_answer(question: str, answer: str) -> str:
    system = """
You are an expert technical evaluator.

Classify the candidate's answer into ONE of these:
- WEAK
- AVERAGE
- STRONG

Criteria:

WEAK:
- Vague
- Incorrect
- Lacks understanding

AVERAGE:
- Partial understanding
- Missing depth

STRONG:
- Clear
- Correct
- Detailed
- Shows real understanding

Respond with ONLY one word:
WEAK or AVERAGE or STRONG
"""

    user = f"""
Question:
{question}

Candidate Answer:
{answer}
"""

    result = ask_groq(system, user).strip().upper()

    if "WEAK" in result:
        return "WEAK"
    elif "STRONG" in result:
        return "STRONG"
    else:
        return "AVERAGE"