#!/bin/bash

# Build --token argument if API_TOKEN env var is set
TOKEN_ARG=""
if [ -n "$API_TOKEN" ]; then
    TOKEN_ARG="--token $API_TOKEN"
fi

# update games
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_games_v2.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_games_v2.py --url $1 $TOKEN_ARG

# update picks
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_picks.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_picks.py --url $1 $TOKEN_ARG

# update team standings
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_records.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_records.py --url $1 $TOKEN_ARG

# Update overall standings
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_standings.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_standings.py --url $1 $TOKEN_ARG

# Update user rankings
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_rankings.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_rankings.py --url $1 $TOKEN_ARG
echo
exit 0