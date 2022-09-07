#!/bin/bash

URL=$1

cat  teams.csv | while read line; do
	teamNameSlug=$(echo $line | awk -F: '{print $1}' | tr -d '\r')
	teamNameName=$(echo $line | awk -F: '{print $2}' | tr -d '\r')
	id=$(echo $line | awk -F: '{print $3}' | tr -d '\r')

	template='{ "id": %s, "teamNameSlug": "%s", "teamNameName": "%s" }'

	# Variable to store your rendered template JSON string
	data=""

	# Render the template, substituting the variable values and save the result into $data
	printf -v data "$template" "$id" "$teamNameSlug" "$teamNameName"

  	curl -X POST --data "$data" https://$URL/api/teams/
	echo
done 
