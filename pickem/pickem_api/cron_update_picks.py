"""
Update Unscored NFL Picks
Jim D'Agostino
Aug 2022
"""
#!/usr/bin/env python3

import requests
import sys
import json
import logging
from datetime import date
import argparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

parser = argparse.ArgumentParser(description='Update User Picks')
parser.add_argument("--url", help="Specify the API url.")
parser.add_argument("--token", help="API authentication token.")
args, leftovers = parser.parse_known_args()


def get_api_headers():
    """Build common headers for API requests, including auth token if provided."""
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = "Token {}".format(args.token)
    return headers

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)

def get_season():
    """
    Fetches the current season from the API endpoint.
    This avoids hardcoding the season in multiple places.
    """
    try:
        # The script now expects a --url argument, which defaults to 'localhost'.
        response = requests.get('http://{}/api/currentseason/'.format(args.url))
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()['current_season']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching current season from API: {e}. Using fallback logic.")
        
        # Fallback to YYZZ date format logic. The season year changes in April.
        today = date.today()
        if today.month < 4:
            season_start_year = today.year - 1
        else:
            season_start_year = today.year
        
        season_end_year = season_start_year + 1
        fallback_season = f"{str(season_start_year)[-2:]}{str(season_end_year)[-2:]}"
        print(f"Fallback season is: {fallback_season}")
        return fallback_season

def get_matching_picks(game_id):
    """
    
    """
    url = "http://{}/api/picks/{}".format(args.url, game_id)
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def post_win(pick_id):
    """
    Send PUT to update pick as a win
    """
    headers = get_api_headers()

    payload='{"pick_correct": "true"}'

    url = "http://{}/api/userpicks/{}".format(args.url, pick_id)
    x = requests.patch(url, payload, headers=headers)

    if  x.status_code == 200 or x.status_code == 201:
        logger.info(" - Game ID {} sucesfully maked as a win!".format(pick_id))
    else:
        logger.error(" - Issues updating Game ID {}, status code: {}".format(pick_id, x.status_code))

def update_game_as_scored(game_id, game_slug):
    """
    Send POST to update game as scored
    """
    headers = get_api_headers()

    payload='{"gameScored": "true"}'

    url = "http://{}/api/games/{}".format(args.url, game_id)
    x = requests.patch(url, payload, headers=headers)

    if  x.status_code == 200 or x.status_code == 201:
        logger.info("Game slug {} sucesfully updated game as scored".format(game_slug))
    else:
        logger.error("Issues updating Game {}, status code: {}".format(game_id, x.status_code))


def update_wins(payload):
    """
    
    """
    logger.info("Cheking all games for a win")
    for entry in payload:
        entry_pick = get_matching_picks(entry['id'])

        game_winner = entry['gameWinner']

        if game_winner:        
            for user_pick in entry_pick:
                if user_pick['pick'] == game_winner:
                    logger.info("User {} made a correct pick by picking {} in the game {} (game id: {})".format(user_pick['userID'], user_pick['pick'], user_pick['slug'], user_pick['id']))
                    post_win(user_pick['id'])
            
            update_game_as_scored(entry['id'], entry['slug'])
        else: 
            logger.warning("Game {} finished, but missing an winner. Please try again later.".format(entry['slug']))


def get_unscored_games():
    """
    Get all the unscored games that are completed
    """
    url = "http://{}/api/unscored".format(args.url)
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def update_picks():
    logger.info("Scheduled Job: Update Unscored Picks")
    games = get_unscored_games()
    update_wins(games)


if __name__ == '__main__':
    update_picks()