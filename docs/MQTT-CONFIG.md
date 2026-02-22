# MQTT Configuration Guide

This guide covers setting up Mosquitto MQTT broker on Proxmox/Home Assistant with TLS encryption and configuring the Raspberry Pi client.

## Mosquitto Broker Setup (Proxmox/Home Assistant)

### Installation

#### Option 1: Docker Container (Recommended for Proxmox)
```bash
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 8883:8883 \
  -v /etc/mosquitto/:/etc/mosquitto/:ro \
  -v /var/lib/mosquitto/:/var/lib/mosquitto/ \
  -e CHANGE_CITEXT=1 \
  eclipse-mosquitto
```

#### Option 2: Direct Installation
```bash
# Update package lists
sudo apt-get update

# Install Mosquitto
sudo apt-get install -y mosquitto mosquitto-clients

# Start service
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### TLS Certificate Setup

#### 1. Generate Certificates
```bash
# Create certificates directory
sudo mkdir -p /etc/mosquitto/certs
cd /etc/mosquitto/certs

# Run the provided certificate generation script
bash /path/to/allergen-alert/scripts/generate-certificates.sh /etc/mosquitto/certs

# Set permissions
sudo chown -R mosquitto:mosquitto /etc/mosquitto/certs
sudo chmod 600 /etc/mosquitto/certs/*.key
```

#### 2. Configure Mosquitto for TLS

Edit `/etc/mosquitto/mosquitto.conf`:

```conf
# Default listener (optional, for internal use)
listener 1883
protocol mqtt

# TLS listener (encrypted, production)
listener 8883
protocol mqtt

# TLS Certificates
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key

# Security - require authentication
allow_anonymous false
password_file /etc/mosquitto/passwd

# Persistence
persistence true
persistence_location /var/lib/mosquitto/

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_dest stdout

# Connection limits
max_connections -1
```

### User Authentication

#### Create Password File
```bash
# Create password for Home Assistant
sudo mosquitto_passwd -c /etc/mosquitto/passwd homeassistant

# Add user for Raspberry Pi client
sudo mosquitto_passwd -b /etc/mosquitto/passwd rpi_sensor your_password_here

# Set permissions
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo chmod 600 /etc/mosquitto/passwd
```

### Restart Mosquitto
```bash
sudo systemctl restart mosquitto

# Check status
sudo systemctl status mosquitto

# Monitor logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### Verify TLS Setup
```bash
# Test connection with TLS
mosquitto_sub -h mqtt.proxmox.local -p 8883 \
  --cafile /etc/mosquitto/certs/ca.crt \
  -u rpi_sensor -P your_password \
  -t "test/topic" -v
```

## Home Assistant MQTT Integration

### 1. Enable MQTT Integration

**Via UI**:
1. Settings → Devices & Services → Create Integration
2. Search for "MQTT"
3. Click "Create"
4. Enter broker details

**Via YAML**:
Edit `configuration.yaml`:
```yaml
mqtt:
  broker: mqtt.proxmox.local
  port: 8883
  username: homeassistant
  password: !secret mqtt_homeassistant_password
  tls_version: tlsv1_2
  tls_insecure: false
  discovery: true
  discovery_prefix: homeassistant
  birth_message:
    topic: homeassistant/status
    payload: online
  will_message:
    topic: homeassistant/status
    payload: offline
```

### 2. Add Secret for Password
Edit `secrets.yaml`:
```yaml
mqtt_homeassistant_password: your_secure_password
```

### 3. Verify MQTT Connection
In Home Assistant:
1. Settings → Devices & Services → MQTT
2. Check connection status (should show "1 configured")
3. Go to Developer Tools → MQTT → Publish
4. Test by publishing to `home/test/topic` with payload `test`

## Raspberry Pi MQTT Client Configuration

### 1. Copy Certificates
```bash
# Create certificates directory
sudo mkdir -p /etc/allergen-alert/certs
sudo chown allergen-alert:allergen-alert /etc/allergen-alert/certs
sudo chmod 700 /etc/allergen-alert/certs

# Copy certificates from Proxmox
sudo scp user@proxmox-host:/etc/mosquitto/certs/ca.crt \
  /etc/allergen-alert/certs/
sudo scp user@proxmox-host:/etc/mosquitto/certs/client.crt \
  /etc/allergen-alert/certs/
sudo scp user@proxmox-host:/etc/mosquitto/certs/client.key \
  /etc/allergen-alert/certs/

# Set permissions
sudo chown allergen-alert:allergen-alert /etc/allergen-alert/certs/*
sudo chmod 600 /etc/allergen-alert/certs/client.key
```

### 2. Configure Allergen Alert

Edit `/opt/allergen-alert/.env`:
```bash
# MQTT Broker (change hostname as needed)
MQTT_BROKER_HOST=mqtt.proxmox.local
MQTT_BROKER_PORT=8883
MQTT_USERNAME=rpi_sensor
MQTT_PASSWORD=your_password_here

# TLS Certificates
MQTT_TLS_CA_CERT=/etc/allergen-alert/certs/ca.crt
MQTT_TLS_CERTFILE=/etc/allergen-alert/certs/client.crt
MQTT_TLS_KEYFILE=/etc/allergen-alert/certs/client.key
MQTT_TLS_VERSION=tlsv1_2

# Device identification
PI_HOSTNAME=rpi-air-quality-01
DEVICE_ID=rpi_main
```

### 3. Test MQTT Connection
```bash
# Run test script
python3 /opt/allergen-alert/scripts/test-mqtt-connection.py

# Or manually test with mosquitto_sub
mosquitto_sub -h mqtt.proxmox.local -p 8883 \
  --cafile /etc/allergen-alert/certs/ca.crt \
  --cert /etc/allergen-alert/certs/client.crt \
  --key /etc/allergen-alert/certs/client.key \
  -u rpi_sensor -P password \
  -t "home/rpi_aq/#" -v
```

## Troubleshooting

### Connection Issues

#### "Connection refused"
```bash
# Check if Mosquitto is running
sudo systemctl status mosquitto

# Check port is listening
sudo netstat -tulpn | grep 8883

# Check firewall
sudo ufw status
sudo ufw allow 8883
```

#### "TLS handshake failure"
```bash
# Verify certificate validity
openssl x509 -in /etc/mosquitto/certs/server.crt -text -noout

# Check certificate matches key
openssl x509 -noout -modulus -in /etc/mosquitto/certs/server.crt | openssl md5
openssl rsa -noout -modulus -in /etc/mosquitto/certs/server.key | openssl md5
# (Both should produce same hash)
```

#### "Authentication failed"
```bash
# Verify user exists in password file
sudo cat /etc/mosquitto/passwd

# Re-create password
sudo mosquitto_passwd -b /etc/mosquitto/passwd rpi_sensor new_password

# Restart Mosquitto
sudo systemctl restart mosquitto
```

### Debugging MQTT Messages

#### Monitor all topics
```bash
mosquitto_sub -h mqtt.proxmox.local -p 8883 \
  --cafile /path/to/ca.crt \
  -u rpi_sensor -P password \
  -t "#" -v
```

#### Monitor discovery messages
```bash
mosquitto_sub -h mqtt.proxmox.local -p 8883 \
  --cafile /path/to/ca.crt \
  -u rpi_sensor -P password \
  -t "homeassistant/sensor/#" -v
```

#### Publish test message
```bash
mosquitto_pub -h mqtt.proxmox.local -p 8883 \
  --cafile /path/to/ca.crt \
  -u rpi_sensor -P password \
  -t "home/rpi_aq/test" -m "hello"
```

### Performance Optimization

#### Message Rate Limiting
If experiencing high CPU or network usage:

Edit `mosquitto.conf`:
```conf
# Limit max connections per second
max_queued_messages 1000
message_size_limit 10000  # bytes
```

#### Persistence Tuning
```conf
persistence true
persistence_interval 3600  # Flush every hour

# Or disable for testing
# persistence false
```

## Network Configuration

### Wi-Fi Setup for Raspberry Pi
```bash
# Edit netplan configuration
sudo nano /etc/netplan/50-cloud-init.yaml

# Example configuration:
network:
  version: 2
  wifis:
    wlan0:
      access-points:
        "YourWiFiSSID":
          password: "yourpassword"
      dhcp4: true
```

Apply changes:
```bash
sudo netplan apply
sudo systemctl restart networking
```

### VPN (Optional)
For remote monitoring, consider VPN for additional security:
- WireGuard (recommended)
- OpenVPN
- Tailscale

## Production Checklist

- [ ] Mosquitto running with TLS
- [ ] Password file configured
- [ ] Certificate validity checked
- [ ] Home Assistant MQTT integration enabled
- [ ] Raspberry Pi client connected
- [ ] Sensor discovery appearing in HA
- [ ] Historical data being stored
- [ ] Firewall rules configured
- [ ] Regular backups of HA data
- [ ] Logs monitored for errors

## Additional Resources

- [Mosquitto Documentation](https://mosquitto.org/man/mosquitto-conf-5.html)
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)
- [MQTT Security Best Practices](https://mosquitto.org/documentation/)
- [Paho Python MQTT Client](https://github.com/eclipse/paho.mqtt.python)
