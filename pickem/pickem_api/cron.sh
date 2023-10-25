#!/bin/bash

# update games 
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_games_v2.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_games_v2.py 

# update picks
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_picks.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_picks.py 

# update team standings 
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_records.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_records.py 

# Update overall standings 
echo
echo
echo "################################################################"
echo "#"
echo "# Running: /code/pickem_api/cron_update_standings.py"
echo "#"
echo "################################################################"
echo
python /code/pickem_api/cron_update_standings.py 
echo
exit 0