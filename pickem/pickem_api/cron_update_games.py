"""
Get NFL Games 
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
import time 
import argparse

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)

parser = argparse.ArgumentParser(description='Populate/Update NFL Games.')
parser.add_argument("--gamedate", help="Specify the date to update.")
args, leftovers = parser.parse_known_args()

def get_season():
    # I'll probably hate myself in the future for hardcoding this :) 
    today = date.today()
    today_datestamp = date(today.year, today.month, today.day)

    if today_datestamp > date(2022, 4, 1) and today_datestamp < date(2023, 4, 1):
        return '2223'
    elif today_datestamp > date(2023, 4, 1) and today_datestamp < date(2024, 4, 1):
        return '2324'
    elif today_datestamp > date(2024, 4, 1):
        return '2425'

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

def get_active_games():
    """
    Check for active games
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
        logger.info("- Game sucesfully %s" % verb)
        logger.info(payload)
    else:
        logger.error('- Issue adding game, please review')
        logger.error(payload)


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
            weekday = time.strftime('%a', time.localtime(entry['startTimestamp']))
            if weekday  == 'Mon':
                tieBreakerGame = True
            else:
                tieBreakerGame = False
            gameWeek = get_game_week(startDate)
            gameYear = "2024"
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
                homeTeamPeriod1 = 0
                homeTeamPeriod2 = 0
                homeTeamPeriod3 = 0
                homeTeamPeriod4 = 0
            else: 
                homeTeamScore = entry['homeScore']['current']
                try:
                    homeTeamPeriod1 = entry['homeScore']['period1']
                except KeyError:
                    homeTeamPeriod1 = None
                try:
                    homeTeamPeriod2 = entry['homeScore']['period2']
                except KeyError:
                    homeTeamPeriod2 = None
                try:
                    homeTeamPeriod3 = entry['homeScore']['period3']
                except KeyError:
                    homeTeamPeriod3 = None
                try:
                    homeTeamPeriod4 = entry['homeScore']['period4']
                except KeyError:
                    homeTeamPeriod4 = None
             
            awayTeamId = entry['awayTeam']['id']
            awayTeamSlug = entry['awayTeam']['slug']
            awayTeamName = entry['awayTeam']['name']
            if statusType == 'notstarted':
                awayTeamScore = 0
                awayTeamPeriod1 = 0
                awayTeamPeriod2 = 0
                awayTeamPeriod3 = 0
                awayTeamPeriod4 = 0
            else: 
                awayTeamScore = entry['awayScore']['current']
                try:
                    awayTeamPeriod1 = entry['awayScore']['period1']
                except KeyError:
                    awayTeamPeriod1 = None
                try:
                    awayTeamPeriod2 = entry['awayScore']['period2']
                except KeyError:
                    awayTeamPeriod2 = None
                try:
                    awayTeamPeriod3 = entry['awayScore']['period3']
                except KeyError:
                    awayTeamPeriod3 = None
                try:
                    awayTeamPeriod4 = entry['awayScore']['period4']
                except KeyError:
                    awayTeamPeriod4 = None
            payload = {
                "id": gameId,
                "slug": slug,
                "competition": competition,
                "gameWeek": gameWeek,
                "gameyear": gameYear,
                "startTimestamp": startTimestamp,
                "tieBreakerGame": tieBreakerGame,
                "gameWinner": gameWinner,
                "statusType": statusType,
                "statusTitle": statusTitle,
                "homeTeamId": homeTeamId,
                "homeTeamSlug": homeTeamSlug,
                "homeTeamName": homeTeamName,
                "homeTeamScore": homeTeamScore,
                "homeTeamPeriod1": homeTeamPeriod1,
                "homeTeamPeriod2": homeTeamPeriod2,
                "homeTeamPeriod3": homeTeamPeriod3,
                "homeTeamPeriod4": homeTeamPeriod4,
                "awayTeamId": awayTeamId,
                "awayTeamSlug": awayTeamSlug,
                "awayTeamName": awayTeamName,
                "awayTeamScore": awayTeamScore,
                "awayTeamPeriod1": awayTeamPeriod1,
                "awayTeamPeriod2": awayTeamPeriod2,
                "awayTeamPeriod3": awayTeamPeriod3,
                "awayTeamPeriod4": awayTeamPeriod4

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
    
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        json_response = json.loads(response.text)
        build_payload(json_response)
    except requests.exceptions.RequestException:
        logger.error(response.text)


def update_games():
    logger.info("Scheduled Job: Update NFL Games")
    try:
        os.environ["X_RAPIDAPI_KEY"]
    except KeyError:
        logger.error("You must set an environment variable \"X_RAPIDAPI_KEY\" with the value of your API Key")
        sys.exit(1)
    api_key = os.getenv('X_RAPIDAPI_KEY')

    if args.gamedate is not None:
        get_games(api_key, args.gamedate)
    else:
        today = date.today()
        game_date = today.strftime("%Y-%m-%d")
        if get_active_games():
            logger.info('Updating active games')
            get_games(api_key, game_date)
        else:
            logger.info("There are no active games right now")
        

if __name__ == '__main__':
    update_games()