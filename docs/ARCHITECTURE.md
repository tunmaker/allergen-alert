# System Architecture

## Overview

Allergen Alert is a distributed air quality monitoring system that integrates a Raspberry Pi sensor gateway with a central Home Assistant instance running on Proxmox.

```
┌─────────────────────────────────────────┐
│        Proxmox Hypervisor (x86)         │
│  ┌─────────────────────────────────────┐│
│  │  Home Assistant VM                  ││
│  │  ┌──────────────────────────────────┤│
│  │  │ Home Assistant Core               ││
│  │  │ ├─ MQTT Integration              ││
│  │  │ ├─ Automation Engine             ││
│  │  │ ├─ Dashboard/UI                  ││
│  │  │ └─ Data Storage (SQLite)        ││
│  │  └──────────────────────────────────┤│
│  │  ┌──────────────────────────────────┤│
│  │  │ Mosquitto MQTT Broker (TLS)      ││
│  │  │ ├─ Port 8883 (MQTTS)             ││
│  │  │ ├─ Certificate-based Auth        ││
│  │  │ └─ Message Persistence           ││
│  │  └──────────────────────────────────┤│
│  └─────────────────────────────────────┘│
└──────────────┬──────────────────────────┘
               │ MQTTS (TLS Encrypted)
               │ Port 8883
               ▼
┌──────────────────────────────────────────┐
│   Raspberry Pi 4 Model B                 │
│  ┌──────────────────────────────────────┐│
│  │ Allergen Alert Daemon (Python)       ││
│  │ ├─ Sensor Reading Loop               ││
│  │ ├─ Data Aggregation                  ││
│  │ ├─ MQTT Client (TLS)                 ││
│  │ └─ Discovery Publisher               ││
│  └──────────────────────────────────────┤│
│  ┌──────────────────────────────────────┐│
│  │ Sensor Interfaces                    ││
│  │ ├─ I2C Bus 1 (AHT21, ENS160, etc.)  ││
│  │ ├─ UART (PMS5003)                    ││
│  │ ├─ I2S (SPH0645 - future)           ││
│  │ └─ Calibration Tracking              ││
│  └──────────────────────────────────────┤│
│  ┌──────────────────────────────────────┐│
│  │ 6 Sensors                            ││
│  │ ├─ SPH0645: I2S Microphone          ││
│  │ ├─ BME680: Env. Sensor (I2C)        ││
│  │ ├─ ENS160: Air Quality (I2C)        ││
│  │ ├─ AHT21: Temp/Humidity (I2C)       ││
│  │ ├─ SCD40: CO2 (I2C)                 ││
│  │ ├─ TSL2591: Light (I2C)             ││
│  │ └─ PMS5003: Particulates (UART)     ││
│  └──────────────────────────────────────┤│
└──────────────────────────────────────────┘
```

## Communication Flow

### 1. Sensor Reading
- **Frequency**: Configurable (1-5 minute intervals)
- **Sampling**: Continuous background reading from each sensor
- **Processing**: Data aggregation and validation on Pi

### 2. MQTT Publishing
- **Discovery**: Automatic Home Assistant discovery on startup
- **Data Topics**: `home/rpi_aq/<sensor_name>/state`
- **Availability**: `home/rpi_aq/availability` (online/offline)
- **Encryption**: TLS 1.2+ with certificate-based authentication

### 3. Home Assistant Integration
- **Auto-discovery**: Sensors appear automatically in HA
- **Entity Names**: Based on device_id and sensor type
- **History**: HA stores historical data with configurable retention
- **Automations**: Trigger actions based on sensor values

## Data Flow Diagram

```
Sensor ─→ Read ─→ Validate ─→ Aggregate ─→ MQTT ─→ Broker ─→ HA
           (Pi)      (Pi)       (Pi)      Publish  (TLS)    Integration
          Loop     Handler    Consensus  Client              Auto-add to
                                         Discovery           Dashboard
```

