#!/bin/bash

# Remember that in such scripts line feeds MUST BE LF
# otherwise there may be some very strange problems

cd /mnt/in
touch /mnt/out/ready

while [ ! -f /mnt/in/ready_ok ]
do
    sleep 0.01
done

TIMESTART=`date +%s%N`
java -classpath /mnt/in Main < /mnt/in/input.txt > /mnt/out/output.txt
EXITCODE=$?
TIMEEND=`date +%s%N`

TIME=`expr \( $TIMEEND - $TIMESTART \) / 1000000`

echo "{\"exit_code\": $EXITCODE, \"exec_time\": $TIME}"

touch /mnt/out/finished

sleep 60