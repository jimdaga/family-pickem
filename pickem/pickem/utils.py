import requests
from django.conf import settings

def get_season():
    """
    Fetches the current season from the API endpoint.
    """
    try:
        # Construct the URL using the configured API host.
        api_host = getattr(settings, 'API_HOST', 'localhost:8000')
        url = f"http://{api_host}/api/currentseason/"
        
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json().get('current_season', 'default_season_value')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching current season from API: {e}. Using fallback logic.")
        # Fallback to a default or raise an exception
        return None 