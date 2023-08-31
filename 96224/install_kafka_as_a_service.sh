#!/bin/sh -eu

# install the needed env for the kafka server

# TODO: make sure docker is installed properly

# TODO: make sure the path /data is mounted and writable

chmod 644 run_kafka_docker.service
sudo cp run_kafka_docker.service /etc/systemd/system/
sudo systemctl enable run_kafka_docker.service
sudo systemctl start run_kafka_docker.service
