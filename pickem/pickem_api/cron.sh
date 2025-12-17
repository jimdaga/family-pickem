#!/bin/bash

# update games 
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_games_v2.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_games_v2.py --url $1

# update picks
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_picks.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_picks.py --url $1

# update team standings 
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_records.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_records.py --url $1

# Update overall standings
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_standings.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_standings.py --url $1

# Update user rankings
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_rankings.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_rankings.py --url $1
echo
exit 0