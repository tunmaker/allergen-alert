# Grafana Dashboard Setup Guide

This guide explains how to set up the Allergen Alert Grafana dashboard for complete air quality visualization and monitoring.

## Overview

The Allergen Alert dashboard provides comprehensive visualization of:
- Real-time air quality metrics (AQI, PM2.5, CO2)
- Temperature and humidity trends (3-sensor consensus)
- Sensor health status and calibration progress
- 24-hour historical trends
- Health impact indicators with color-coded thresholds

## Prerequisites

1. **Grafana instance** (v8.0+)
   - Docker, VM, or local installation
   - Network access to MQTT broker or InfluxDB/Prometheus
   - Admin access for creating dashboards

2. **Data source configured**
   - MQTT to InfluxDB bridge, OR
   - Prometheus with MQTT exporter, OR
   - Direct InfluxDB storage from Pi

3. **Allergen Alert sending data** to your metrics backend

## Option 1: Docker Setup (Recommended for Proxmox)

### 1.1 Create docker-compose.yml

```yaml
version: '3'

services:
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    volumes:
      - grafana_storage:/var/lib/grafana
      - ./provisioning:/etc/grafana/provisioning
    networks:
      - monitoring

  influxdb:
    image: influxdb:latest
    container_name: influxdb
    ports:
      - "8086:8086"
    environment:
      - INFLUXDB_DB=allergen_alert
      - INFLUXDB_ADMIN_USER=admin
      - INFLUXDB_ADMIN_PASSWORD=admin
    volumes:
      - influxdb_storage:/var/lib/influxdb
    networks:
      - monitoring

  mqtt-to-influxdb:
    image: fluent/fluent-bit:latest
    container_name: mqtt-to-influxdb
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
    networks:
      - monitoring
    depends_on:
      - influxdb

volumes:
  grafana_storage:
  influxdb_storage:

networks:
  monitoring:
```

### 1.2 Configure MQTT to InfluxDB Bridge

Create `fluent-bit.conf`:

```conf
[SERVICE]
    Flush        5
    Log_Level    info
    Daemon       off

[INPUT]
    Name              mqtt
    Tag               allergen_alert.*
    Broker            mqtt.proxmox.local:8883
    Port              8883
    Topics            home/rpi_aq/+/state
    mqtt_Mode         publisher
    Secure            ON
    CA_Path           /etc/ssl/certs/ca-certificates.crt

[OUTPUT]
    Name              influxdb
    Match             allergen_alert.*
    Host              influxdb
    Port              8086
    Database          allergen_alert
    Sequence_Tag      _seq
    HTTP_Token        <your_token>
    Auto_Tags         on
```

### 1.3 Start Services

```bash
docker-compose up -d
```

Grafana will be available at: http://localhost:3000

## Option 2: Manual Installation

### 2.1 Install Grafana

