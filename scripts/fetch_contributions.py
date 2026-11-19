#!/usr/bin/env python3
"""
Fetch GitHub contribution data for the profile.
Uses GitHub GraphQL API to get contributions, streaks, and repo data.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "contributions.json"

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
USERNAME = "Jani-shiv"

CONTRIBUTIONS_QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          name
          url
          stargazerCount
          forkCount
          primaryLanguage {
            name
            color
          }
        }
        contributions {
          totalCount
        }
      }
    }
  }
}
"""

REPOS_QUERY = """
query($username: String!) {
  user(login: $username) {
    repositories(first: 20, orderBy: {field: STARGAZERS, direction: DESC}, ownerAffiliations: OWNER) {
      nodes {
        name
        description
        stargazerCount
        forkCount
        primaryLanguage {
          name
          color
        }
        url
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def run_query(query: str, variables: dict) -> dict:
    token = os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN environment variable not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.post(GITHUB_GRAPHQL_URL, headers=headers, json={"query": query, "variables": variables})
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    return data["data"]

def compute_streaks(weeks: list) -> tuple[int, int]:
    """Compute current and longest streaks from weeks data."""
    days = []
    for week in weeks:
        for day in week.get("contributionDays", []):
            days.append({"date": day["date"], "count": day["contributionCount"]})

    days.sort(key=lambda x: x["date"])

    current_streak = 0
    longest_streak = 0
    temp_streak = 0

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    last_contrib_date = None
    for day in days:
        if day["count"] > 0:
            last_contrib_date = day["date"]

    if last_contrib_date:
        last_date = datetime.fromisoformat(last_contrib_date).date()
        if last_date >= yesterday:
            current_streak = 1

    for i, day in enumerate(days):
        if day["count"] > 0:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 0

    return current_streak, longest_streak

def compute_monthly(weeks: list) -> list:
    """Aggregate contributions by month."""
    from collections import defaultdict

    monthly = defaultdict(int)
    for week in weeks:
        for day in week.get("contributionDays", []):
            date = day["date"]
            count = day["contributionCount"]
            dt = datetime.fromisoformat(date)
            month_key = dt.strftime("%b")
            monthly[month_key] += count

    result = []
    today = datetime.now()
    for i in range(11, -1, -1):
        dt = today - timedelta(days=i * 30)
        month_key = dt.strftime("%b")
        if month_key in monthly:
            result.append({"month": month_key, "count": monthly[month_key]})

    return result

def compute_active_days(weeks: list) -> int:
    """Count days with contributions > 0."""
    active = 0
    for week in weeks:
        for day in week.get("contributionDays", []):
            if day["contributionCount"] > 0:
                active += 1
    return active

def find_busiest_day(weeks: list) -> dict:
    """Find the day with the most contributions."""
    max_count = 0
    busiest_date = ""
    for week in weeks:
        for day in week.get("contributionDays", []):
            if day["contributionCount"] > max_count:
                max_count = day["contributionCount"]
                busiest_date = day["date"]
    return {"date": busiest_date, "count": max_count}

def main() -> int:
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365)

    variables = {
        "username": USERNAME,
        "from": from_date.isoformat() + "Z",
        "to": to_date.isoformat() + "Z",
    }

    print(f"Fetching contributions for {USERNAME}...")
    data = run_query(CONTRIBUTIONS_QUERY, variables)

    user = data["user"]
    if not user:
        print(f"User {USERNAME} not found")
        return 1

    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    weeks = calendar["weeks"]

    print("Fetching repositories...")
    repos_data = run_query(REPOS_QUERY, {"username": USERNAME})
    repos = repos_data["user"]["repositories"]["nodes"]

    featured_repos = []
    for repo in repos[:6]:
        lang = repo.get("primaryLanguage")
        featured_repos.append({
            "name": repo["name"],
            "description": repo["description"] or "No description",
            "stargazers_count": repo["stargazerCount"],
            "forks_count": repo["forkCount"],
            "language": lang["name"] if lang else "",
            "language_color": lang["color"] if lang else "#FF6B35",
            "html_url": repo["url"],
        })

    current_streak, longest_streak = compute_streaks(weeks)
    active_days = compute_active_days(weeks)
    busiest_day = find_busiest_day(weeks)
    monthly = compute_monthly(weeks)

    total_contributions = calendar["totalContributions"]

    output = {
        "username": USERNAME,
        "total_contributions": total_contributions,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "active_days": active_days,
        "busiest_day": busiest_day,
        "monthly": monthly,
        "weeks": weeks,
        "repos": [],
        "featured_repos": featured_repos,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    DATA_FILE.write_text(json.dumps(output, indent=2))
    print(f"Written to {DATA_FILE}")
    print(f"Total contributions: {total_contributions}")
    print(f"Current streak: {current_streak} days")
    print(f"Longest streak: {longest_streak} days")
    print(f"Active days: {active_days}")
    print(f"Busiest day: {busiest_day}")
    print(f"Featured repos: {len(featured_repos)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())