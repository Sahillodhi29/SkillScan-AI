from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

from utils.groq_client import ask_groq
from agents.skill_extractor import extract_skills
from agents.evaluator import evaluate_answer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ─────────────────────────────
# MODELS
# ─────────────────────────────
class AnalyzeRequest(BaseModel):
    job_description: str
    resume: str

class AssessRequest(BaseModel):
    job_description: str
    resume: str
    conversation_history: list
    user_message: str
    skills: list
    current_skill: Optional[str] = None
    skill_state: Optional[dict] = None

class ScoreRequest(BaseModel):
    job_description: str
    resume: str
    skills: list
    skill_results: dict
    conversation_history: list


# ─────────────────────────────
# CONTEXT BUILDER
# ─────────────────────────────
def build_context(history):
    recent = history[-8:]
    text = ""
    for msg in recent:
        role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
        text += f"{role}: {msg['content']}\n\n"
    return text.strip()


# ─────────────────────────────
# SCORING ENGINE
# ─────────────────────────────
def compute_skill_score(skill_data: dict) -> int:
    level = skill_data.get("level", "AVERAGE")
    strong_count  = skill_data.get("strongCount", 0)
    weak_streak   = skill_data.get("weakStreak", 0)
    answer_count  = skill_data.get("answerCount", 1)
    avg_count     = skill_data.get("avgCount", 0)

    if level == "STRONG":
        base = 75
        depth_bonus = min(strong_count * 5, 20)
        score = base + depth_bonus
        if weak_streak > 0:
            score -= 8
    elif level == "WEAK":
        base = 38
        streak_penalty = min(weak_streak * 8, 22)
        score = base - streak_penalty
        if answer_count >= 4:
            score += 5
    else:  # AVERAGE
        base = 50
        ratio = avg_count / max(answer_count, 1)
        if ratio > 0.6:
            score = base + 5
        elif strong_count > 0:
            score = base + 12
        else:
            score = base - 5

    return max(10, min(95, int(score)))


def overall_score(skill_scores: dict) -> int:
    if not skill_scores:
        return 50
    return round(sum(skill_scores.values()) / len(skill_scores))


def gap_category(score: int) -> str:
    if score >= 78:
        return "proficient"
    elif score >= 52:
        return "developing"
    else:
        return "gap"


# ─────────────────────────────
# ANALYZE
# ─────────────────────────────
@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    skills_data = extract_skills(request.job_description, request.resume)
    skills_list = [skill["name"] for skill in skills_data.get("skills", [])]

    return {
        "skills_to_assess": skills_list,
        "full_skill_tree": skills_data.get("skills", [])
    }


