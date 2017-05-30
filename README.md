## Install ##
1. Download the code to `/opt/algochecker-engine` and `cd` to this directory.
2. Execute `apt-get install docker.io python3 python3-pip`.
3. Execute `pip3 install -r requirements.txt`.
4. Copy the configuration file `worker_conf.py.dist` to `worker_conf.py`.
5. Adjust the configuration if needed (mostly ensure that `REDIS_CONF` is valid). Everything should
work without any changes if you are doing the whole setup on a single machine.
6. Install systemd service:
```
cp contrib/systemd/algo-engine.service /lib/systemd/system/
systemctl enable algo-engine
```
7. Execute `service algo-engine start`.
8. Done. The service should be up and running, waiting for submissions to process.


## Check installation ##
Not necessarily, you may test algochecker-engine without any additional software, just by:
1. Going to the directory `/opt/algochecker-engine/contrib`.
2. Starting the standalone package server: `python3 packserv.py`.
3. Starting (in parallel) the `submit` tool: `python3 submit.py demo-basic`.
4. Seeing what happens in the engine: `journalctl -u algo-engine`.


## Ok, but where is the GUI? ##
Consult `README.md` file of `algochecker-web` project for hints about setting up the web interface.


## Additional tools ##
In the `contrib` directory you may find some additional tools which may be helpful especially for testing.
* `packserv.py` - mock of package repository; packages created on-demand by means
of `contrib/package` directory
* `submit.py` - sends some user submission to the queue, few templates available in
`contrib/submission` directory
* `collect.py` - prints final results published by workers on the Redis "reports" channel
