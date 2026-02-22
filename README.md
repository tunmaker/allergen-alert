# Allergen Alert - Raspberry Pi Air Quality Monitor

A comprehensive air quality monitoring system for Raspberry Pi that integrates with Home Assistant via MQTT. Monitor particulate matter, CO2, VOCs, temperature, humidity, pressure, light, and sound levels from 6 consumer-grade sensors.

## Features

- **6 Integrated Sensors**: PM2.5/PM10, CO2, VOCs, Temperature, Humidity, Pressure, Light, Sound
- **Home Assistant Integration**: Automatic MQTT discovery and real-time dashboard
- **TLS-Encrypted Communication**: Secure MQTT over TLS with certificate-based authentication
- **Multi-Sensor Support**: Easy to add multiple Raspberry Pis as sensor gateways
- **Intelligent Calibration**: Automatic burn-in tracking (ENS160), offset correction, auto-calibration (SCD40)
- **Data Aggregation**: Multiple temperature and humidity sensors for best accuracy
- **Duty Cycle Management**: Extends PMS5003 laser lifetime with intelligent scheduling
- **Systemd Integration**: Automatic startup and restart on failure

## Hardware Requirements

### Raspberry Pi
- **Device**: Raspberry Pi 4 Model B
- **OS**: Raspberry Pi OS Lite 64-bit (recommended)
- **Power**: 5V/3A power supply

### Sensors (6 Total)
1. **SPH0645LM4H** - I2S MEMS Microphone (Sound)
2. **BME680** - 4-in-1 Environmental Sensor (Temp, Humidity, Pressure, Gas)
3. **ENS160 + AHT21** - Air Quality + Temp/Humidity
4. **SCD40** - CO2 Sensor (NDIR)
5. **TSL2591** - Light Sensor
6. **PMS5003** - Laser Particulate Matter Sensor

**See [WIRING.md](docs/WIRING.md) for detailed hardware connections.**

## Architecture

```
┌─────────────────────────┐
│    Proxmox Host         │
│  ┌──────────────────┐   │
│  │ Home Assistant   │   │
│  │ + Mosquitto MQTT │   │
│  │    (TLS)         │   │
│  └──────────────────┘   │
└───────────┬─────────────┘
            │ MQTTS (Port 8883)
            │
┌───────────┴──────────────┐
│   Raspberry Pi 4         │
│  ┌──────────────────┐    │
│  │ Allergen Alert   │    │
│  │ (Python Daemon)  │    │
│  │                  │    │
│  │ ┌─────────────┐  │    │
│  │ │ I2C Sensors │  │    │
│  │ │ UART Sensor │  │    │
│  │ │ I2S Audio   │  │    │
│  │ └─────────────┘  │    │
│  └──────────────────┘    │
└─────────────────────────┘
```

## Quick Start

### 1. Prerequisites

- Raspberry Pi 4 with sensors connected
- Mosquitto MQTT broker running on Proxmox VM (with TLS enabled)
- Home Assistant with MQTT integration enabled

### 2. Installation

Clone the repository:
```bash
git clone https://github.com/yourusername/allergen-alert.git
cd allergen-alert
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Copy and configure environment variables:
```bash
cp .env.example .env
nano .env  # Edit with your MQTT broker details
```

### 3. Setup Raspberry Pi

Enable I2C and UART:
```bash
sudo raspi-config
# Interface Options → I2C → Yes
# Interface Options → Serial Port → No (login shell), Yes (hardware)
# Save and reboot
```

Run setup script:
```bash
sudo bash scripts/setup-rpi.sh
```

### 4. Configure MQTT TLS

Copy your TLS certificates to the Pi:
```bash
sudo mkdir -p /etc/allergen-alert/certs
sudo cp /path/to/ca.crt /etc/allergen-alert/certs/
sudo cp /path/to/client.crt /etc/allergen-alert/certs/
sudo cp /path/to/client.key /etc/allergen-alert/certs/
sudo chown -R $(whoami):$(whoami) /etc/allergen-alert/certs
sudo chmod 600 /etc/allergen-alert/certs/client.key
```

See [MQTT-CONFIG.md](docs/MQTT-CONFIG.md) for detailed TLS setup on Proxmox.

### 5. Test Sensor Detection

```bash
# Scan I2C devices
sudo i2cdetect -y 1

# Expected addresses:
# 0x29 (TSL2591)
# 0x38 (AHT21)
# 0x53 (ENS160)
# 0x62 (SCD40)
# 0x76 or 0x77 (BME680)

# Test UART device
python3 scripts/test-mqtt-connection.py
```

### 6. Start the Service

```bash
# Install systemd service
sudo cp systemd/allergen-alert.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable allergen-alert.service
sudo systemctl start allergen-alert.service