## Security Architecture

### Transport Security
- **MQTT**: TLS 1.2+ encrypted connection
- **Certificates**: Self-signed CA + client certificates
- **Authentication**: Username/password + certificate-based

### Data Privacy
- **Local-only**: All data stays on home network
- **No cloud**: No external service access
- **Open source**: Full code transparency

### Device Security
- **Systemd service**: Runs with limited privileges
- **User account**: Dedicated `allergen-alert` user
- **File permissions**: Restrictive certificate permissions
- **No sudo required**: Application runs as non-root

## Component Details

### Raspberry Pi Daemon
**File**: `src/main.py`

- Multi-threaded sensor reading loop
- Configurable polling intervals
- Automatic reconnection to MQTT broker
- Signal handling for graceful shutdown
- Comprehensive error logging

### MQTT Client
**Files**: `src/mqtt/client.py`

- Paho-MQTT implementation
- TLS support with certificate validation
- Automatic reconnection with exponential backoff
- Message persistence (QoS 1)
- Discovery message publishing

### Discovery Publisher
**Files**: `src/mqtt/discovery.py`

- Home Assistant MQTT Discovery format
- Standard device classes and attributes
- Sensor-specific configuration
- Bulk discovery message publishing

### Sensor Drivers
**Files**: `src/sensors/*.py`

Each sensor has:
- I2C/UART/I2S protocol handling
- Error recovery and validation
- Data type conversion and formatting
- Optional calibration parameters
- Duty cycle management (PMS5003)

## Scaling Considerations

### Single Pi Setup
- Up to 15-20 sensor entities
- MQTT message rate: ~5-10 messages/minute
- CPU load: <5% on Raspberry Pi 4
- Network: Minimal bandwidth (<1 MB/hour)

### Multiple Pis
- Use unique `DEVICE_ID` for each Pi
- Separate MQTT topics per device
- Home Assistant discovers multiple devices
- Aggregation via automations or templates

## Customization Points

### Adding Sensors
1. Create driver in `src/sensors/`
2. Register in `src/main.py`
3. Add MQTT topic publishing
4. Publish discovery message

### Modifying Read Intervals
Edit `.env`:
```bash
SIMPLE_SENSOR_INTERVAL=300        # BME680, TSL2591 (5 min)
AIR_QUALITY_SENSOR_INTERVAL=60    # AHT21, ENS160, SCD40 (1 min)
PM_SENSOR_INTERVAL=300            # PMS5003 (5 min)
```

### Custom Automations
Home Assistant automations can:
- Trigger on thresholds
- Send notifications
- Control smart home devices
- Calculate aggregated values
- Generate alerts

## Performance Characteristics

### Sensor Accuracy
- **Temperature**: ±0.2-0.8°C (AHT21 most accurate)
- **Humidity**: ±2-6% RH
- **CO2**: ±40 ppm (SCD40 NDIR)
- **PM2.5**: ±10-15% (consumer grade)

### Latency
- Sensor read: 10-100ms per sensor
- MQTT publish: 50-200ms per message
- Home Assistant update: 1-5 seconds
- Dashboard refresh: 5-30 seconds (depends on browser)

### Reliability
- **Uptime**: 99%+ with proper setup
- **Recovery**: Automatic reconnection to MQTT
- **Data loss**: Minimal with MQTT QoS 1
- **Failover**: Manual (replace Pi)

## Future Enhancements

### Planned Features
- [ ] Support for additional sensor types
- [ ] Local data logging to database
- [ ] Grafana dashboard integration
- [ ] REST API for remote access
- [ ] Advanced analytics and ML predictions

### Possible Extensions
- Mobile app with notifications
- Voice assistant integration (Alexa, Google Home)
- Integration with other platforms (Node-RED, Zigbee2MQTT)
- Multi-location aggregation
- Predictive air quality alerts
