#!/bin/bash

# Remember that in such scripts line feeds MUST BE LF
# otherwise there may be some very strange problems

cd /mnt/in
mkfifo /mnt/in/input.txt
mkfifo /mnt/in/output.txt

cd /mnt/service
chmod +x service
./service < svc-input.txt > svc-output.txt
EXITCODE=$?
touch /mnt/in/svc-finished
exit $EXITCODE
