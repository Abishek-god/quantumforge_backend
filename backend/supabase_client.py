"""
Quantum Forge — Supabase Client
Database operations for problems, submissions, profiles, and achievements.
"""

import os
from supabase import create_client, Client
from datetime import date, timedelta

# ── Initialize Supabase Client ──────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Problems ────────────────────────────────────────────────
def get_problems(difficulty=None, category=None):
    """Fetch all problems, optionally filtered by difficulty or category."""
    query = supabase.table("problems").select("id, title, difficulty, category, xp_reward")
    if difficulty:
        query = query.eq("difficulty", difficulty)
    if category:
        query = query.eq("category", category)
    result = query.order("id").execute()
    return result.data


def get_problem_by_id(problem_id):
    """Fetch a single problem with all details including test cases."""
    result = (
        supabase.table("problems")
        .select("*")
        .eq("id", problem_id)
        .single()
        .execute()
    )
    return result.data


# ── Daily Challenge ─────────────────────────────────────────
def get_daily_challenge():
    """Get today's daily challenge. If none exists, pick a random problem."""
    today = date.today().isoformat()
    result = (
        supabase.table("daily_challenges")
        .select("*, problems(*)")
        .eq("challenge_date", today)
        .execute()
    )
    if result.data:
        return result.data[0]

    # No challenge for today — pick a random problem
    problems = supabase.table("problems").select("id").execute()
    if not problems.data:
        return None

    import random
    random_problem = random.choice(problems.data)

    # Insert today's challenge
    supabase.table("daily_challenges").insert({
        "challenge_date": today,
        "problem_id": random_problem["id"]
    }).execute()

    # Fetch with full problem data
    result = (
        supabase.table("daily_challenges")
        .select("*, problems(*)")
        .eq("challenge_date", today)
        .execute()
    )
    return result.data[0] if result.data else None


# ── Submissions ─────────────────────────────────────────────
def save_submission(user_id, problem_id, code, passed, score, execution_time=0):
    """Save a user's code submission."""
    result = supabase.table("submissions").insert({
        "user_id": user_id,
        "problem_id": problem_id,
        "code": code,
        "passed": passed,
        "score": score,
        "execution_time": execution_time
    }).execute()
    return result.data


def get_user_submissions(user_id, limit=10):
    """Fetch a user's recent submissions."""
    result = (
        supabase.table("submissions")
        .select("*, problems(title, difficulty)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


# ── User Profiles & Stats ──────────────────────────────────
def get_user_stats(user_id):
    """Get a user's profile with stats."""
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    return result.data


def update_user_stats(user_id, xp_gained, problem_solved=False):
    """Update user XP, streak, and problems_solved count."""
    profile = get_user_stats(user_id)
    if not profile:
        return None

    today = date.today()
    last_active = profile.get("last_active")
    current_streak = profile.get("streak", 0)
    longest_streak = profile.get("longest_streak", 0)

    # Calculate streak
    if last_active:
        last_active_date = date.fromisoformat(str(last_active))
        if last_active_date == today - timedelta(days=1):
            current_streak += 1
        elif last_active_date != today:
            current_streak = 1
    else:
        current_streak = 1

    longest_streak = max(longest_streak, current_streak)

    # Determine rank based on XP
    new_xp = profile.get("xp", 0) + xp_gained
    rank = calculate_rank(new_xp)

    update_data = {
        "xp": new_xp,
        "streak": current_streak,
        "longest_streak": longest_streak,
        "last_active": today.isoformat(),
        "rank": rank,
    }

    if problem_solved:
        update_data["problems_solved"] = profile.get("problems_solved", 0) + 1

    result = (
        supabase.table("profiles")
        .update(update_data)
        .eq("id", user_id)
        .execute()
    )
    return result.data


def calculate_rank(xp):
    """Determine user rank based on XP."""
    if xp >= 1000:
        return "Grandmaster"
    elif xp >= 500:
        return "Expert"
    elif xp >= 250:
        return "Advanced"
    elif xp >= 100:
        return "Intermediate"
    elif xp >= 25:
        return "Novice"
    return "Beginner"


# ── Achievements ────────────────────────────────────────────
def get_achievements():
    """Get all available achievements."""
    result = supabase.table("achievements").select("*").execute()
    return result.data


def get_user_achievements(user_id):
    """Get achievements earned by a user."""
    result = (
        supabase.table("user_achievements")
        .select("*, achievements(*)")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data


def check_and_award_achievements(user_id):
    """Check if user qualifies for new achievements and award them."""
    profile = get_user_stats(user_id)
    if not profile:
        return []

    all_achievements = get_achievements()
    user_achievements = get_user_achievements(user_id)
    earned_ids = {ua["achievement_id"] for ua in user_achievements}

    newly_earned = []
    for ach in all_achievements:
        if ach["id"] in earned_ids:
            continue

        qualified = False
        ctype = ach["condition_type"]
        cval = ach["condition_value"]

        if ctype == "problems_solved" and profile.get("problems_solved", 0) >= cval:
            qualified = True
        elif ctype == "streak" and profile.get("streak", 0) >= cval:
            qualified = True
        elif ctype == "xp" and profile.get("xp", 0) >= cval:
            qualified = True

        if qualified:
            supabase.table("user_achievements").insert({
                "user_id": user_id,
                "achievement_id": ach["id"]
            }).execute()
            newly_earned.append(ach)

    return newly_earned


# ── Leaderboard ─────────────────────────────────────────────
def get_leaderboard(limit=10):
    """Get top users by XP."""
    result = (
        supabase.table("profiles")
        .select("username, xp, rank, problems_solved, streak")
        .order("xp", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


# ── Quiz Scores ─────────────────────────────────────────────
def save_quiz_score(user_id, topic, score, total, time_taken=0):
    """Save a quiz result."""
    result = supabase.table("quiz_scores").insert({
        "user_id": user_id,
        "topic": topic,
        "score": score,
        "total": total,
        "time_taken": time_taken
    }).execute()
    return result.data


def get_user_quiz_scores(user_id):
    """Get a user's quiz history."""
    result = (
        supabase.table("quiz_scores")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data
