#!/usr/bin/env python3

import requests
import json
from datetime import datetime
from datetime import date
import argparse

parser = argparse.ArgumentParser(description='Add User Standings')
parser.add_argument("--url", default="localhost:8000", help="Specify the API url.")
parser.add_argument("--token", help="API authentication token.")
args, leftovers = parser.parse_known_args()


def get_api_headers():
    """Build common headers for API requests, including auth token if provided."""
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = "Token {}".format(args.token)
    return headers


def unique_list(list):
    """
    Input a list, and return a unique list.
    """
    unique_list = []

    for x in list:
        if x not in unique_list:
            unique_list.append(x)

    return unique_list


def get_pick_user_ids(game_year, game_week):
    """
    Get a list of all ID's that have made picks
    """
    url = "http://{}/api/userpickids/{}/{}".format(
        args.url, game_year, game_week)

    id_list = []

    try:
        response = requests.request("GET", url, headers=get_api_headers())
        json_response = json.loads(response.text)

        for pick in json_response:
            if pick['uid'] != None:
                id_list.append(pick['uid'])

        return unique_list(id_list)

    except requests.exceptions.RequestException:
        print(response.text)


def get_user_info(game_year, game_week, uid):
    """
    Get user email/userid
    """
    url = "http://{}/api/userpicks/{}/{}/{}".format(
        args.url, game_year, game_week, uid)

    email_list = []
    userid_list = []

    try:
        response = requests.request("GET", url, headers=get_api_headers())
        json_response = json.loads(response.text)

        for pick in json_response:
            if pick['uid'] != None:
                email_list.append(pick['userEmail'])
                userid_list.append(pick['userID'])

        return unique_list(email_list), unique_list(userid_list)

    except requests.exceptions.RequestException:
        print(response.text)


def get_game_week(game_date):
    """
    Check week number for a date
    """
    try:
        url = "http://{}/api/weeks/{}".format(args.url, game_date)

        response = requests.request("GET", url, headers=get_api_headers())
        json_response = json.loads(response.text)
        return json_response['weekNumber']
    except:
        return "1"


def post_entry(game_year, game_week, uid):
    """
    Create a user record
    """
    url = "http://{}/api/userpoints/add".format(args.url)

    headers = get_api_headers()

    user_email, user_id = get_user_info(game_year, game_week, uid)

    user_email_str = None
    for x in unique_list(user_email):
        user_email_str = x
    user_id_str = None
    for y in unique_list(user_id):
        user_id_str = y

    payload = {
        "id": uid,
        "userEmail": user_email_str,
        "userID": user_id_str,
        "game_year": game_year
    }

    payload_string = json.dumps(payload, default=str)
    print(payload)
    x = requests.post(url, payload_string, headers=headers)

    if x.status_code == 200 or x.status_code == 201:
        print(" - User ID {}'s record sucesfully added".format(uid))
    else:
        print(" - Issues adding entry for User ID {}, status code: {}".format(uid, x.status_code))


def add_user_record(game_year, game_week, uid):
    """
    Check if a user has a entry
    """
    url = "http://{}/api/userpoints/{}/{}".format(args.url, game_year, uid)

    response = requests.request("GET", url, headers=get_api_headers())
    json_response = json.loads(response.text)

    if len(json_response) > 1:
        print("- User record already exists")
    else:
        post_entry(game_year, game_week, uid)


def update_games():
    print("Updating standings with weeks correct picks value")
    today = date.today()
    game_year = today.strftime("%Y")
    game_date = today.strftime("%Y-%m-%d")
    game_week = get_game_week(game_date)

    pick_list = get_pick_user_ids(game_year, game_week)
    for pick_id in pick_list:
        add_user_record(game_year, game_week, pick_id)


if __name__ == '__main__':
    update_games()
