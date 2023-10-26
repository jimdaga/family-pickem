#!/usr/bin/env python3

import requests
import json
from datetime import datetime
from datetime import date
import argparse

parser = argparse.ArgumentParser(description='Update Pickem User Records')
parser.add_argument("--url", help="Specify the API url.")
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
    
def unique_list(list):
    """
    Input a list, and return a unique list.
    """
    unique_list = []

    for x in list:
        if x not in unique_list:
            unique_list.append(x)

    return unique_list

def get_user_email(uid):
    """
    Get user email 
    """
    url = "http://{}/api/userinfo/{}".format(args.url, uid)

    headers = {
        "Content-Type": "application/json",
    }

    try:
        response = requests.request("GET", url, headers=headers)
        json_response = json.loads(response.text)
    except requests.exceptions.RequestException:
        print(response.text)
    
    return json_response['email']

def get_pick_user_ids(game_season, game_week):
    """
    Get a list of all ID's that have made picks
    """
    url = "http://{}/api/userpickids/{}/{}".format(
        args.url, game_season, game_week)

    headers = {
        "Content-Type": "application/json",
    }

    id_list = []

    try:
        response = requests.request("GET", url, headers=headers)
        json_response = json.loads(response.text)

        for pick in json_response:
            if pick['uid'] != None:
                id_list.append(pick['uid'])

        return unique_list(id_list)

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


def patch_picks(game_season, game_week, uid, points_total):
    """
    Update users record with correct picks 
    """
    url = "http://{}/api/userpoints/{}/{}".format(args.url, game_season, uid)

    headers = {
        "Content-Type": "application/json",
    }

    week_points = "week_{}_points".format(game_week)

    payload = {
        "userID": uid,
        week_points: points_total,
    }

    payload_string = json.dumps(payload, default=str)
    x = requests.patch(url, payload_string, headers=headers)

    if x.status_code == 200 or x.status_code == 201:
        print(" - User ID {}'s points sucesfully updated".format(uid))
    elif x.status_code == 404:
        # Add entry for new user
        print(" - No Records found for user with ID {}, adding an entry now".format(uid))
        today = date.today()

        user_email = get_user_email(uid)

        payload_new = {
            "userID": uid,
            "gameseason": game_season,
            "gameyear": today.year,
            "userEmail": user_email,
            "total_points": "0",
        }

        payload_new_string = json.dumps(payload_new, default=str)
        try:
            requests.post(url, payload_new_string, headers=headers)
        except:
            print(" - Issues adding new entry for User ID {}, status code: {}".format(uid, x.status_code))
    else:
        print(" - Issues updating record for User ID {}, status code: {}".format(uid, x.status_code))


def patch_total_points(game_season, uid):
    """
    Update users total points record
    """
    get_url = "http://{}/api/userpoints/{}/{}".format(
        args.url, game_season, uid)
    patch_url = "http://{}/api/userpoints/{}/{}".format(
        args.url, game_season, uid)

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("GET", get_url, headers=headers)
    json_response = json.loads(response.text)

    sum = 0
    for key in json_response:
        if ((('points' in key) or ('bonus' in key)) and (json_response[key] != None) and (key != 'total_points')):
            sum += json_response[key]
    print(" - User with ID {} has {} total correct picks".format(uid, sum))

    payload = {
        "id": uid,
        "total_points": sum,
    }

    payload_string = json.dumps(payload, default=str)
    x = requests.patch(patch_url, payload_string, headers=headers)

    if x.status_code == 200 or x.status_code == 201:
        print(" - User ID {}'s total points sucesfully updated".format(uid))
    else:
        print(" - Issues updating record for User ID {}, status code: {}".format(uid, x.status_code))


def update_correct_picks(game_season, game_week, uid):
    """
    Count how many correct picks the user made, and update their record
    """
    picks_url = "http://{}/api/userpicks/{}/{}/{}".format(
        args.url, game_season, game_week, uid)

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("GET", picks_url, headers=headers)
    json_response = json.loads(response.text)

    points_total = 0
    for pick in json_response:
        points_total += 1

    patch_picks(game_season, game_week, uid, points_total)


def update_games():
    print("Updating standings with weeks correct picks value")
    today = date.today()
    game_season = get_season()
    game_date = today.strftime("%Y-%m-%d")
    game_week = get_game_week(game_date)

    pick_list = get_pick_user_ids(game_season, game_week)
    for pick_id in pick_list:
        update_correct_picks(game_season, game_week, pick_id)
        patch_total_points(game_season, pick_id)
        print()


if __name__ == '__main__':
    update_games()