# Check status
sudo systemctl status allergen-alert.service

# View logs
sudo journalctl -u allergen-alert.service -f
```

### 7. Verify Home Assistant Integration

In Home Assistant:
1. Go to **Settings → Devices & Services → MQTT**
2. Look for a device named "Raspberry Pi Main" (or your `PI_HOSTNAME`)
3. Should see 15+ sensor entities (temperature, humidity, PM2.5, CO2, etc.)
4. Create a dashboard card to display the data

## Configuration

### Environment Variables (.env)

Key settings to customize:

```bash
# MQTT connection
MQTT_BROKER_HOST=mqtt.proxmox.local
MQTT_BROKER_PORT=8883
MQTT_USERNAME=rpi_sensor
MQTT_PASSWORD=secure_password

# Device identification (for multi-Pi setups)
PI_HOSTNAME=rpi-air-quality-01
DEVICE_ID=rpi_main

# Sensor intervals (seconds)
SIMPLE_SENSOR_INTERVAL=300        # BME680, TSL2591
AIR_QUALITY_SENSOR_INTERVAL=60    # ENS160, SCD40
PM_SENSOR_INTERVAL=300            # PMS5003
```

See [.env.example](.env.example) for all available options.

### MQTT Topics

The system publishes to:

```
homeassistant/sensor/<device>/<sensor_id>/config    # Discovery
home/rpi_aq/<sensor_name>/state                      # Data updates
home/rpi_aq/availability                             # Online/offline status
```

Example:
```
homeassistant/sensor/rpi_main/temperature/config
home/rpi_aq/temperature/state
home/rpi_aq/availability
```

### Home Assistant Integration

Minimal configuration (if not using autodiscovery):

```yaml
# configuration.yaml
mqtt:
  broker: mqtt.proxmox.local
  port: 8883
  username: homeassistant
  password: !secret mqtt_password
  tls_version: tlsv1_2
  discovery: true
  discovery_prefix: homeassistant

sensor:
  - platform: mqtt
    name: "Air Quality Index"
    state_topic: "home/rpi_aq/aqi/state"
    unit_of_measurement: "AQI"
    device_class: "aqi"
```

See [HA-INTEGRATION.md](docs/HA-INTEGRATION.md) for complete examples.

## Sensor Specifications

| Sensor | Measurement | Accuracy | Range |
|--------|-------------|----------|-------|
| BME680 | Temp, Humidity, Pressure, Gas | ±1°C, ±3% RH, ±1 hPa | 300-1100 hPa |
| AHT21 | Temp, Humidity | ±0.2°C, ±2% RH | -40 to 85°C |
| SCD40 | CO2 | ±40 ppm + 5% | 400-5000 ppm |
| ENS160 | eCO2, TVOC, AQI | Relative | 400-65000 ppm |
| TSL2591 | Light | High dynamic range | 188 µlux to 88k lux |
| PMS5003 | PM1.0, PM2.5, PM10 | ±10-15% | 0-500 µg/m³ |
| SPH0645 | Sound | dBA | 50Hz-15kHz |

## Project Structure

```
allergen-alert/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── .env.example                        # Configuration template
│
├── config/
│   ├── mqtt-io.yaml                    # mqtt-io sensor configuration
│   ├── home-assistant-sensors.yaml     # HA MQTT sensor definitions
│   └── mosquitto.conf.example          # Mosquitto configuration
│
├── src/
│   ├── main.py                         # Main daemon (complex sensors)
│   ├── sensors/
│   │   ├── pms5003.py                  # Particulate matter sensor
│   │   ├── ens160_aht21.py             # Air quality sensor
│   │   ├── scd40.py                    # CO2 sensor
│   │   ├── bme680.py                   # Environmental sensor
│   │   ├── tsl2591.py                  # Light sensor
│   │   └── sph0645.py                  # Microphone
│   │
│   ├── mqtt/
│   │   ├── client.py                   # MQTT client with TLS
│   │   └── discovery.py                # HA MQTT discovery
│   │
│   └── utils/
│       ├── i2c_scanner.py              # I2C device detection
│       └── calibration.py              # Sensor calibration
│
├── scripts/
│   ├── setup-rpi.sh                    # Pi environment setup
│   ├── generate-certificates.sh        # TLS certificate generation
│   ├── test-mqtt-connection.py         # MQTT connectivity test
│   └── i2c-scanner.py                  # I2C device scanner
│
├── docs/
│   ├── ARCHITECTURE.md                 # System design
│   ├── SETUP_GUIDE.md                  # Detailed installation
│   ├── HA-INTEGRATION.md               # Home Assistant configuration
│   ├── MQTT-CONFIG.md                  # MQTT broker setup
│   ├── TROUBLESHOOTING.md              # Common issues
│   └── WIRING.md                       # Hardware wiring diagram
│
├── systemd/
│   └── allergen-alert.service          # Systemd service unit
│
└── tests/
    ├── test_mqtt_client.py             # MQTT client tests
    ├── test_sensor_reading.py          # Sensor reading tests
    └── test_ha_discovery.py            # Discovery message tests
