#!/usr/bin/env python3

import requests
import json

def get_team_ids():
    
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"

    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.request("GET", url, headers=headers)
        json_response = json.loads(response.text)

        leagues_data = json_response["sports"][0]["leagues"]
        for leauge in leagues_data:
            for team in leauge['teams']:
                print('Updating Team Data for {}'.format(team['team']['slug']))
                update_team_record(team['team']['id'])


    except requests.exceptions.RequestException:
        print(response.text)

def update_team_record(team_id):
    """
    Get all the game data from ESPN APIs
    """
    headers = {
        "Content-Type": "application/json",
    }

    team_url = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2022/teams/{}".format(team_id)
    record_url = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2022/types/2/teams/{}/record".format(team_id)


    # Get team name info 
    try:
        response = requests.request("GET", team_url, headers=headers)
        json_response = json.loads(response.text)

        team_details = json_response
        team_id = team_details['id']
        team_slug = team_details['slug']
        team_display_name = team_details['displayName']
        logo = team_details['logos'][0]['href']

    except requests.exceptions.RequestException:
        print("Issue getting team details")
        print(response.text)

    # Get win/loss record info
    try:
        response = requests.request("GET", record_url, headers=headers)
        json_response = json.loads(response.text)

        stats = json_response["items"][0]['stats']
        for stat in stats:
            if stat['name'] == 'wins':
                team_wins = stat['displayValue']
            elif stat['name'] == 'losses':
                team_losses = stat['displayValue']
            elif stat['name'] == 'ties':
                team_ties = stat['displayValue']

    except requests.exceptions.RequestException:
        print(response.text)

    print("{} (Slug: {} - ID: {}) {}-{}-{}".format(team_display_name, team_slug, team_id, team_wins, team_losses, team_ties))

    url = "http://localhost:8000/api/teams/id/{}".format(team_id)

    payload = {
        "id": team_id,
        "teamNameSlug": team_slug,
        "teamNameName": team_display_name,
        "teamLogo": logo,
        "teamWins": team_wins,
        "teamLosses": team_losses,
        "teamTies": team_ties,
    }

    payload_string = json.dumps(payload, default=str)
    x = requests.patch(url, payload_string, headers = headers)

    if  x.status_code == 200 or x.status_code == 201:
        print(" - Team {} sucesfully updated \n".format(team_slug))
    else:
        print(" - Issues updating record for team {}, status code: {} \n".format(team_slug, x.status_code))

def update_games():
    get_team_ids()


if __name__ == '__main__':
    update_games()