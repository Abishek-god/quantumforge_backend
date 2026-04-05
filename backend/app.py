"""
Quantum Forge — Flask Backend
Main application with all REST API routes.
Deployed on Render.
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ── App Setup ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins=["*"])  # In production, restrict to your Netlify domain

# ── Import Modules ──────────────────────────────────────────
from execute import execute_code, run_test_cases, extract_function_name
from ai_helper import explain_code, get_hint, fix_code, generate_quiz, review_code
from supabase_client import (
    get_problems,
    get_problem_by_id,
    get_daily_challenge,
    save_submission,
    get_user_submissions,
    get_user_stats,
    update_user_stats,
    get_achievements,
    get_user_achievements,
    check_and_award_achievements,
    get_leaderboard,
    save_quiz_score,
    get_user_quiz_scores,
)


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Quantum Forge API is running 🚀"})


# ══════════════════════════════════════════════════════════════
#  CODE EXECUTION
# ══════════════════════════════════════════════════════════════
@app.route("/api/execute", methods=["POST"])
def execute():
    """Execute user code and return output."""
    data = request.get_json()
    code = data.get("code", "")

    if not code.strip():
        return jsonify({"error": "No code provided"}), 400

    result = execute_code(code)
    return jsonify(result)


@app.route("/api/submit", methods=["POST"])
def submit_solution():
    """Submit code against a problem's test cases."""
    data = request.get_json()
    code = data.get("code", "")
    problem_id = data.get("problem_id")
    user_id = data.get("user_id")

    if not code.strip() or not problem_id:
        return jsonify({"error": "Code and problem_id are required"}), 400

    # Get problem and its test cases
    problem = get_problem_by_id(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    test_cases = problem.get("test_cases", [])
    function_name = extract_function_name(code)

    # Run against test cases
    result = run_test_cases(code, test_cases, function_name)

    # Calculate score
    score = int((result["passed_count"] / max(result["total"], 1)) * 100)

    # Save submission if user is logged in
    if user_id:
        save_submission(user_id, problem_id, code, result["passed"], score)

        if result["passed"]:
            xp = problem.get("xp_reward", 10)
            update_user_stats(user_id, xp, problem_solved=True)
            new_achievements = check_and_award_achievements(user_id)
            result["new_achievements"] = new_achievements
            result["xp_earned"] = xp

    result["score"] = score
    return jsonify(result)


# ══════════════════════════════════════════════════════════════
#  PROBLEMS
# ══════════════════════════════════════════════════════════════
@app.route("/api/problems", methods=["GET"])
def list_problems():
    """Get all problems, optionally filtered."""
    difficulty = request.args.get("difficulty")
    category = request.args.get("category")
    problems = get_problems(difficulty, category)
    return jsonify(problems)


@app.route("/api/problems/<int:problem_id>", methods=["GET"])
def get_problem(problem_id):
    """Get a single problem with full details."""
    problem = get_problem_by_id(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404
    return jsonify(problem)


@app.route("/api/daily-challenge", methods=["GET"])
def daily_challenge():
    """Get today's daily challenge."""
    challenge = get_daily_challenge()
    if not challenge:
        return jsonify({"error": "No challenges available"}), 404
    return jsonify(challenge)


# ══════════════════════════════════════════════════════════════
#  AI ASSISTANT
# ══════════════════════════════════════════════════════════════
@app.route("/api/ai/explain", methods=["POST"])
def ai_explain():
    """AI explains a code snippet."""
    data = request.get_json()
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"error": "No code provided"}), 400
    explanation = explain_code(code)
    return jsonify({"explanation": explanation})


@app.route("/api/ai/hint", methods=["POST"])
def ai_hint():
    """AI gives a hint for a problem."""
    data = request.get_json()
    problem = data.get("problem_description", "")
    code = data.get("code", "")
    level = data.get("hint_level", 1)
    hint = get_hint(problem, code, level)
    return jsonify({"hint": hint})


