"""
Update Unscored NFL Picks
Jim D'Agostino
Aug 2022
"""
#!/usr/bin/env python3

import requests
import sys
import os
import json
import re
import datetime
from datetime import date

def update_wins(payload):
    for entry in payload:
        entry_pick = get_matching_picks(entry['id'])
        game_winner = entry['gameWinner']
        for user_pick in entry_pick:
            if user_pick['pick'] == game_winner:
                print("User {} made a correct pick by picking {} in the game {} (game id: {})".format(user_pick['userID'], user_pick['pick'], user_pick['slug'], user_pick['id']))


def get_matching_picks(game_id):
    url = "http://localhost:8000/api/picks/{}".format(game_id)
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def get_unscored_games():
    """
    Get all the unscored games that are completed
    """
    url = "http://localhost:8000/api/unscored"
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    return json_response


def update_picks():
    print("Scheduled Job: Update Unscored Picks")
    get_unscored_games()

if __name__ == '__main__':
     update_wins(get_unscored_games())