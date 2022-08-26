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
import datetime
from datetime import date
import argparse

parser = argparse.ArgumentParser(description='Populate/Update NFL Games.')
parser.add_argument("--gamedate", help="Specify the date to update.")
args, leftovers = parser.parse_known_args()
    

def check_game_id(id):
    """
    Check if game ID has already been added.
    """
    url = "http://localhost:8000/api/games/{}".format(id)

    headers = {
        "Content-Type": "application/json",
    }

    x = requests.get(url, headers = headers)
    if  x.status_code == 200:
        return True
    else:
        return False


def get_game_week(game_date):
    """
    Check week number for a date
    """
    url = "http://localhost:8000/api/weeks/{}".format(game_date)

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("GET", url, headers=headers)
    json_response = json.loads(response.text)
    return json_response['weekNumber']


def add_games(payload, id):
    """
    Send POST/PUT to API to add game
    """
    headers = {
        "Content-Type": "application/json",
    }

    if check_game_id(id): 
        url = "http://localhost:8000/api/games/{}".format(id)
        x = requests.put(url, data = payload, headers = headers)
        verb = "Updated"
    else:
        url = "http://localhost:8000/api/games/"
        x = requests.post(url, data = payload, headers = headers)
        verb = "Added"
    
    if  x.status_code == 200 or x.status_code == 201:
        print("- Game sucesfully %s" % verb)
        print(payload)
    else:
        print('- Issue adding game, please review')
        print(payload)
    print('\n')


def build_payload(payload):
    """
    Read in game data and build payload to send to API.
    """
    for entry in payload:
        regex = r"\s*nfl\s*"
        sport = entry['competition']['slug']
        
        if re.match(regex, sport):
            gameId = entry['id']
            slug = entry['slug']
            competition = entry['competition']['slug']
            startTimestamp = datetime.datetime.fromtimestamp(entry['startTimestamp'])
            startDate = datetime.date.fromtimestamp(entry['startTimestamp'])
            gameWeek = get_game_week(startDate)
            gameYear = "2022"
            if "winner" in entry:
                if entry['winner'] == 1:
                    gameWinner = entry['homeTeam']['slug']
                elif entry['winner'] == 2:
                    gameWinner = entry['awayTeam']['slug']
            else:
                gameWinner = 0
            statusType = entry['status']['type']
            statusTitle = entry['status']['title']
            homeTeamId = entry['homeTeam']['id']
            homeTeamSlug = entry['homeTeam']['slug']
            homeTeamName = entry['homeTeam']['name']
            if statusType == 'notstarted':
                homeTeamScore = 0
            else: 
                homeTeamScore = entry['homeScore']['current']
            awayTeamId = entry['awayTeam']['id']
            awayTeamSlug = entry['awayTeam']['slug']
            awayTeamName = entry['awayTeam']['name']
            if statusType == 'notstarted':
                awayTeamScore = 0
            else: 
                awayTeamScore = entry['awayScore']['current']

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
            json_string = json.dumps(payload, default=str)
            add_games(json_string, gameId)


def get_games(api_key, game_date):
    """
    Get all the game data from viperscore APIs
    """
    url = "https://viperscore.p.rapidapi.com/games/scheduled/date"

    querystring = {"sport":"american-football","date":"{}".format(game_date)}

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

    if args.gamedate is not None:
        get_games(api_key, args.gamedate)
    else:
        today = date.today()
        game_date = today.strftime("%Y-%m-%d")
        get_games(api_key, game_date)

if __name__ == '__main__':
    main()