@app.route("/api/ai/fix", methods=["POST"])
def ai_fix():
    """AI fixes buggy code."""
    data = request.get_json()
    code = data.get("code", "")
    error = data.get("error_message", "")
    if not code.strip():
        return jsonify({"error": "No code provided"}), 400
    fix = fix_code(code, error)
    return jsonify({"fix": fix})


@app.route("/api/ai/review", methods=["POST"])
def ai_review():
    """AI reviews code quality."""
    data = request.get_json()
    code = data.get("code", "")
    problem_desc = data.get("problem_description", "")
    if not code.strip():
        return jsonify({"error": "No code provided"}), 400
    review = review_code(code, problem_desc)
    return jsonify({"review": review})


# ══════════════════════════════════════════════════════════════
#  QUIZZES
# ══════════════════════════════════════════════════════════════
@app.route("/api/quiz/<topic>", methods=["GET"])
def get_quiz(topic):
    """Generate a quiz on a topic."""
    count = request.args.get("count", 5, type=int)
    questions = generate_quiz(topic, count)
    return jsonify({"topic": topic, "questions": questions})


@app.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    """Submit quiz answers and get score."""
    data = request.get_json()
    user_id = data.get("user_id")
    topic = data.get("topic", "general")
    answers = data.get("answers", [])
    questions = data.get("questions", [])
    time_taken = data.get("time_taken", 0)

    if not questions or not answers:
        return jsonify({"error": "Questions and answers are required"}), 400

    # Grade the quiz
    correct = 0
    results = []
    for i, question in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else -1
        is_correct = user_answer == question.get("correct", -1)
        if is_correct:
            correct += 1
        results.append({
            "question": question["question"],
            "user_answer": user_answer,
            "correct_answer": question["correct"],
            "is_correct": is_correct,
            "explanation": question.get("explanation", ""),
        })

    total = len(questions)
    score_pct = int((correct / max(total, 1)) * 100)

    # Save score if user is logged in
    if user_id:
        save_quiz_score(user_id, topic, correct, total, time_taken)
        xp = correct * 5  # 5 XP per correct answer
        update_user_stats(user_id, xp)

        if correct == total:
            check_and_award_achievements(user_id)

    return jsonify({
        "score": correct,
        "total": total,
        "percentage": score_pct,
        "results": results,
        "xp_earned": correct * 5,
    })


# ══════════════════════════════════════════════════════════════
#  USER DATA
# ══════════════════════════════════════════════════════════════
@app.route("/api/user/<user_id>/stats", methods=["GET"])
def user_stats(user_id):
    """Get user profile and stats."""
    stats = get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "User not found"}), 404
    return jsonify(stats)


@app.route("/api/user/<user_id>/submissions", methods=["GET"])
def user_submissions(user_id):
    """Get user's submission history."""
    limit = request.args.get("limit", 10, type=int)
    submissions = get_user_submissions(user_id, limit)
    return jsonify(submissions)


@app.route("/api/user/<user_id>/achievements", methods=["GET"])
def user_achievements(user_id):
    """Get user's achievements."""
    achievements_data = get_user_achievements(user_id)
    all_achievements = get_achievements()
    earned_ids = {a["achievement_id"] for a in achievements_data}
    return jsonify({
        "earned": achievements_data,
        "all": all_achievements,
        "total_earned": len(achievements_data),
        "total_available": len(all_achievements),
    })


@app.route("/api/user/<user_id>/quiz-scores", methods=["GET"])
def user_quiz_scores(user_id):
    """Get user's quiz history."""
    scores = get_user_quiz_scores(user_id)
    return jsonify(scores)


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    """Get top users by XP."""
    limit = request.args.get("limit", 10, type=int)
    board = get_leaderboard(limit)
    return jsonify(board)


# ══════════════════════════════════════════════════════════════
#  RUN SERVER
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
