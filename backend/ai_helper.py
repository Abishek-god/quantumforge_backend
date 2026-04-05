"""
Quantum Forge — AI Helper
Groq API integration for code explanation, hints, error fixing, and quiz generation.
"""

import os
import json
from groq import Groq

# ── Initialize Groq Client ──────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama3-70b-8192"


def _chat(system_prompt, user_message, temperature=0.7, max_tokens=2048):
    """Internal helper for Groq chat completion."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"


# ── Code Explanation ────────────────────────────────────────
def explain_code(code):
    """Explain a code snippet line-by-line in a beginner-friendly way."""
    system_prompt = """You are a friendly Python tutor for beginners.
Explain the given code line-by-line in a clear, encouraging way.
Use simple language and provide analogies when helpful.
Format your response with markdown for readability.
Start with a brief summary of what the code does, then explain each line."""

    return _chat(system_prompt, f"Please explain this Python code:\n\n```python\n{code}\n```")


# ── Smart Hints ─────────────────────────────────────────────
def get_hint(problem_description, user_code, hint_level=1):
    """Give a contextual hint based on the problem and user's current attempt."""
    levels = {
        1: "Give a very subtle hint — just a nudge in the right direction without revealing the approach.",
        2: "Give a moderate hint — suggest the general approach or algorithm to use.",
        3: "Give a strong hint — explain the approach step-by-step but don't write the code.",
    }

    hint_instruction = levels.get(hint_level, levels[1])

    system_prompt = f"""You are a supportive coding mentor.
The student is working on a coding problem and needs help.
{hint_instruction}
Never give the complete solution.
Be encouraging and positive.
Format with markdown."""

    user_message = f"""Problem: {problem_description}

Student's current code:
```python
{user_code}
```

Please provide a hint."""

    return _chat(system_prompt, user_message)


# ── Error Fixing ────────────────────────────────────────────
def fix_code(code, error_message):
    """Analyze buggy code and suggest fixes with explanation."""
    system_prompt = """You are an expert Python debugger and teacher.
Analyze the code and the error message.
1. Explain what went wrong in simple terms
2. Show the corrected code
3. Explain the fix so the student learns

Format your response with markdown. Use code blocks for code."""

    user_message = f"""This code has an error:

```python
{code}
```

Error message:
```
{error_message}
```

Please help me fix it and explain what went wrong."""

    return _chat(system_prompt, user_message)


# ── Quiz Generation ─────────────────────────────────────────
def generate_quiz(topic, count=5):
    """Generate MCQ quiz questions on a Python topic."""
    system_prompt = """You are a Python quiz generator.
Generate multiple choice questions about the given topic.
Return ONLY a valid JSON array with no extra text.
Each question object must have:
- "question": the question text
- "options": array of 4 option strings (A, B, C, D)
- "correct": index of correct option (0-3)
- "explanation": brief explanation of the answer

Make questions progressively harder. Include code snippets when relevant.
Only return valid JSON — no markdown, no extra text."""

    user_message = f"Generate {count} Python quiz questions about: {topic}"

    response = _chat(system_prompt, user_message, temperature=0.5)

    # Try to parse JSON from response
    try:
        # Handle potential markdown code blocks
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback with default questions
        return _fallback_quiz(topic, count)


def _fallback_quiz(topic, count):
    """Fallback quiz if AI generation fails."""
    return [
        {
            "question": f"Which of the following best describes '{topic}' in Python?",
            "options": [
                "A built-in data type",
                "A control flow statement",
                "A function parameter",
                "A module"
            ],
            "correct": 0,
            "explanation": f"This is a fallback question. The AI quiz generation for '{topic}' encountered an issue."
        }
    ] * min(count, 5)


# ── Code Review ─────────────────────────────────────────────
def review_code(code, problem_description=""):
    """Provide a comprehensive code review with suggestions."""
    system_prompt = """You are a senior Python developer doing a code review for a student.
Provide constructive feedback on:
1. Correctness — Does it solve the problem?
2. Style — Is the code clean and Pythonic?
3. Efficiency — Can it be optimized?
4. Edge cases — Are there inputs it would fail on?

Give a score out of 100 and specific improvement suggestions.
Be encouraging but honest. Format with markdown."""

    context = f"\n\nProblem description: {problem_description}" if problem_description else ""
    user_message = f"Please review this code:{context}\n\n```python\n{code}\n```"

    return _chat(system_prompt, user_message)
