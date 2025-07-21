#!/usr/bin/env python3

import requests
import json
from datetime import date
import argparse
import os
import requests
from datetime import date
from espn_api.football import League


parser = argparse.ArgumentParser(description='Populate/Update NFL Games.')
parser.add_argument('--url', default='localhost', help='The host for the API endpoint (e.g., localhost or a domain name)')
parser.add_argument("--gameweek", help="Specify the week to update.")
args, leftovers = parser.parse_known_args()


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
        return 2526


def check_game_id(id):
    """
    Check if game ID has already been added.
    """
    url = "http://{}/api/games/{}".format(args.url, id)

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
    try:
        url = "http://{}/api/weeks/{}".format(args.url, game_date)

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.request("GET", url, headers=headers)
        json_response = json.loads(response.text)
        return json_response['weekNumber']
    except:
        return "1"


def get_team_slug(team_id):
    """
    
    """
    url = "http://{}/api/teams/id/{}".format(args.url, team_id)

    headers = {
        "Content-Type": "application/json",
    }

    x = requests.get(url, headers = headers)
    if  x.status_code == 200:
        json_response = json.loads(x.text)
        return json_response[0]['teamNameSlug']
    else:
        return False
        

def add_games(payload, id):
    """
    Send POST/PUT to API to add game
    """
    headers = {
        "Content-Type": "application/json",
    }

    if check_game_id(id): 
        url = "http://{}/api/games/{}".format(args.url, id)
        x = requests.put(url, data = payload, headers = headers)
        verb = "Updated"
    else:
        url = "http://{}/api/games/".format(args.url)
        x = requests.post(url, data = payload, headers = headers)
        verb = "Added"
    
    if  x.status_code == 200 or x.status_code == 201:
        print("- Game sucesfully %s" % verb)
        print(payload)
    else:
        print('- Issue adding game, please review')
        print(payload)


def build_payload(week):
    """
    Get all the game data from ESPN APIs
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

    game_year = "2025"
    querystring = {"week": week, "dates": game_year}

    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        response.raise_for_status()
        json_response = json.loads(response.text)    

        game_competition = "nfl"
        game_season = get_season()
        game_week = json_response['week']['number']

        for event in json_response["events"]:
            print("###################################################")
            
            for competition in event["competitions"]:
                game_id = competition['id']       
                game_start_timestamp = competition['date']

                # (STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_HALFTIME, STATUS_FINAL)
                if competition['status']['type']['name'] == "STATUS_SCHEDULED":
                    game_status_type = "notstarted"
                elif competition['status']['type']['name'] == "STATUS_IN_PROGRESS":
                    game_status_type = "inprogress"
                elif competition['status']['type']['name'] == "STATUS_END_PERIOD":
                    game_status_type = "inprogress"  
                elif competition['status']['type']['name'] == "STATUS_HALFTIME":
                    game_status_type = "inprogress"
                elif competition['status']['type']['name'] == "STATUS_FINAL":
                    game_status_type = "finished"
                else:
                    game_status_type = competition['status']['type']['name']

                if game_status_type == "inprogress":
                    game_status_title = competition['status']['type']['detail'] # "4:26 - 2nd Quarter",
                else:
                    game_status_title = competition['status']['type']['description'] # (Scheduled, In Progress, Halftime, Final)

                for competitor in competition["competitors"]:
                    if competitor['homeAway'] == "home":
                        home_team_id = competitor['id'] # HomeTeamId (4287)
                        home_team_slug = get_team_slug(competitor['id']) # HomeTeamSlug (miami-dolphins)                                          
                        home_team_name = competitor['team']['displayName']  # HomeTeamName (Miami Dolphins)
                        try:
                            home_team_winner = competitor['winner']
                        except KeyError:
                            home_team_winner = False

                        home_team_score = competitor['score']

                        try: 
                            home_team_score_1 = int(competitor['linescores'][0]['value'])
                        except (KeyError, IndexError):
                            home_team_score_1 = None
                        try:
                            home_team_score_2 = int(competitor['linescores'][1]['value'])
                        except (KeyError, IndexError):
                            home_team_score_2 = None
                        try:
                            home_team_score_3 = int(competitor['linescores'][2]['value'])
                        except (KeyError, IndexError):
                            home_team_score_3 = None
                        try: 
                            home_team_score_4 = int(competitor['linescores'][3]['value'])
                        except (KeyError, IndexError):
                            home_team_score_4 = None
                        try:
                            home_team_score_ot = int(competitor['linescores'][4]['value'])
                        except (KeyError, IndexError):
                            home_team_score_ot = None

                    elif competitor['homeAway'] == "away":
                        away_team_id = competitor['id'] # AwayTeamId (4426)
                        away_team_slug = get_team_slug(competitor['id']) # AwayTeamSlug (new-england-patriots)
                        away_team_name = competitor['team']['displayName'] # AwayTeamName (New England Patriots)
                        try:
                            away_team_winner = competitor['winner']
                        except KeyError:
                            away_team_winner = False

                        away_team_score = competitor['score']

                        try:
                            away_team_score_1 = int(competitor['linescores'][0]['value'])
                        except (KeyError, IndexError):
                            away_team_score_1 = None
                        try:
                            away_team_score_2 = int(competitor['linescores'][1]['value'])
                        except (KeyError, IndexError):
                            away_team_score_2 = None
                        try:
                            away_team_score_3 = int(competitor['linescores'][2]['value'])
                        except (KeyError, IndexError):
                            away_team_score_3 = None
                        try:
                            away_team_score_4 = int(competitor['linescores'][3]['value'])
                        except (KeyError, IndexError):
                            away_team_score_4 = None
                        try:
                            away_team_score_ot = int(competitor['linescores'][4]['value'])
                        except (KeyError, IndexError):
                            away_team_score_ot = None
                if home_team_winner: 
                    game_winner = home_team_slug
                elif away_team_winner:
                    game_winner = away_team_slug
                else:
                    game_winner = ""

            payload = {
                "id": game_id,
                "slug": "{}-{}".format(home_team_slug, away_team_slug),
                "competition": game_competition,
                "gameWeek": game_week,
                "gameyear": game_year,
                "gameseason": game_season,
                "startTimestamp": game_start_timestamp,
                "gameWinner": game_winner,
                "statusType": game_status_type,
                "statusTitle": game_status_title,
                "homeTeamId": home_team_id,
                "homeTeamSlug": home_team_slug,
                "homeTeamName": home_team_name,
                "homeTeamScore": home_team_score,
                "homeTeamPeriod1": home_team_score_1,
                "homeTeamPeriod2": home_team_score_2,
                "homeTeamPeriod3": home_team_score_3,
                "homeTeamPeriod4": home_team_score_4,
                "homeTeamPeriodOT": home_team_score_ot,
                "awayTeamId": away_team_id,
                "awayTeamSlug": away_team_slug,
                "awayTeamName": away_team_name,
                "awayTeamScore": away_team_score,
                "awayTeamPeriod1": away_team_score_1,
                "awayTeamPeriod2": away_team_score_2,
                "awayTeamPeriod3": away_team_score_3,
                "awayTeamPeriod4": away_team_score_4,
                "awayTeamPeriodOT": away_team_score_ot
            }
            json_string = json.dumps(payload, default=str)
            add_games(json_string, game_id)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def update_games():
    print("Scheduled Job: Update NFL Games")

    if args.gameweek is not None:
        build_payload(args.gameweek)
    else:
        today = date.today()
        today_fmt = today.strftime("%Y-%m-%d")
        game_week = get_game_week(today_fmt)
        build_payload(game_week)


if __name__ == '__main__':
    update_games()