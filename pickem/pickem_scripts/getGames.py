#!/usr/bin/env python3
"""
Get NFL Games 
Jim D'Agostino
Aug 2022
"""

import requests
import sys
import os
import json
import re

def add_games(payload):
    # Send POST to API to add game
    url = "http://localhost:8000/api/games/add/"

    headers = {
        "Content-Type": "application/json",
    }

    x = requests.post(url, data = payload, headers = headers)
    if  x.status_code == requests.codes.ok:
        print('- Game sucesfully Added')
        print(payload)

    else:
        print('- Issue adding game, please review')
        print(payload)
        print(x.json())

def build_payload(payload):
    for entry in payload:
        regex = r"\s*nfl.\s*"
        sport = entry['competition']['slug']
        
        if re.match(regex, sport):
            gameId = entry['id']
            slug = entry['slug']
            competition = entry['competition']['slug']
            gameWeek = "1"
            gameYear = "2022"
            # startTimestamp = entry['startTimestamp']
            startTimestamp = "2022-08-20T03:33:58Z"
            if "winner" in entry:
                gameWinner = entry['winner']
            else:
                gameWinner = 0
            statusType = entry['status']['type']
            statusTitle = entry['status']['title']
            homeTeamId = entry['homeTeam']['id']
            homeTeamSlug = entry['homeTeam']['slug']
            homeTeamName = entry['homeTeam']['name']
            if "current" in entry:
                homeTeamScore = entry['homeScore']['current']
            else: 
                homeTeamScore = 0
            awayTeamId = entry['awayTeam']['id']
            awayTeamSlug = entry['awayTeam']['slug']
            awayTeamName = entry['awayTeam']['name']
            if "current" in entry:
                awayTeamScore = entry['awayScore']['current']
            else:
                awayTeamScore = 0

            payload = {
                "id": gameId,
                "slug": slug,
                "competition": competition,
                "gameWeek": gameWeek,
                "gameyear": gameYear,
                "startTimestamp": startTimestamp,
                "gameWinner": gameWinner,
                "statusType": statusType,
                "statusTitle": statusTitle,
                "homeTeamId": homeTeamId,
                "homeTeamSlug": homeTeamSlug,
                "homeTeamName": homeTeamName,
                "homeTeamScore": homeTeamScore,
                "awayTeamId": awayTeamId,
                "awayTeamSlug": awayTeamSlug,
                "awayTeamName": awayTeamName,
                "awayTeamScore": awayTeamScore,
            }
            json_string = json.dumps(payload) 
            add_games(json_string)

def get_games(api_key):
    url = "https://viperscore.p.rapidapi.com/games/scheduled/date"

    querystring = {"sport":"american-football","date":"2022-08-16"}

    headers = {
        "X-RapidAPI-Key": "%s" % api_key,
        "X-RapidAPI-Host": "viperscore.p.rapidapi.com"
    }
    
    response = requests.request("GET", url, headers=headers, params=querystring)
    json_response = json.loads(response.text)
    build_payload(json_response)


def main():
    print()
    print("#############################################")
    print("Get NFL Games                                ")
    print("#############################################")
    print()
    try:
        os.environ["X_RAPIDAPI_KEY"]
    except KeyError:
        print("You must set an environment variable \"X_RAPIDAPI_KEY\" with the value of your API Key")
        sys.exit(1)
    api_key = os.getenv('X_RAPIDAPI_KEY')

    get_games(api_key)

if __name__ == '__main__':
    main()