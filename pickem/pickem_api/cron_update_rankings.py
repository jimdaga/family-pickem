#!/usr/bin/env python3

"""
Calculate and update user rankings in the standings.

This script:
1. Fetches all users in the current season
2. Calculates rankings based on total_points
3. Handles ties (users with same points get same rank)
4. Stores the rank in the current_rank field

This should be run after cron_update_standings.py to ensure
rankings reflect the latest point totals.
"""

import os
import sys
import django
import argparse

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pickem.settings')
django.setup()

from pickem_api.models import userSeasonPoints
from pickem.utils import get_season


def calculate_rankings(gameseason):
    """
    Calculate rankings for all users in a season, handling ties.

    Users are ranked by total_points (descending).
    Users with the same points receive the same rank.

    Example:
        User A: 100 points -> Rank 1
        User B: 100 points -> Rank 1 (tie)
        User C: 95 points  -> Rank 3 (not 2, because two users tied for 1st)
        User D: 90 points  -> Rank 4

    Args:
        gameseason (int): The season to calculate rankings for
    """
    print(f"Calculating rankings for season {gameseason}...")

    # Get all users for this season, ordered by points (descending)
    users = userSeasonPoints.objects.filter(
        gameseason=gameseason
    ).order_by('-total_points', 'userEmail')  # Secondary sort by email for consistency

    if not users.exists():
        print(f"  No users found for season {gameseason}")
        return

    # Calculate ranks with tie handling
    current_rank = 1
    previous_points = None
    users_at_current_rank = 0

    for user in users:
        points = user.total_points or 0  # Treat None as 0

        if previous_points is not None and points < previous_points:
            # Points changed, so advance rank by number of users at previous rank
            current_rank += users_at_current_rank
            users_at_current_rank = 0

        # Assign rank
        user.current_rank = current_rank
        user.save(update_fields=['current_rank'])

        users_at_current_rank += 1
        previous_points = points

        print(f"  {user.userEmail}: {points} points -> Rank {current_rank}")

    print(f"✓ Rankings calculated for {users.count()} users")


def update_rankings(url=None):
    """
    Update rankings for the current season.

    Args:
        url: Optional URL parameter for compatibility with cron.sh (not used in this script)
    """
    print("=" * 60)
    print("Update User Rankings")
    print("=" * 60)

    # Get current season
    try:
        gameseason = get_season()
        print(f"Current season: {gameseason}")
    except Exception as e:
        print(f"Error getting current season: {e}")
        return

    # Calculate rankings
    calculate_rankings(gameseason)

    print("=" * 60)
    print("Rankings update complete!")
    print("=" * 60)


if __name__ == '__main__':
    # Parse command line arguments for compatibility with cron.sh
    parser = argparse.ArgumentParser(description='Update user rankings in the standings')
    parser.add_argument('--url', type=str, help='API URL (for compatibility with cron.sh)')

    args = parser.parse_args()
    update_rankings(url=args.url)
