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


def get_unscored_games():
    """
    Get all the unscored games
    """
    url = "http://localhost:8000/api/unscored"
    
    response = requests.request("GET", url)
    json_response = json.loads(response.text)
    print(json_response)

def update_picks():
    print("Scheduled Job: Update Unscored Picks")

if __name__ == '__main__':
    update_picks()