#!/bin/bash

# Remember that in such scripts line feeds MUST BE LF
# otherwise there may be some very strange problems

cd /mnt/server

SERVER_IP=$(hostname -i)
echo -n ${SERVER_IP} > /mnt/shared/server_ip
touch ready

chmod +x server
./server ${SERVER_IP} > output.txt 2> error.txt

touch finished

exit $?