# ─────────────────────────────
# ASSESS
# ─────────────────────────────
@app.post("/assess")
async def assess(request: AssessRequest):

    skills = request.skills if request.skills else ["General Knowledge"]
    current_skill = request.current_skill or skills[0]
    state = request.skill_state or {}

    # ── OPENING QUESTION ──────────────────────────────────────────
    if len(request.conversation_history) == 0 and not request.user_message.strip():
        system = f"""You are a warm, experienced technical interviewer conducting a real job interview.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Your task:
- Greet the candidate naturally and warmly (one short sentence)
- Then immediately ask ONE focused question about: {current_skill}
- The question should be specific and contextual — reference something from their resume if possible
- Keep it conversational, not robotic
- Do NOT list multiple questions. Ask exactly ONE question."""

        reply = ask_groq(system, "Start the interview with a warm greeting and one focused question.")
        return {
            "message": reply.strip(),
            "is_complete": False,
            "level": None,
            "switch_skill": False,
            "next_skill": current_skill
        }

    # ── LEARNING PLAN GENERATION ──────────────────────────────────
    if request.user_message.startswith("Generate a personalised learning plan"):
        system = """You are an expert career coach. Generate a personalised learning plan.
Return ONLY a valid JSON array — no markdown, no explanation.
Format: [{"skill":"...","tip":"...","weeks":N}]
Each tip must be specific and actionable (one sentence)."""
        raw = ask_groq(system, request.user_message)
        return {
            "message": raw.strip(),
            "is_complete": False,
            "level": None,
            "switch_skill": False,
            "next_skill": current_skill
        }

    # ── GET LAST INTERVIEWER QUESTION ─────────────────────────────
    last_question = ""
    for msg in reversed(request.conversation_history):
        if msg["role"] == "assistant":
            last_question = msg["content"]
            break

    # ── EVALUATE CANDIDATE'S ANSWER ───────────────────────────────
    level = "AVERAGE"
    if last_question and request.user_message.strip():
        try:
            level = evaluate_answer(last_question, request.user_message)
        except Exception:
            level = "AVERAGE"

    # ── READ SKILL STATE ──────────────────────────────────────────
    strong_count  = state.get("strongCount", 0)
    weak_streak   = state.get("weakStreak", 0)
    answer_count  = state.get("answerCount", 0)
    avg_count     = state.get("avgCount", 0)

    # Update state based on new answer
    if level == "STRONG":
        strong_count += 1
        weak_streak = 0
    elif level == "WEAK":
        weak_streak += 1
        strong_count = max(0, strong_count - 1)
    else:  # AVERAGE
        weak_streak = 0
        strong_count = max(0, strong_count - 1)
        avg_count += 1

    answer_count += 1

    # ── ADAPTIVE SWITCH DECISION ──────────────────────────────────
    force_switch = False

    if answer_count >= 2:
        if weak_streak >= 2:
            force_switch = True
        elif strong_count >= 4:
            force_switch = True
        elif answer_count >= 5:   # ← reduced from 6 to 5 for snappier flow
            force_switch = True

    current_idx = skills.index(current_skill) if current_skill in skills else 0
    is_last_skill = (current_idx == len(skills) - 1)

    # ── KEY FIX: wrap_up fires whenever force_switch on last skill ──
    # Previously: wrap_up required switching=True AND is_last_skill
    # But if there's no next skill, switching was False → wrap_up never fired
    wrap_up = force_switch and is_last_skill

    if force_switch and not is_last_skill:
        next_skill = skills[current_idx + 1]
        switching = True
    else:
        next_skill = current_skill
        switching = False

    # ── BUILD SYSTEM PROMPT ───────────────────────────────────────
    history_text = build_context(request.conversation_history)

    if wrap_up:
        # Assessment complete — thank and wrap up
        system = f"""You are a warm, experienced technical interviewer who has just completed a full skills assessment.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Skills assessed: {', '.join(skills)}
Last skill assessed: {current_skill}
Candidate's last answer level: {level}

Your task:
1. Briefly acknowledge their last answer naturally (one short sentence)
2. Warmly thank the candidate for completing the assessment — genuine, human, not corporate
3. Tell them their performance report and personalised learning plan is being generated
4. Keep it warm, encouraging, and professional — 3-4 sentences max

STRICT RULES:
- Do NOT give scores or grades here
- Be genuinely warm and human
- End on an encouraging note"""

        user_prompt = f"""Candidate's last answer: "{request.user_message}"
Wrap up the interview warmly."""

    elif switching:
        system = f"""You are a warm, experienced technical interviewer.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Current situation:
- You have just finished assessing: {current_skill}
- Candidate's last answer level: {level}
- You are now transitioning to assess: {next_skill}

Conversation so far:
{history_text}

Your task:
1. Acknowledge the previous answer briefly and naturally (one short sentence)
2. Use a smooth, human transition phrase
3. Ask ONE specific, focused question about: {next_skill}
4. Reference something from their resume if relevant

STRICT RULES:
- Ask exactly ONE question about {next_skill}
- Keep the whole response under 4 sentences"""

        user_prompt = f"""Candidate's latest answer: "{request.user_message}"
Now respond as the interviewer."""

    elif level == "WEAK":
        system = f"""You are a warm, experienced technical interviewer.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Current skill being assessed: {current_skill}
Candidate's answer level: WEAK (they struggled)
Weak answers in a row: {weak_streak}

Conversation so far:
{history_text}

Your task:
1. Briefly and genuinely encourage (one short, warm sentence)
2. Ask a SIMPLER, more fundamental question about {current_skill}

STRICT RULES:
- Ask exactly ONE question, simpler than before
- Keep the whole response under 3 sentences"""

        user_prompt = f"""Candidate's latest answer: "{request.user_message}"
Now respond as the interviewer."""

    elif level == "STRONG":
        system = f"""You are a warm, experienced technical interviewer.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Current skill being assessed: {current_skill}
Candidate's answer level: STRONG (impressive answer)
Strong answers so far: {strong_count}

Conversation so far:
{history_text}

Your task:
1. Briefly acknowledge positively (one natural sentence)
2. Ask a DEEPER, more challenging follow-up question about {current_skill}

STRICT RULES:
- Ask exactly ONE deeper question
- Keep the whole response under 4 sentences"""

        user_prompt = f"""Candidate's latest answer: "{request.user_message}"
Now respond as the interviewer."""

    else:
        system = f"""You are a warm, experienced technical interviewer.

Job Description:
{request.job_description}

Candidate Resume:
{request.resume}

Current skill being assessed: {current_skill}
Candidate's answer level: AVERAGE (partial understanding shown)

Conversation so far:
{history_text}

Your task:
1. Naturally acknowledge their answer (one short sentence)
2. Ask a follow-up question that probes a specific aspect within {current_skill}

STRICT RULES:
- Ask exactly ONE question
- Keep the whole response under 4 sentences"""

        user_prompt = f"""Candidate's latest answer: "{request.user_message}"
Now respond as the interviewer."""

    # ── LLM CALL ──────────────────────────────────────────────────
    try:
        reply = ask_groq(system, user_prompt)
        if not reply or len(reply.strip()) < 5:
            raise ValueError("Empty reply")
    except Exception as e:
        error_str = str(e)
        print("LLM ERROR:", e)

        if "token limit" in error_str.lower() or "rate limit" in error_str.lower() or "⚠️" in error_str:
            reply = error_str
        elif wrap_up:
            reply = f"Thank you so much for completing this assessment today — you tackled some genuinely tough questions with great thought. Your personalised performance report and learning plan are being generated right now. Best of luck with your journey ahead!"
        elif switching:
            reply = f"Thanks for that. Let's move on — tell me about your experience with {next_skill}?"
        elif level == "WEAK":
            reply = f"No worries — let's try a different angle on {current_skill}. Can you describe a time you've used it, even in a small project?"
        else:
            reply = f"Good. Can you go deeper on that — what are the trade-offs or challenges you've encountered with {current_skill}?"

    updated_state = {
        "strongCount": strong_count,
        "weakStreak": weak_streak,
        "answerCount": answer_count,
        "avgCount": avg_count
    }

    return {
        "message": reply.strip(),
        "is_complete": wrap_up,   # ← TRUE when on last skill and force_switch fires
        "level": level,
        "switch_skill": switching,
        "next_skill": next_skill,
        "updated_state": updated_state
    }


