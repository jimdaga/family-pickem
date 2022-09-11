#!/usr/bin/env python3

import requests
import json

def get_active_games():
    """
    Get all the game data from ESPN APIs
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

    querystring = {"dates":"20220908-20220912","limit":"200"}

    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        json_response = json.loads(response.text)
        for event in json_response["events"]:
            for competition in event["competitions"]:
                status=competition['status']['type']['name']
                status_list = ['STATUS_HALFTIME', 'STATUS_END_PERIOD', 'STATUS_IN_PROGRESS']
                if status in status_list:
                    return True
                else:
                    return False
    except requests.exceptions.RequestException:
        print(response.text)


def update_games():
    get_games()
        

if __name__ == '__main__':
    update_games()