#!/usr/bin/env python3

import requests
import json

def get_games():
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
                print(competition['id'])
                print(competition['status']['type']['name'])

    except requests.exceptions.RequestException:
        print(response.text)


def update_games():
    get_games()
        

if __name__ == '__main__':
    update_games()