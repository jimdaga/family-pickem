from datetime import date, datetime, time
import pytz
from pickem_api.models import currentSeason

def get_season(display_name=False):
    """Get the current season from the database
    
    Args:
        display_name (bool): If True, return the user-friendly display name instead of the season number
    
    Returns:
        int or str: Season number (int) or display name (str) depending on display_name parameter
    """
    try:
        season_obj = currentSeason.objects.first()
        if display_name:
            return season_obj.get_display_season()
        return season_obj.season
    except (currentSeason.DoesNotExist, AttributeError):
        if display_name:
            return "2024-2025"  # Default display season if none found
        return 2024  # Default season if none found

def get_sunday_1pm_est_cutoff(week_games):
    """
    Calculate the Sunday 1PM EST cutoff for the given week's games.
    
    Args:
        week_games: QuerySet of GamesAndScores for a specific week
    
    Returns:
        datetime: Sunday 1PM EST cutoff time, or None if no Sunday games found
    """
    est = pytz.timezone('US/Eastern')
    
    # Find Sunday games in the week
    sunday_games = []
    for game in week_games:
        game_time_est = game.startTimestamp.astimezone(est)
        if game_time_est.weekday() == 6:  # Sunday is weekday 6
            sunday_games.append(game_time_est)
    
    if not sunday_games:
        return None
    
    # Find the Sunday of this week's games
    sunday_date = min(sunday_games).date()
    
    # Create Sunday 1PM EST datetime
    sunday_1pm_est = est.localize(datetime.combine(sunday_date, time(13, 0)))  # 1:00 PM
    
    return sunday_1pm_est

def is_pick_locked(game, week_games=None):
    """
    Determine if picks are locked for a specific game based on the new rules:
    - If the game is before Sunday at 1PM EST: picks lock when the game starts
    - If the game is after Sunday at 1PM EST: picks are locked for all other games at Sunday 1PM EST
    
    Args:
        game: GamesAndScores object
        week_games: QuerySet of all games in the same week (optional, will query if not provided)
    
    Returns:
        tuple: (is_locked: bool, lock_reason: str)
    """
    from pickem_api.models import GamesAndScores
    
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est)
    
    # If the game has already started or finished, it's locked
    if game.statusType != 'notstarted':
        return True, "Game has already started"
    
    # Get all games in the same week if not provided
    if week_games is None:
        week_games = GamesAndScores.objects.filter(
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            competition=game.competition
        )
    
    # Get Sunday 1PM EST cutoff for this week
    sunday_1pm_cutoff = get_sunday_1pm_est_cutoff(week_games)
    
    if sunday_1pm_cutoff is None:
        # No Sunday games found, fall back to individual game start times
        game_start_est = game.startTimestamp.astimezone(est)
        if now_est >= game_start_est:
            return True, "Game has started"
        return False, "Game not started yet"
    
    # Convert game start time to EST
    game_start_est = game.startTimestamp.astimezone(est)
    
    # Rule 1: If the game is before Sunday at 1PM EST, picks lock when the game starts
    if game_start_est < sunday_1pm_cutoff:
        if now_est >= game_start_est:
            return True, "Game has started"
        return False, "Game not started yet"
    
    # Rule 2: If the game is after Sunday at 1PM EST, picks are locked at Sunday 1PM EST
    else:
        if now_est >= sunday_1pm_cutoff:
            return True, "Late game picks locked at Sunday 1PM EST"
        return False, "Before Sunday 1PM EST cutoff"

def are_picks_locked_for_week(week_games):
    """
    Check if any picks are locked for the week based on the new rules.
    
    Args:
        week_games: QuerySet of GamesAndScores for a specific week
    
    Returns:
        dict: {
            'any_locked': bool,
            'sunday_cutoff_passed': bool,
            'sunday_cutoff_time': datetime or None,
            'individual_locks': dict of game_id -> (is_locked, reason)
        }
    """
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est)
    
    sunday_1pm_cutoff = get_sunday_1pm_est_cutoff(week_games)
    sunday_cutoff_passed = sunday_1pm_cutoff and now_est >= sunday_1pm_cutoff
    
    individual_locks = {}
    any_locked = False
    
    for game in week_games:
        is_locked, reason = is_pick_locked(game, week_games)
        individual_locks[game.id] = (is_locked, reason)
        if is_locked:
            any_locked = True
    
    return {
        'any_locked': any_locked,
        'sunday_cutoff_passed': sunday_cutoff_passed,
        'sunday_cutoff_time': sunday_1pm_cutoff,
        'individual_locks': individual_locks
    }