# Home Assistant Integration Guide

This document explains how to integrate Allergen Alert with Home Assistant running on Proxmox.

## Architecture Overview

```
Proxmox Host
└── Home Assistant VM
    └── Mosquitto MQTT Broker (with TLS)
        ↓
Raspberry Pi 4 (Sensor Gateway)
├── Sensors (6 total)
└── MQTT Client (publishes via MQTTS)
```

## Prerequisites

1. **Proxmox VM** running Home Assistant (version 2024+)
2. **Mosquitto MQTT broker** with TLS configured
3. **Raspberry Pi 4 Model B** with Allergen Alert installed
4. **Network connectivity** between Pi and HA (LAN or VPN)

## Step 1: Verify Mosquitto Broker Configuration

Ensure your Mosquitto broker on the Proxmox VM is properly configured:

```bash
# Check Mosquitto is running
systemctl status mosquitto

# Verify TLS listener is active
netstat -ln | grep 8883
```

Expected configuration in `/etc/mosquitto/mosquitto.conf`:
```conf
listener 1883
protocol mqtt

listener 8883
protocol mqtt
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key

allow_anonymous false
password_file /etc/mosquitto/passwd
```

## Step 2: Configure Allergen Alert

### 2.1 Copy certificates to Raspberry Pi

```bash
# On Proxmox VM, copy certificates
scp /etc/mosquitto/certs/ca.crt pi@<pi-ip>:/home/pi/allergen-alert/certs/
```

### 2.2 Configure environment variables

Edit `.env` on the Raspberry Pi:

```bash
# MQTT Configuration
MQTT_BROKER_HOST=mqtt.proxmox.local      # or IP address of Proxmox host
MQTT_BROKER_PORT=8883
MQTT_USERNAME=rpi_sensor
MQTT_PASSWORD=<secure-password>
MQTT_TLS_CA_CERT=/home/pi/allergen-alert/certs/ca.crt
MQTT_TLS_CERTFILE=
MQTT_TLS_KEYFILE=
MQTT_TLS_VERSION=tlsv1_2

# Device Configuration
DEVICE_ID=rpi_main
PI_HOSTNAME=Raspberry Pi Air Quality Monitor

# Sensor Intervals (seconds)
SIMPLE_SENSOR_INTERVAL=300        # BME680, TSL2591 (5 minutes)
AIR_QUALITY_SENSOR_INTERVAL=60    # AHT21, ENS160, SCD40 (1 minute)
PM_SENSOR_INTERVAL=300            # PMS5003 (5 minutes)
SOUND_SENSOR_INTERVAL=60          # SPH0645 (1 minute)
HEALTH_CHECK_INTERVAL=600         # Health check (10 minutes)

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/allergen-alert.log
```

### 2.3 Test MQTT connectivity

```bash
# On Raspberry Pi
python3 scripts/test-mqtt-connection.py
```

Expected output:
```
Successfully connected to MQTT broker
Testing discovery message publication...
✓ Discovery message published
Testing data publication...
✓ Data publication successful
```

## Step 3: Configure Home Assistant MQTT Integration

### 3.1 Add MQTT integration (if not already present)

In Home Assistant, go to **Settings → Devices & Services → Integrations** and add MQTT:

**Configuration Details:**
- **Broker:** mqtt.proxmox.local (or IP address)
- **Port:** 8883
- **Username:** homeassistant
- **Password:** <secure-password>
- **TLS Insecure:** False
- **Discovery:** Enabled
- **Discovery Prefix:** homeassistant

### 3.2 Enable MQTT discovery

Add to `configuration.yaml`:

```yaml
mqtt:
  broker: mqtt.proxmox.local
  port: 8883
  username: !secret mqtt_user
  password: !secret mqtt_password
  tls_version: tlsv1_2
  discovery: true
  discovery_prefix: homeassistant
  discovery_retain: true
```

## Step 4: Start Allergen Alert

```bash
# On Raspberry Pi
sudo systemctl start allergen-alert
sudo systemctl status allergen-alert

# View logs
sudo journalctl -u allergen-alert -f
```

## Step 5: Verify Sensor Entities in Home Assistant

Go to **Developer Tools → MQTT** in Home Assistant and look for messages:

**Expected topics:**
- `home/rpi_aq/temperature/state` - AHT21 temperature
- `home/rpi_aq/humidity/state` - AHT21 humidity
- `home/rpi_aq/temperature_consensus/state` - Temperature consensus
- `home/rpi_aq/humidity_consensus/state` - Humidity consensus
- `home/rpi_aq/co2/state` - SCD40 CO2
- `home/rpi_aq/aqi/state` - ENS160 AQI
- `home/rpi_aq/pm2_5/state` - PM2.5
- `home/rpi_aq/light/state` - TSL2591 light
- `home/rpi_aq/unhealthy_sensors/state` - Health status

## Step 6: Create Home Assistant Automations

### Example: High PM2.5 Alert

```yaml
automation:
  - id: "high_pm25_alert"
    alias: "High PM2.5 Alert"
    description: "Notify when PM2.5 exceeds safe levels"
    trigger:
      platform: numeric_state
      entity_id: sensor.pm2_5
      above: 35  # µg/m³
      for:
        minutes: 2  # Only alert if sustained
    action:
      service: notify.mobile_app_<device>
      data:
        title: "Air Quality Alert"
        message: "PM2.5 is {{ states('sensor.pm2_5') }} µg/m³"
        data:
          color: "red"
```