# ─────────────────────────────
# SCORE
# ─────────────────────────────
@app.post("/score")
async def score(request: ScoreRequest):
    skill_scores = {}
    for skill in request.skills:
        skill_data = request.skill_results.get(skill, {})
        skill_scores[skill] = compute_skill_score(skill_data)

    total = overall_score(skill_scores)

    proficient  = [s for s in request.skills if gap_category(skill_scores[s]) == "proficient"]
    developing  = [s for s in request.skills if gap_category(skill_scores[s]) == "developing"]
    gaps        = [s for s in request.skills if gap_category(skill_scores[s]) == "gap"]

    target_skills = gaps + developing
    learning_plan = []

    if target_skills:
        system = """You are an expert career coach and learning strategist.

Generate a personalised learning plan with real, working resources.

Return ONLY a valid JSON array. No markdown, no preamble.

Format exactly:
[
  {
    "skill": "skill name",
    "gap_reason": "one sentence why this needs work based on the assessment",
    "adjacent_skills": ["skill1", "skill2"],
    "resources": [
      {"title": "resource title", "url": "https://real-working-url.com", "type": "Course|Book|Practice|Video|Documentation"},
      {"title": "another resource", "url": "https://another-real-url.com", "type": "Practice"}
    ],
    "tip": "specific actionable advice in one sentence",
    "weeks": 4
  }
]

CRITICAL: Use ONLY real, working URLs from these trusted sources:
- Courses: coursera.org, udemy.com, edx.org, freecodecamp.org, theodinproject.com, fullstackopen.com
- Practice: leetcode.com, hackerrank.com, exercism.org, codewars.com, kaggle.com
- Docs: docs.python.org, developer.mozilla.org, reactjs.org, docs.docker.com, kubernetes.io/docs
- Books: O'Reilly at learning.oreilly.com, or specific book landing pages
- Videos: youtube.com (specific playlists/channels only if well-known)
- Roadmaps: roadmap.sh"""

        user = f"""Job Description:
{request.job_description}

Candidate Resume (summarised):
{request.resume[:800]}

Skills needing improvement (priority order — gaps first):
{json.dumps({s: skill_scores[s] for s in target_skills}, indent=2)}

Proficient skills (for context):
{proficient}

Generate a learning plan for each skill that needs improvement.
Focus on ADJACENT skills they can realistically acquire given their background.
Each skill needs exactly 2 resources with real working URLs."""

        try:
            raw = ask_groq(system, user)
            if "```" in raw:
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            m = __import__('re').search(r'\[[\s\S]*\]', raw)
            if m:
                learning_plan = json.loads(m.group(0))
        except Exception as e:
            print("Learning plan generation error:", e)
            for s in target_skills:
                learning_plan.append({
                    "skill": s,
                    "gap_reason": f"Assessment showed developing proficiency in {s}.",
                    "adjacent_skills": [],
                    "resources": [
                        {"title": f"{s} – Full Course", "url": "https://www.freecodecamp.org", "type": "Course"},
                        {"title": f"Practice {s}", "url": "https://exercism.org", "type": "Practice"}
                    ],
                    "tip": f"Build 2-3 small projects using {s} to solidify your understanding.",
                    "weeks": 4
                })

    summary_system = """You are an expert technical recruiter writing a concise candidate profile summary.
Write 2-3 sentences. Be specific, balanced, and professional.
Reference the strongest skills and the main growth areas.
Do NOT use bullet points. Plain prose only."""

    summary_user = f"""Candidate skills assessed:
Proficient: {proficient}
Developing: {developing}
Needs work: {gaps}
Overall score: {total}%

Job they applied for:
{request.job_description[:400]}

Write a balanced 2-3 sentence professional summary of this candidate's profile."""

    try:
        summary = ask_groq(summary_system, summary_user).strip()
    except:
        strong_str = ", ".join(proficient) if proficient else "some areas"
        gap_str = ", ".join(gaps) if gaps else "a few areas"
        summary = f"The candidate shows solid proficiency in {strong_str}, demonstrating real-world understanding across assessed competencies. Growth opportunities exist in {gap_str}, where targeted effort could unlock significant career advancement. The personalised plan below is designed to close those gaps efficiently."

    return {
        "overall_score": total,
        "skill_scores": skill_scores,
        "proficient": proficient,
        "developing": developing,
        "gaps": gaps,
        "learning_plan": learning_plan,
        "summary": summary
    }


@app.get("/")
async def root():
    return {"status": "SkillScan AI running 🚀"}