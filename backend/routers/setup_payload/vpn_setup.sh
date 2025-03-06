#!/bin/bash

# OpenVPN installation 
sudo apt update
sudo apt install openvpn

# systemctl service for OpenVPN 
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# Create the OpenVPN systemd service file
SERVICE_FILE="/etc/systemd/system/openvpn-client@.service"

echo "Creating systemd service file for OpenVPN client..."
cat <<EOL > $SERVICE_FILE
[Unit]
Description=OpenVPN client for %I
After=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/openvpn --config /etc/openvpn/client/%i.conf
WorkingDirectory=/etc/openvpn/client
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd to recognize the new service
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Variables
VPN_SERVER={{ vpn_server }}
VPN_PORT={{ vpn_port }}
VPN_PROTOCOL={{ vpn_protocol }}
VPN_CONFIG_PATH="/etc/openvpn/client"
VPN_CONFIG_FILE="${VPN_CONFIG_PATH}/client.conf"


# Ensure OpenVPN directory exists
mkdir -p $VPN_CONFIG_PATH

chmod 600 $VPN_CONFIG_FILE

# Create the OpenVPN configuration file
cat <<EOL > $VPN_CONFIG_FILE
client
dev tun
proto $VPN_PROTOCOL
remote $VPN_SERVER $VPN_PORT
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-CBC
auth SHA256
comp-lzo
verb 3
<ca>
{{ ca_certificate }}
</ca>
<cert>
{{ client_certificate }}
</cert>
<key>
{{ client_key }}
</key>
EOL

# Start the OpenVPN client
sudo systemctl start openvpn-client@client
sudo systemctl enable openvpn-client@client

# Confirm VPN connection status
sleep 5
if systemctl status openvpn-client@client | grep -q "active (running)"; then
    echo "VPN connection established successfully."
else
    echo "Failed to establish VPN connection."
fi
