#!/bin/bash

# Remember that in such scripts line feeds MUST BE LF
# otherwise there may be some very strange problems

cd /mnt/data
touch /mnt/out/ready

while [ ! -f /mnt/in/ready_ok ]
do
    sleep 0.01
done

TIMESTART=`date +%s%N`
/mnt/in/prog < /mnt/in/input.txt > /mnt/out/output.txt 2> /mnt/out/error.txt
EXITCODE=$?
TIMEEND=`date +%s%N`

TIME=`expr \( $TIMEEND - $TIMESTART \) / 1000000`

echo "{\"exit_code\": $EXITCODE, \"exec_time\": $TIME}"

touch /mnt/out/finished

sleep 60