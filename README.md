# SkillScan AI 🎯

> **AI-Powered Skill Assessment & Personalised Learning Plan Agent**

A resume tells you what someone *claims* to know — not how well they actually know it. **SkillScan AI** takes a Job Description and a candidate's resume, conversationally assesses real proficiency on each required skill, identifies gaps, and generates a personalised learning plan focused on adjacent skills the candidate can realistically acquire — with curated resources and time estimates.

Built for the **Catalyst Hackathon** by Deccan AI.

---

## ✨ What It Does

1. **Parses** a Job Description + Resume to extract required skills
2. **Conducts** a warm, adaptive conversational interview — asking deeper questions for strong answers, simpler ones for weak answers
3. **Evaluates** every answer as `WEAK`, `AVERAGE`, or `STRONG` in real time
4. **Scores** each skill on a 0–100 scale using an adaptive scoring engine
5. **Generates** a personalised learning plan with real, working resource links and time estimates

---

## 🖥️ Demo

> 📹 **[Watch the 5-minute demo video →](#)** *(link to be added)*

**Live App:** *(deployed URL or see local setup below)*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (HTML/JS)                    │
│                                                              │
│   index.html  →  upload.html  →  assess.html  →  report.html│
│   (Landing)      (JD + Resume)   (Live Chat)    (Results)   │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API (fetch)
┌───────────────────────────▼─────────────────────────────────┐
│                    BACKEND (FastAPI / Python)                 │
│                                                              │
│  POST /analyze   →  skill_extractor.py  →  Skills List       │
│  POST /assess    →  Adaptive Interview Engine                 │
│  POST /score     →  Scoring Engine + Learning Plan Generator  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      GROQ API (LLaMA 3.3 70B)                │
│                                                              │
│  • Skill extraction from JD + Resume                         │
│  • Answer evaluation (WEAK / AVERAGE / STRONG)               │
│  • Adaptive interview question generation                     │
│  • Learning plan + resource curation                         │
│  • Candidate profile summary generation                      │
└─────────────────────────────────────────────────────────────┘
```

### Agent Flow

```
JD + Resume
    │
    ▼
[Skill Extractor Agent]
    │  Extracts top skills from JD,
    │  cross-referenced against resume
    ▼
[Interview Agent] ◄──────────────────────────────┐
    │  Asks ONE focused question per skill        │
    │  Evaluates answer → WEAK/AVERAGE/STRONG     │
    │  Adapts next question depth accordingly     │
    │  Switches skill after 5 answers OR          │
    │  2 consecutive WEAK / 4 consecutive STRONG  │
    └─────────────────────────────────────────────┘
    │  (when all skills assessed)
    ▼
[Scoring Engine]
    │  Computes per-skill score (0–100)
    │  Categorises: Proficient / Developing / Gap
    ▼
[Learning Plan Agent]
    │  Generates personalised resources per gap skill
    │  Focuses on adjacent skills candidate can acquire
    │  Provides real URLs + time estimates
    ▼
[Report]
    Professional PDF-style report with scores + plan
```

---

## 📊 Scoring Logic

Each skill is scored from **0–100** based on the candidate's adaptive interview performance.

### Per-Skill Score Calculation

| Performance Level | Base Score | Modifiers |
|---|---|---|
| **STRONG** | 75 | +5 per additional strong answer (max +20); -8 if any weak answer |
| **AVERAGE** | 50 | +5 if >60% avg answers; +12 if any strong answer; -5 otherwise |
| **WEAK** | 38 | -8 per consecutive weak answer (max -22); +5 if answered ≥4 questions |

Scores are clamped between **10 and 95**.

### Overall Score

Simple mean of all per-skill scores.

### Gap Categories

| Score | Category | Meaning |
|---|---|---|
| ≥ 78 | ✅ Proficient | Candidate demonstrates solid command |
| 52–77 | 🔶 Developing | Partial understanding, needs targeted work |
| < 52 | ❌ Gap | Significant gap, prioritised in learning plan |

### Adaptive Switch Logic

The interviewer moves to the next skill when:
- **2 consecutive WEAK answers** → candidate is struggling, move on
- **4 consecutive STRONG answers** → candidate has demonstrated mastery
- **5 total answers** → sufficient data collected for that skill

---

## 🗂️ Project Structure

```
SkillScan AI/
├── backend/
│   ├── main.py                  # FastAPI app — all 3 endpoints
│   ├── agents/
│   │   ├── skill_extractor.py   # Extracts skills from JD + Resume
│   │   └── evaluator.py         # Rates answers as WEAK/AVERAGE/STRONG
│   └── utils/
│       └── groq_client.py       # Groq API wrapper with rate-limit handling
├── frontend/
│   ├── index.html               # Landing page
│   ├── upload.html              # JD + Resume input
│   ├── assess.html              # Live conversational assessment
│   └── report.html              # Scores + personalised learning plan
├── requirements.txt
└── README.md
```

---

## ⚙️ Local Setup

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com/) (free tier available)

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/skillscan-ai.git
cd skillscan-ai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment

Create a `.env` file in the `backend/` directory:

```bash
# backend/.env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Backend will be running at `http://localhost:8000`

### 5. Open the frontend

Open `frontend/index.html` in your browser. That's it — no build step needed!

> **Tip:** Use VS Code's Live Server extension or `python -m http.server 3000` from the `frontend/` directory for the best experience.

---

## 📦 Requirements

```
fastapi
uvicorn
groq
python-dotenv
python-multipart
PyPDF2
```

---

## 🔌 API Reference

### `POST /analyze`
Extracts skills from a Job Description and Resume.

**Request:**
```json
{
  "job_description": "We are looking for a Python developer...",
  "resume": "I have 3 years of experience in Python, FastAPI..."
}
```

**Response:**
```json
{
  "skills_to_assess": ["Python", "FastAPI", "SQL", "Docker"],
  "full_skill_tree": [
    {
      "name": "Python",
      "subskills": ["OOP", "Async Programming", "Error Handling"]
    }
  ]
}
```

---

### `POST /assess`
Drives the adaptive conversational interview — one turn at a time.

**Request:**
```json
{
  "job_description": "...",
  "resume": "...",
  "conversation_history": [],
  "user_message": "",
  "skills": ["Python", "FastAPI", "SQL"],
  "current_skill": "Python",
  "skill_state": {}
}
```

**Response:**
```json
{
  "message": "Great to meet you! I noticed you've worked with Python for 3 years — can you walk me through how you've used async programming in a real project?",
  "is_complete": false,
  "level": null,
  "switch_skill": false,
  "next_skill": "Python",
  "updated_state": {
    "strongCount": 0,
    "weakStreak": 0,
    "answerCount": 0,
    "avgCount": 0
  }
}
```

---

### `POST /score`
Generates final scores and a personalised learning plan.

**Request:**
```json
{
  "job_description": "...",
  "resume": "...",
  "skills": ["Python", "FastAPI", "SQL"],
  "skill_results": {
    "Python": { "level": "STRONG", "strongCount": 3, "weakStreak": 0, "answerCount": 4, "avgCount": 0 },
    "FastAPI": { "level": "AVERAGE", "strongCount": 1, "weakStreak": 0, "answerCount": 3, "avgCount": 2 },
    "SQL": { "level": "WEAK", "strongCount": 0, "weakStreak": 2, "answerCount": 3, "avgCount": 1 }
  },
  "conversation_history": [...]
}
```

**Response:**
```json
{
  "overall_score": 62,
  "skill_scores": { "Python": 90, "FastAPI": 57, "SQL": 30 },
  "proficient": ["Python"],
  "developing": ["FastAPI"],
  "gaps": ["SQL"],
  "learning_plan": [
    {
      "skill": "SQL",
      "gap_reason": "Candidate struggled with query optimisation and JOIN operations.",
      "adjacent_skills": ["Database Design", "Query Optimisation"],
      "resources": [
        { "title": "SQL for Data Scientists – Full Course", "url": "https://www.kaggle.com/learn/advanced-sql", "type": "Course" },
        { "title": "SQL Practice", "url": "https://leetcode.com/studyplan/top-sql-50/", "type": "Practice" }
      ],
      "tip": "Start by mastering JOINs and GROUP BY — these cover 80% of real-world SQL queries.",
      "weeks": 3
    }
  ],
  "summary": "The candidate demonstrates strong Python fundamentals with solid async and OOP knowledge. FastAPI shows developing proficiency, and SQL represents the primary growth area for this role."
}
```

---

## 🧪 Sample Inputs

### Sample Job Description
```
Senior Python Backend Developer

We're looking for a backend engineer with strong Python skills to build 
scalable APIs. You will work with FastAPI, design SQL databases, and deploy 
using Docker and CI/CD pipelines.

Required: Python (3+ years), FastAPI, PostgreSQL/SQL, Docker, REST API design
Nice to have: Redis, Kubernetes, AWS
```

### Sample Resume
```
Jane Smith | Backend Developer | jane@email.com

Experience:
- 3 years Python development at TechCorp (2021–2024)
  • Built REST APIs using Flask and Django
  • Worked with MySQL databases
  • Basic Docker containerisation

Skills: Python, Flask, Django, MySQL, Git, Linux
Education: B.Tech Computer Science, 2021
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| LLM | Groq API — LLaMA 3.3 70B Versatile |
| Deployment | Uvicorn (local) |

---

## 🚀 What Makes It Special

- **Truly adaptive** — questions get harder or easier based on your answers, just like a real interview
- **No hallucinated resources** — learning plan resources are constrained to trusted domains (Coursera, LeetCode, MDN, etc.)
- **Adjacent skill focus** — learning plan targets skills the candidate can *realistically* acquire given their background
- **Beautiful UI** — polished, production-quality interface with smooth animations
- **Graceful rate-limit handling** — clear user-facing messages when API limits are hit

---

## 👤 Author

Built with ❤️ for Catalyst Hackathon by Deccan AI

---

## 📄 License

MIT License — feel free to use and extend.