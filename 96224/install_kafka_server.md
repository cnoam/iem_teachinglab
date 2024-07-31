# Create a small Kafka server
[NC 2024-07-31] 
 
Create VM (e.g. in Azure) with SSH connection. The key should be stored in your ~/.ssh 

I used Ubuntu 20.04, 22.04

Give the server a DNS name in the Azure portal. e.g. `kafka.eastus.cloudapp.azure.com`

Add to `~/.ssh/config`  :
```
Host kafka
  HostName kafka.eastus.cloudapp.azure.com
  User azureuser
  IdentitiesOnly yes
```
# Install docker

`ssh kafka`

```
sudo apt-get remove docker docker-engine docker.io containerd runc

# https://docs.docker.com/engine/install/ubuntu/#install-from-a-package
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh ./get-docker.sh

# sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker

docker run hello-world
```

Get an image with Kafka. For example the Spark course which already contains data

```
git clone https://github.com/cnoam/spark-course.git
cd spark-course
# Edit the dockercompose.yml and update the line to something like this:
# KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://:29092
docker compose up kafka -d
```

Load data:
```
sudo apt install -y kafkacat
files=`ls data/sdg/retail-data/by-day/*.csv`
for f in $files; do kafkacat -b localhost:29092 -t retail -P -l $f; done

# verify:
kafkacat -b localhost:29092 -e -t retail -C  | wc -l
```

# Add network inbound rule so clients can connect to port 29092
In the portal, under 'network settings' add inboud rule: TCP, from anywhere, port 29092

on local PC, check connectivity:
export REMOTEHOST=kafka.eastus.cloudapp.azure.com<br>
`kafkacat -b $REMOTEHOST:29092 -e -t retail -C  | wc -l`

After a few moments, you should get **542214**

**WARNING:** This kafka server provide free access to anyone. You should keep only public data in it. Also you should add alerts if the VM start to behave erratically.

