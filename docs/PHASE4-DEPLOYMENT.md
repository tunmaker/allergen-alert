# Phase 4: Full Deployment Guide

Complete guide for deploying the entire Allergen Alert system with Grafana dashboards and Home Assistant automations.

## Architecture Overview

```
Raspberry Pi 4 (Allergen Alert Daemon)
    ↓ (MQTT with TLS)
Proxmox VM - Mosquitto MQTT Broker
    ├→ Home Assistant (automations + control)
    ├→ InfluxDB (time-series storage)
    ├→ Grafana (visualization & dashboards)
    └→ Node-RED (optional: advanced flows)

User Controls:
├→ Home Assistant Dashboard (UI controls)
├→ Mobile Notifications (alerts & summaries)
├→ Grafana Dashboards (monitoring)
└→ Smart Home Devices (climate, ventilation, purifiers)
```

## Prerequisites

Before starting, ensure you have:

1. **Proxmox Host**
   - 4+ vCPU
   - 8+ GB RAM
   - 50+ GB disk space
   - Network access to Raspberry Pi

2. **Virtual Machines on Proxmox**
   - Home Assistant VM (or Docker container)
   - MQTT broker (Mosquitto)
   - InfluxDB (time-series database)
   - Grafana (dashboard server)

3. **Raspberry Pi 4 with Allergen Alert**
   - All 6 sensors connected and verified
   - Phase 1, 2, 3 implementation complete
   - Network connectivity to Proxmox (LAN or VPN)

4. **Smart Home Devices** (optional but recommended)
   - Smart thermostat (Nest, Ecobee, etc.) or HVAC controller
   - Smart windows/vents (Aqara, Eve, etc.)
   - Smart fans or air purifiers (Philips, Dyson, etc.)

## Step 1: Prepare Proxmox Infrastructure

### 1.1 Create MQTT Broker VM

```bash
# On Proxmox host
pct create 101 /path/to/ubuntu-20.04-template.tar.zst \
  -hostname mqtt-broker \
  -memory 2048 \
  -cores 2 \
  -net0 name=eth0,bridge=vmbr0,ip=192.168.1.100/24,gw=192.168.1.1 \
  -storage local-lvm

# Start container
pct start 101

# Enter and setup Mosquitto
pct enter 101
apt update && apt install -y mosquitto mosquitto-clients

# Generate TLS certificates (or copy from existing)
mkdir -p /etc/mosquitto/certs
cd /etc/mosquitto/certs

# Copy CA, server certs from existing setup
# Or generate new: see MQTT-CONFIG.md
```

### 1.2 Create InfluxDB Container

```bash
docker run -d \
  --name influxdb \
  -p 8086:8086 \
  -e INFLUXDB_DB=allergen_alert \
  -e INFLUXDB_ADMIN_USER=admin \
  -e INFLUXDB_ADMIN_PASSWORD=secure_password \
  -v influxdb_storage:/var/lib/influxdb \
  influxdb:latest
```

### 1.3 Create Grafana Container

```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=secure_password \
  -e GF_USERS_ALLOW_SIGN_UP=false \
  -v grafana_storage:/var/lib/grafana \
  grafana/grafana:latest
```

## Step 2: Configure Data Flow (MQTT → InfluxDB)

### 2.1 Set Up Telegraf Bridge (Recommended)

```bash
docker run -d \
  --name telegraf \
  -v /etc/telegraf/telegraf.conf:/etc/telegraf/telegraf.conf:ro \
  telegraf:latest
```

Create `/etc/telegraf/telegraf.conf`:

```toml
[agent]
  interval = "10s"
  round_interval = true

[[inputs.mqtt_consumer]]
  servers = ["mqtt://mqtt-broker:1883"]
  topics = ["home/rpi_aq/+/state"]
  username = "telegraf"
  password = "secure_password"
  data_format = "value"
  data_type = "float"

[[outputs.influxdb]]
  urls = ["http://influxdb:8086"]
  database = "allergen_alert"
  username = "telegraf"
  password = "secure_password"
  retention_policy = ""
  write_consistency = "any"
  timeout = "5s"

[[outputs.influxdb.tagpass]]
  measurement = ["home_rpi_aq*"]
```

