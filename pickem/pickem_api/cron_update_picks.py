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

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)

def get_matching_picks(game_id):
    """
    
    """
    url = "http://localhost:8000/api/picks/{}".format(game_id)
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def post_win(pick_id):
    """
    Send PUT to update pick as a win
    """
    headers = {
        "Content-Type": "application/json",
    }

    payload='{"pick_correct": "true"}'

    url = "http://localhost:8000/api/userpicks/{}".format(pick_id)
    x = requests.patch(url, payload, headers = headers)

    if  x.status_code == 200 or x.status_code == 201:
        logger.info(" - Game ID {} sucesfully maked as a win!".format(pick_id))
    else:
        logger.error(" - Issues updating Game ID {}, status code: {}".format(pick_id, x.status_code))

def update_game_as_scored(game_id, game_slug):
    """
    Send POST to update game as scored
    """
    headers = {
        "Content-Type": "application/json",
    }

    payload='{"gameScored": "true"}'

    url = "http://localhost:8000/api/games/{}".format(game_id)
    x = requests.patch(url, payload, headers = headers)

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
        
        for user_pick in entry_pick:
            if user_pick['pick'] == game_winner:
                logger.info("User {} made a correct pick by picking {} in the game {} (game id: {})".format(user_pick['userID'], user_pick['pick'], user_pick['slug'], user_pick['id']))
                post_win(user_pick['id'])
        
        update_game_as_scored(entry['id'], entry['slug'])


def get_unscored_games():
    """
    Get all the unscored games that are completed
    """
    url = "http://localhost:8000/api/unscored"
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def update_picks():
    logger.info("Scheduled Job: Update Unscored Picks")
    games = get_unscored_games()
    update_wins(games)


if __name__ == '__main__':
    update_picks()