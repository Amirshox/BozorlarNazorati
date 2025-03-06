#!/bin/bash

GITHUB_TOKEN={{ github_token }}
GITHUB_USERNAME=KamoliddinS
GITHUB_REPO=https_server

SERVICE_NAME=jetson_device_manager.service
SERVICE_PATH=/etc/systemd/system/$SERVICE_NAME

JETSON_DEVICE_ID={{ jetson_device_id }}
JETSON_DEVICE_MANAGER_URL={{ jetson_device_manager_url }}

is_git_repo() {
    local dir=$1
    if [ -d "$dir/.git" ]; then
        echo "The directory '$dir' is a Git repository."
        return 0
    else
        echo "The directory '$dir' is not a Git repository."
        return 1
    fi
}

if is_git_repo "$GITHUB_REPO"; then
  echo "Repository already exists. Updating repository..."
  cd $GITHUB_REPO
  git pull
else
  echo  "Repository does not exist. Cloning repository..."

  git clone https://$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/$GITHUB_REPO.git
  cd $GITHUB_REPO
fi


echo "Installing python"
sudo apt-get update
sudo apt-get install python3-pip -y
sudo apt install nmap arp-scan

echo "Installing python packages"
pip3 install -r websocket_client.requirements.txt

echo "Creating environment configurations"
cat << EOF | sudo tee .env
JETSON_DEVICE_ID=$JETSON_DEVICE_ID
JETSON_DEVICE_MANAGER_URL=$JETSON_DEVICE_MANAGER_URL
INFO_LOG_OUTPUT_PATH=/var/log/jetson_device_manager_info.logs
ERROR_LOG_OUTPUT_PATH=/var/log/jetson_device_manager_error.logs
EOF

echo "Creating systemctl service"
cat << EOF | sudo tee $SERVICE_PATH
[Unit]
Description=Jetson device manager service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/sudo python3 $(pwd)/websocket_client.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF


sudo systemctl daemon-reload

sudo systemctl enable $SERVICE_NAME

sudo systemctl start $SERVICE_NAME

echo "Service $SERVICE_NAME has been created and started."

json_content='{
    "deepstream_applications": []
}'

json_file_name='deepstream_controller.json'

mkdir deepstream_management
mkdir deepstream_management/services
cd deepstream_management
echo "$json_content" > $json_file_name

cd ..
mkdir deepstream_applications