## Step 3: Deploy Grafana Dashboard

### 3.1 Access Grafana

1. Open browser: `http://proxmox-ip:3000`
2. Login: admin / secure_password
3. Change admin password immediately

### 3.2 Add InfluxDB Data Source

1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **InfluxDB**
4. Configure:
   ```
   Name: allergen-alert
   URL: http://influxdb:8086
   Database: allergen_alert
   User: admin
   Password: secure_password
   ```
5. Click **Save & Test**

### 3.3 Import Dashboard

1. Go to **Dashboards → Manage**
2. Click **New → Import**
3. Upload `dashboard/grafana/allergen-alert-dashboard.json`
4. Select data source: **allergen-alert**
5. Click **Import**

### 3.4 Configure Dashboard Alerts (Optional)

On any panel:
1. Click **Alert** button
2. Set condition: `when avg() of last 5m is above X`
3. Create notification channel:
   - **Email**: SMTP configuration
   - **Slack**: Webhook URL
   - **PagerDuty**: Integration key
4. Save

Example alert:
```
Name: PM2.5 High Alert
Condition: when avg(home_rpi_aq_pm2_5_state) of last 5m is above 35
For: 2m
Notify: Slack channel #air-quality
```

## Step 4: Configure Home Assistant

### 4.1 Access Home Assistant

1. Open browser: `http://proxmox-ha-ip:8123`
2. Complete setup if first time
3. Create user account

### 4.2 Add MQTT Integration

1. Go to **Settings → Devices & Services → Integrations**
2. Search for **MQTT**
3. Configure:
   ```
   Broker: mqtt-broker (or IP)
   Port: 1883 (or 8883 for TLS)
   Username: homeassistant
   Password: secure_password
   Discovery: ON
   ```
4. Click **Create**

### 4.3 Verify Sensor Discovery

After MQTT integration enabled:

1. Wait 1-2 minutes for discovery
2. Go to **Settings → Devices & Services → Entities**
3. Look for sensor entities from Allergen Alert:
   - sensor.temperature_consensus
   - sensor.humidity_consensus
   - sensor.pm2_5
   - sensor.co2_scd40
   - sensor.overall_aqi
   - etc.

All sensors should appear automatically through MQTT discovery.

### 4.4 Add Smart Home Devices

Connect your climate control devices:

**Thermostat Example:**
```yaml
climate:
  - platform: generic_thermostat
    name: Living Room
    heater: switch.living_room_heater
    ac_mode: cool
    target_sensor: sensor.temperature_consensus
    min_temp: 15
    max_temp: 30
    ac_power: switch.living_room_ac
```

**Smart Window Example:**
```yaml
cover:
  - platform: mqtt
    name: Living Room Window
    command_topic: "home/living_room/window/command"
    state_topic: "home/living_room/window/state"
    payload_open: "OPEN"
    payload_close: "CLOSE"
    payload_stop: "STOP"
```

**Air Purifier Example:**
```yaml
fan:
  - platform: mqtt
    name: Air Purifier
    command_topic: "home/air_purifier/command"
    state_topic: "home/air_purifier/state"
    percentage_state_topic: "home/air_purifier/speed"
    percentage_command_topic: "home/air_purifier/speed/set"
```

### 4.5 Add Automations

1. Go to **Settings → Automations & Scenes**
2. Click **Create Automation**
3. Click **Edit in YAML**
4. Copy automation from `config/home-assistant-automations.yaml`
5. Update entity IDs for your devices
6. Click **Save**

Start with these core automations:
- Climate: Heating (low temp)
- Climate: Cooling (high temp)
- Ventilation: High CO2 opening
- Air Purifier: High PM2.5 start

Test each one before adding more.

## Step 5: Configure Notifications

### 5.1 Mobile App Notifications

1. Install Home Assistant mobile app
2. Open app on phone
3. Add Home Assistant instance
4. Go to **Settings → Companion App**
5. Configure push notifications

