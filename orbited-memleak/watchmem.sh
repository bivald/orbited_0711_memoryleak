#!/bin/bash

echo -n > orbited-log
while [[ true ]]
do
	(
		echo -n \[$(date)\]" "
		ps auxw | grep orbi[t]
	) >>orbited-log
	tail -n1 orbited-log
	sleep 60
done
