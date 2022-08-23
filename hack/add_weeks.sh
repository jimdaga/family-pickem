#!/bin/bash

for game_date in `cat weeks.csv`; do
	competition=$(echo $game_date | awk -F, '{print $1}')
	weekNumber=$(echo $game_date | awk -F, '{print $2}' | gsed 's/"//g')
	gameDate=$(echo $game_date | awk -F, '{print $3}' | tr -d '\r')

	template='{ "weekNumber": %s, "competition": "%s", "date": "%s" }'

	# Variable to store your rendered template JSON string
	data=""

	# Render the template, substituting the variable values and save the result into $data
	printf -v data "$template" "$weekNumber" "$competition" "$gameDate"

  	curl -X POST --data "$data" http://localhost:8000/api/weeks
	echo
done 