In automations, use:
```yaml
service: notify.mobile_app_username
data:
  title: "Alert"
  message: "Your message"
  data:
    color: "red"
    priority: "high"
```

### 5.2 Email Notifications

```yaml
service: notify.email
data:
  title: "Alert"
  message: "Your message"
  target: "user@example.com"
```

### 5.3 Slack Notifications

1. Create Slack webhook: https://api.slack.com/messaging/webhooks
2. In automation:
```yaml
service: notify.slack
data:
  title: "Alert"
  message: "Your message"
  target: "#air-quality"
```

## Step 6: Monitoring & Verification

### 6.1 Verify Data Flow

**Check MQTT Publishing:**
```bash
# On Proxmox host
mqtt sub -h mqtt-broker -u rpi_sensor -P password -t "home/rpi_aq/#"

# Should show continuous updates:
home/rpi_aq/temperature_consensus/state 22.5
home/rpi_aq/humidity_consensus/state 45
home/rpi_aq/pm2_5/state 12.3
# ... etc
```

**Check InfluxDB Storage:**
```bash
# Docker exec into InfluxDB
docker exec influxdb influx query 'show measurements'

# Should show:
home_rpi_aq_temperature_consensus_state
home_rpi_aq_pm2_5_state
# ... etc
```

**Check Home Assistant Entities:**
Go to **Developer Tools → States** and search for "rpi_aq"

All sensor entities should be listed.

### 6.2 Test Automations

1. Go to **Settings → Automations & Scenes**
2. Find automation
3. Click **Run** button
4. Verify action occurs:
   - Check device state changed
   - Check notification received
   - Check Home Assistant logs

### 6.3 Monitor Grafana

1. Open Grafana dashboard
2. Verify panels show data (not blank)
3. Check time range (default: last 24h)
4. Monitor for **No Data** errors:
   - Edit panel → Check query syntax
   - Verify metric names match InfluxDB
   - Check data source connectivity

## Step 7: Performance Tuning

### 7.1 Database Retention

Set data retention policy in InfluxDB:

```bash
docker exec influxdb influx

> create retention policy "7days" on "allergen_alert" duration 7d replication 1

> create retention policy "30days" on "allergen_alert" duration 30d replication 1 default

> show retention policies on "allergen_alert"
```

This prevents database from growing indefinitely.

### 7.2 Grafana Panel Optimization

For production:

1. **Reduce refresh rate:**
   - Dashboard → Top right → 60s (instead of 30s)

2. **Limit time range:**
   - For 24h view: last 24h
   - For weekly: last 7d
   - Avoid 90+ days on high-frequency metrics

3. **Enable caching:**
   - Grafana → Configuration → Enable HTTP cache headers

### 7.3 Home Assistant Performance

1. **Limit automation complexity:**
   - Avoid nested conditions where possible
   - Use `choose` instead of multiple automations

2. **Enable debug logging selectively:**
   ```yaml
   logger:
     logs:
       homeassistant.automation: debug  # Only when troubleshooting
   ```

3. **Archive old automations:**
   - Delete unused automations
   - Keep active set minimal

## Step 8: Backup & Recovery

### 8.1 Backup Strategy

**Daily backups:**
```bash
# Backup Grafana (docker)
docker exec grafana grafana-cli admin export-dashboard > grafana-backup-$(date +%Y%m%d).json

# Backup Home Assistant configuration
tar czf ha-backup-$(date +%Y%m%d).tar.gz /home/homeassistant/.homeassistant/

# Backup InfluxDB
docker exec influxdb influxd backup /tmp/backup-$(date +%Y%m%d)
```

**Weekly cloud backup:**
```bash
# Upload to cloud storage (AWS S3, Google Drive, etc)
aws s3 cp grafana-backup-latest.json s3://my-backups/
```

### 8.2 Recovery Procedure

1. **Restore Grafana:**
   ```bash
   docker exec grafana grafana-cli admin restore-dashboard grafana-backup.json
   ```

2. **Restore Home Assistant:**
   ```bash
   tar xzf ha-backup.tar.gz -C /home/homeassistant/
   systemctl restart homeassistant
   ```