```

## Documentation

- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** - Step-by-step installation instructions
- **[HA-INTEGRATION.md](docs/HA-INTEGRATION.md)** - Home Assistant configuration examples
- **[MQTT-CONFIG.md](docs/MQTT-CONFIG.md)** - MQTT broker and TLS setup
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and data flow
- **[WIRING.md](docs/WIRING.md)** - Hardware connection diagram
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## Usage Examples

### Monitor Air Quality in Real-Time

```bash
# Start the daemon
sudo systemctl start allergen-alert.service

# Monitor MQTT messages
mosquitto_sub -h mqtt.proxmox.local -p 8883 \
  --cafile /etc/allergen-alert/certs/ca.crt \
  -u rpi_sensor -P password \
  -t "home/rpi_aq/#" -v
```

### Home Assistant Automation Example

```yaml
automation:
  - id: "air_quality_alert"
    alias: "High PM2.5 Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.particulate_matter_2_5
      above: 35  # µg/m³
    action:
      service: persistent_notification.create
      data:
        title: "Air Quality Alert"
        message: "PM2.5 is {{ states('sensor.particulate_matter_2_5') }} µg/m³"
```

### Multiple Raspberry Pi Setup

For monitoring multiple locations, configure each Pi with a unique `DEVICE_ID`:

```bash
# Pi 1: Living Room
DEVICE_ID=rpi_living_room
MQTT_TOPIC_PREFIX=home/air_quality/living_room

# Pi 2: Bedroom
DEVICE_ID=rpi_bedroom
MQTT_TOPIC_PREFIX=home/air_quality/bedroom
```

Each will publish to separate topics and appear as different devices in Home Assistant.

## Sensor Calibration

### Temperature Offset Correction

The BME680 may read 2-5°C higher than other sensors due to Pi CPU heat. Calibrate offset:

```bash
# Compare readings with AHT21 (most accurate)
python3 -c "
from src.sensors.bme680 import BME680
from src.sensors.ens160_aht21 import AHT21
bme = BME680()
aht = AHT21()
print(f'BME680: {bme.temperature}°C')
print(f'AHT21: {aht.temperature}°C')
print(f'Offset: {bme.temperature - aht.temperature}°C')
"

# Set offset in .env
BME680_TEMP_OFFSET=-2.5  # Adjust as needed
```

### ENS160 Burn-In Period

ENS160 requires 1 hour initial burn-in and 7 days for full accuracy:

```
Initial 1 hour: Sensor self-calibrating
Days 1-7: Improving accuracy with air exposure
Day 7+: Full accuracy achieved
```

The system tracks this automatically in logs.

## Troubleshooting

### Sensors Not Detected

```bash
# Verify I2C is enabled
i2cdetect -y 1

# Check UART device exists
ls -la /dev/ttyAMA0

# See detailed logs
sudo journalctl -u allergen-alert.service -n 50
```

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

## Performance Notes

- **Single Pi capacity**: Recommended for 1 location, up to 50 HA devices
- **Data retention**: Home Assistant stores history by default, configure retention in HA settings
- **Network**: Requires stable Wi-Fi or Ethernet connection to Proxmox/MQTT broker
- **Power**: ~3-5W typical power consumption (Pi + sensors)
- **CPU**: Minimal load (<5% on Pi 4), background daemon

## Data Privacy & Security

- **Local-first**: All data stays on your local network
- **TLS Encryption**: MQTT uses TLS 1.2+ with certificate authentication
- **No cloud**: No data leaves your home network
- **Open Source**: Full transparency of what the system does

## Future Enhancements

- [ ] Support for additional sensors (Zigbee coordinators, etc.)
- [ ] Advanced analytics with InfluxDB + Grafana
- [ ] Mobile app integration with Home Assistant Companion
- [ ] Machine learning for predictive alerts
- [ ] Multi-room averaging and correlation analysis

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

## License

MIT License - See [LICENSE](LICENSE) for details.

## Support

- **Issues**: Report bugs on [GitHub Issues](https://github.com/yourusername/allergen-alert/issues)
- **Documentation**: See [docs/](docs/) folder
- **Community**: Home Assistant Forums

## References

- [Home Assistant MQTT Documentation](https://www.home-assistant.io/integrations/mqtt/)
- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [Sensor Datasheets](docs/WIRING.md#datasheets)

---

**Start monitoring your air quality now!** 🌍