### Example: High CO2 Alert

```yaml
automation:
  - id: "high_co2_alert"
    alias: "High CO2 Alert"
    description: "Notify when CO2 exceeds 1000 ppm"
    trigger:
      platform: numeric_state
      entity_id: sensor.co2_scd40
      above: 1000
      for:
        minutes: 5
    action:
      service: notify.mobile_app_<device>
      data:
        title: "Ventilation Needed"
        message: "CO2 is {{ states('sensor.co2_scd40') }} ppm - Open a window!"
```

### Example: Sensor Health Alert

```yaml
automation:
  - id: "sensor_health_alert"
    alias: "Sensor Health Alert"
    description: "Alert when sensors become unhealthy"
    trigger:
      platform: state
      entity_id: sensor.unhealthy_sensors
      to: "none"
      from: "none"
    action:
      service: persistent_notification.create
      data:
        title: "Sensor Status Change"
        message: >
          Unhealthy sensors: {{ states('sensor.unhealthy_sensors') }}
```

## Step 7: Create Home Assistant Dashboard

Example dashboard card configuration:

```yaml
views:
  - title: Air Quality
    cards:
      # Current readings
      - type: entities
        title: Current Status
        entities:
          - sensor.temperature_consensus
          - sensor.humidity_consensus
          - sensor.air_quality_index
          - sensor.co2_scd40

      # PM Chart (last 24 hours)
      - type: history-stats
        title: Particulate Matter Levels
        entities:
          - sensor.pm1_0
          - sensor.pm2_5
          - sensor.pm10

      # CO2 Chart
      - type: history-stats
        title: CO2 Levels
        entities:
          - sensor.co2_scd40

      # Sensor Health
      - type: entities
        title: Sensor Health
        entities:
          - sensor.unhealthy_sensors
```

## Troubleshooting

### MQTT Connection Failed

```bash
# Check Mosquitto is running and listening on 8883
netstat -ln | grep 8883

# Check TLS certificates
openssl s_client -connect mqtt.proxmox.local:8883 -CAfile /home/pi/allergen-alert/certs/ca.crt
```

### Sensors Not Appearing in Home Assistant

1. **Check MQTT Discovery**
   - Go to **Developer Tools → MQTT → Subscribe**
   - Subscribe to `homeassistant/#`
   - Restart Allergen Alert
   - Look for discovery messages

2. **Check Mosquitto logs**
   ```bash
   tail -f /var/log/mosquitto/mosquitto.log
   ```

3. **Verify credentials**
   ```bash
   mosquitto_pub -h mqtt.proxmox.local -p 8883 \
     -u rpi_sensor -P <password> \
     --cafile /path/to/ca.crt \
     -t "home/rpi_aq/test" -m "hello"
   ```

### Data Not Updating

1. **Check Allergen Alert logs**
   ```bash
   sudo journalctl -u allergen-alert -f
   ```

2. **Verify sensor health**
   - Check `sensor.unhealthy_sensors` in Home Assistant
   - Run `sudo systemctl restart allergen-alert`

3. **Check network connectivity**
   ```bash
   ping mqtt.proxmox.local
   ```

### Temperature Readings Seem Off

1. **Review offset settings** in `src/utils/data_aggregation.py`
   - BME680 is typically 3°C high due to CPU heat
   - Check `temperature_consensus` vs individual sensors

2. **Adjust offsets if needed**
   - Update `TEMPERATURE_OFFSETS` in `TemperatureAggregator`
   - Restart Allergen Alert

## Performance Tuning

### Adjust Sensor Intervals

Edit `.env` to change reading frequencies:

```bash
SIMPLE_SENSOR_INTERVAL=300        # Lower for more frequent readings
AIR_QUALITY_SENSOR_INTERVAL=60    # Higher to reduce CPU load
PM_SENSOR_INTERVAL=600            # PMS5003 duty cycle
```

### Reduce MQTT Publish Rate

Increase intervals to reduce network traffic and storage growth.

### Enable Log Rotation

```bash
# Create logrotate config
sudo nano /etc/logrotate.d/allergen-alert
```

```
/var/log/allergen-alert.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 pi pi
    sharedscripts
    postrotate
        systemctl reload allergen-alert > /dev/null 2>&1 || true
    endscript
}
```

## Next Steps

1. **Create custom Lovelace cards** for better visualization
2. **Set up data export to InfluxDB** for long-term analytics
3. **Configure Grafana dashboards** for advanced reporting
4. **Implement node-RED flows** for complex automations
5. **Add mobile push notifications** for critical alerts

## Support

For issues or questions:
1. Check logs: `sudo journalctl -u allergen-alert -f`
2. Review MQTT traffic: `mosquitto_sub -v -h mqtt.proxmox.local -p 8883 -u rpi_sensor -P <password> --cafile /path/to/ca.crt -t "home/rpi_aq/#"`
3. Test connectivity: `python3 scripts/test-mqtt-connection.py`