**Ubuntu/Debian:**
```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
sudo apt-get update
sudo apt-get install grafana-server

sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

**Access:** http://localhost:3000
**Default credentials:** admin/admin

### 2.2 Add Data Source

1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **InfluxDB**
4. Configure:
   - **URL:** http://localhost:8086
   - **Database:** allergen_alert
   - **User:** admin
   - **Password:** (your password)
5. Click **Save & Test**

## Importing the Dashboard

### Method 1: Import from JSON File

1. Go to **Dashboards → New → Import**
2. Click **Upload JSON file**
3. Select `allergen-alert-dashboard.json`
4. Choose your data source
5. Click **Import**

### Method 2: Manual Setup (Copy Panel Configs)

If you prefer to create panels manually, refer to the panel configurations in this document.

## Dashboard Panels Overview

### 1. Top Row - Current Status (Gauges)

**Air Quality Index (AQI)**
- Color thresholds: Green (0-50) → Yellow (51-100) → Orange (101-150) → Red (151-200) → Purple (200+)
- Shows real-time overall air quality
- Updates every 30 seconds

**Temperature Consensus**
- Color thresholds: Blue (<15) → Green (15-20) → Yellow (20-24) → Red (24+)
- Median of 3 temperature sensors (AHT21, BME680, SCD40)
- CPU heat correction applied

**Humidity Consensus**
- Color thresholds: Red (<30%) → Green (30-60%) → Yellow (60-80%) → Red (80%+)
- Weighted average prioritizing most accurate sensor (AHT21)
- Optimal range: 40-60%

**CO2 Levels**
- Color thresholds: Green (<400) → Yellow (400-600) → Orange (600-1000) → Red (1000+) ppm
- Direct reading from SCD40 (most accurate CO2)
- Excellent for ventilation control decisions

### 2. Middle Rows - 24-Hour Trends

**PM2.5 Levels**
- Raw and smoothed readings
- Shows effectiveness of moving average filter
- Color-coded by EPA standard
- Useful for correlating with air purifier operation

**Temperature Variance**
- Overlays all 3 temperature sensors
- Shows BME680 CPU heat effect (typically 2-5°C high)
- Validates sensor offset correction

**Air Quality Indicators**
- CO2, eCO2 (estimated), TVOC combined
- Shows relationship between indicators
- Identifies cause of poor air quality

**Light Intensity**
- TSL2591 readings in lux
- Useful for detecting daytime patterns
- Can trigger daylight-based automations

### 3. Lower Rows - Health & Status

**ENS160 Burn-in Progress**
- Bar showing 0-100% progress over 7 days
- Indicates when full accuracy is reached
- Green bar when complete

**ENS160 Accuracy Level**
- Text display: initializing → burn_in → improving → full
- Useful for understanding data reliability
- Auto-updates as sensor burns in

**Sensor Health Status**
- Table showing unhealthy sensors
- "none" when all healthy
- "sensor1,sensor2,..." when issues detected

**PM2.5 Health Impact**
- Large stat showing PM2.5 with health category
- Green (Good: 0-12)
- Yellow (Moderate: 12-35)
- Orange (Unhealthy for Sensitive: 35-55)
- Red (Unhealthy: 55-150)
- Purple (Very Unhealthy/Hazardous: 150+)

## Customization Guide

### Adding Alerts

1. Go to your dashboard
2. Click **Alert** button on any panel
3. Set condition: `when avg() of last 5m is above X`
4. Create notification channel: Email, Slack, PagerDuty, etc.
5. Example alert: **PM2.5 > 35 µg/m³ for 5 minutes**

### Adjusting Time Range

- Click time range selector (top right)
- Options: Last 1h, 3h, 6h, 12h, 24h, 7 days, 30 days
- Or set custom range

### Adding Custom Variables

To filter by sensor or location:

1. Go to **Dashboard settings → Variables**
2. Click **New variable**
3. Name: `sensor`
4. Query: `label_values(home_rpi_aq_*, sensor)`
5. Add `${sensor}` to panel queries

### Color Scheme Customization

To change panel colors:

1. Edit panel → **Field options**
2. **Threshold** section:
   - Adjust color thresholds to your preferences
   - Supports absolute or percentage modes
   - RGB color picker

## Data Source Configuration

### InfluxDB Query Examples

**Current PM2.5:**
```
SELECT last("value") FROM "home_rpi_aq_pm2_5_state" WHERE time > now() - 1h
```

**CO2 24-hour trend:**
```
SELECT mean("value") FROM "home_rpi_aq_co2_state"
WHERE time > now() - 24h
GROUP BY time(5m)
```

**Temperature consensus:**
```
SELECT "value" FROM "home_rpi_aq_temperature_consensus_state"
WHERE time > now() - 24h
```

### Prometheus Relabeling (if using Prometheus)

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'allergen-alert'
    static_configs:
      - targets: ['mqtt-exporter:9000']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'home_rpi_aq_.*'
        action: keep
```

## Advanced: Provisioning Dashboards

For automatic deployment, use Grafana provisioning:

Create `/etc/grafana/provisioning/dashboards/allergen-alert.yaml`:

```yaml
apiVersion: 1

providers:
  - name: 'Allergen Alert'
    orgId: 1
    folder: 'Air Quality'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards/allergen-alert
```

Place `allergen-alert-dashboard.json` in `/var/lib/grafana/dashboards/allergen-alert/`

Restart Grafana:
```bash
sudo systemctl restart grafana-server
```

## Troubleshooting

### Dashboard Shows "No Data"

1. Verify data source connection:
   - Go to **Configuration → Data Sources → Test**
   - Should show "Data source is working"

2. Check MQTT data flow:
   - Subscribe to `home/rpi_aq/#` in MQTT client
   - Verify messages are being published

3. Check InfluxDB:
   ```bash
   influx query 'from(bucket:"allergen_alert") |> range(start:-1h)'
   ```

### Panels Not Updating

1. Check refresh rate (top right) - set to 30s
2. Verify query: Edit panel → **Run query** button
3. Check metric names in InfluxDB:
   ```bash
   influx bucket list
   ```

### High CPU Usage

- Reduce panel refresh rate (60s instead of 30s)
- Limit time range (24h instead of 90d)
- Disable auto-refresh for archived dashboards

## Performance Optimization

### For Production

1. **Enable Grafana rendering:**
   ```bash
   [rendering]
   server_url = http://renderer:8081/render
   ```

2. **Configure retention policies (InfluxDB):**
   ```sql
   CREATE RETENTION POLICY "30d" ON "allergen_alert"
   DURATION 30d REPLICATION 1 DEFAULT
   ```

3. **Use downsampling for old data:**
   ```sql
   SELECT mean("value") INTO "30d_mean"
   FROM "home_rpi_aq_pm2_5_state"
   GROUP BY time(1h)
   ```

## Next Steps

- Set up **Home Assistant automations** for climate control (see HA-AUTOMATIONS.md)
- Configure **alerts** for critical thresholds
- Create **custom annotations** for maintenance events
- Set up **data export** for long-term analysis

## Support

For issues:
1. Check Grafana logs: `journalctl -u grafana-server -f`
2. Check data source connectivity
3. Verify MQTT broker is accessible
4. Review dashboard JSON for syntax errors