3. **Restore InfluxDB:**
   ```bash
   docker exec influxdb influxd restore /tmp/backup-date/
   ```

## Step 9: Security Hardening

### 9.1 Change Default Passwords

- [ ] Grafana admin password
- [ ] Home Assistant user password
- [ ] InfluxDB credentials
- [ ] MQTT broker credentials
- [ ] Proxmox passwords

### 9.2 Enable HTTPS

For Home Assistant:
```yaml
http:
  ssl_certificate: /path/to/cert.pem
  ssl_key: /path/to/key.pem
```

For Grafana:
```ini
[security]
cert_file = /etc/grafana/cert.pem
cert_key = /etc/grafana/key.pem
```

### 9.3 Network Segmentation

Create VLAN for IoT:
```
Main Network: 192.168.1.0/24
IoT Network: 192.168.2.0/24

Home Assistant: 192.168.1.10
MQTT Broker: 192.168.2.50
Raspberry Pi: 192.168.2.100
```

## Step 10: Ongoing Maintenance

### Weekly Tasks
- [ ] Review error logs in Home Assistant
- [ ] Check Grafana dashboard for data anomalies
- [ ] Verify all automations triggered as expected

### Monthly Tasks
- [ ] Create backups
- [ ] Update container images
- [ ] Review and adjust thresholds based on data trends
- [ ] Check sensor health status

### Quarterly Tasks
- [ ] Review InfluxDB storage usage
- [ ] Update automation logic if needed
- [ ] Optimize Grafana dashboards
- [ ] Review security settings

### Annual Tasks
- [ ] Full system backup to archive storage
- [ ] Update documentation
- [ ] Review and update calibration
- [ ] Plan system upgrades

## Troubleshooting

### Sensors Not Appearing in Home Assistant

1. Verify MQTT discovery enabled: **Settings → Devices & Services → MQTT**
2. Check topics are correct format: `homeassistant/sensor/*/config`
3. Verify sensor discovery messages retain flag is set: `true`
4. Restart Home Assistant: **Settings → System → Restart**

### Grafana Shows No Data

1. Verify data source: **Configuration → Data Sources → Test**
2. Check InfluxDB has data: `influx query 'show measurements'`
3. Edit panel → **Run Query** to test query syntax
4. Check metric naming matches InfluxDB exactly (case-sensitive)

### Automation Not Triggering

1. Verify entity exists: **Developer Tools → States**
2. Check automation YAML syntax
3. Test automation: **Automations & Scenes → ... → Run**
4. Enable debug logging: see HA-AUTOMATIONS.md

### High CPU/Memory Usage

1. Reduce Grafana refresh rates (60s instead of 30s)
2. Limit InfluxDB retention policy
3. Archive old Home Assistant automations
4. Check for log spam: `journalctl -u home-assistant -f | grep ERROR`

## Next Steps

1. **Fine-tune thresholds** based on your environment
2. **Create custom scenes** for different modes (sleep, away, entertain)
3. **Add voice control** with Alexa/Google Home
4. **Set up remote access** with VPN (WireGuard/OpenVPN)
5. **Integrate with other smart home systems** (Zigbee, Z-Wave)

## Support Resources

- Home Assistant Docs: https://www.home-assistant.io/docs/
- Grafana Docs: https://grafana.com/docs/grafana/latest/
- MQTT Documentation: https://mqtt.org/
- Allergen Alert: See project README.md

## Deployment Checklist

- [ ] Proxmox infrastructure created (MQTT, InfluxDB, Grafana)
- [ ] Data flow verified (MQTT → InfluxDB)
- [ ] Grafana dashboard imported and tested
- [ ] Home Assistant MQTT integration configured
- [ ] Sensors auto-discovered in Home Assistant
- [ ] Smart home devices connected
- [ ] Automations created and tested
- [ ] Notifications configured
- [ ] Backups scheduled
- [ ] Security hardening completed
- [ ] Documentation updated
- [ ] Team trained on system operation

**Status: Deployment Complete! ✓**

Your Allergen Alert system is now fully operational with comprehensive monitoring and automated climate control.
