"""Home Assistant MQTT Discovery message generation."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class HADiscoveryMessage:
    """Generate Home Assistant MQTT discovery messages."""

    # Supported device classes and their attributes
    DEVICE_CLASSES = {
        "temperature": {
            "name": "Temperature",
            "unit_of_measurement": "°C",
            "icon": "mdi:thermometer",
            "value_template": "{{ value }}",
        },
        "humidity": {
            "name": "Humidity",
            "unit_of_measurement": "%",
            "icon": "mdi:water-percent",
            "value_template": "{{ value }}",
        },
        "pressure": {
            "name": "Pressure",
            "unit_of_measurement": "hPa",
            "icon": "mdi:gauge",
            "value_template": "{{ value }}",
        },
        "pm25": {
            "name": "Particulate Matter 2.5",
            "unit_of_measurement": "µg/m³",
            "icon": "mdi:air-filter",
            "device_class": "pm25",
            "value_template": "{{ value }}",
        },
        "pm10": {
            "name": "Particulate Matter 10",
            "unit_of_measurement": "µg/m³",
            "icon": "mdi:air-filter",
            "device_class": "pm10",
            "value_template": "{{ value }}",
        },
        "pm1": {
            "name": "Particulate Matter 1.0",
            "unit_of_measurement": "µg/m³",
            "icon": "mdi:air-filter",
            "value_template": "{{ value }}",
        },
        "co2": {
            "name": "Carbon Dioxide",
            "unit_of_measurement": "ppm",
            "icon": "mdi:air-filter",
            "value_template": "{{ value }}",
        },
        "eco2": {
            "name": "Estimated CO2",
            "unit_of_measurement": "ppm",
            "icon": "mdi:air-filter",
            "value_template": "{{ value }}",
        },
        "tvoc": {
            "name": "Total VOC",
            "unit_of_measurement": "ppb",
            "icon": "mdi:air-filter",
            "value_template": "{{ value }}",
        },
        "aqi": {
            "name": "Air Quality Index",
            "unit_of_measurement": "AQI",
            "icon": "mdi:air-filter",
            "device_class": "aqi",
            "value_template": "{{ value }}",
        },
        "light": {
            "name": "Light Intensity",
            "unit_of_measurement": "lux",
            "icon": "mdi:lightbulb",
            "value_template": "{{ value }}",
        },
        "sound": {
            "name": "Sound Level",
            "unit_of_measurement": "dBA",
            "icon": "mdi:microphone",
            "value_template": "{{ value }}",
        },
        "gas": {
            "name": "Gas Resistance",
            "unit_of_measurement": "Ω",
            "icon": "mdi:gas-cylinder",
            "value_template": "{{ value }}",
        },
    }

    @staticmethod
    def create_sensor_discovery(
        device_id: str,
        sensor_type: str,
        sensor_id: str = None,
        device_name: str = "Air Quality Monitor",
        device_model: str = "Raspberry Pi 4B",
        device_manufacturer: str = "Raspberry Pi Foundation",
        custom_name: str = None,
        custom_unit: str = None,
        custom_icon: str = None,
        value_template: str = None,
    ) -> Dict:
        """
        Create a sensor discovery message for Home Assistant.

        Args:
            device_id: Device identifier (e.g., 'rpi_main')
            sensor_type: Sensor type (temperature, humidity, pm25, co2, etc.)
            sensor_id: Sensor ID (if None, uses sensor_type)
            device_name: Human-readable device name
            device_model: Device model
            device_manufacturer: Device manufacturer
            custom_name: Override the default sensor name
            custom_unit: Override the default unit of measurement
            custom_icon: Override the default icon
            value_template: Override the default value template

        Returns:
            Discovery message dict
        """
        if sensor_id is None:
            sensor_id = sensor_type

        # Get defaults from DEVICE_CLASSES
        if sensor_type not in HADiscoveryMessage.DEVICE_CLASSES:
            logger.warning(f"Unknown sensor type: {sensor_type}")
            return {}

        defaults = HADiscoveryMessage.DEVICE_CLASSES[sensor_type].copy()

        # Build discovery message
        discovery = {
            "unique_id": f"{device_id}_{sensor_id}",
            "object_id": f"{device_id}_{sensor_id}",
            "name": custom_name or defaults.get("name"),
            "state_topic": f"home/rpi_aq/{sensor_id}/state",
            "availability_topic": "home/rpi_aq/availability",
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": {
                "identifiers": [device_id],
                "name": device_name,
                "model": device_model,
                "manufacturer": device_manufacturer,
            },
        }

        # Add optional fields
        if custom_unit or "unit_of_measurement" in defaults:
            discovery["unit_of_measurement"] = custom_unit or defaults.get(
                "unit_of_measurement"
            )

        if custom_icon or "icon" in defaults:
            discovery["icon"] = custom_icon or defaults.get("icon")

        if "device_class" in defaults:
            discovery["device_class"] = defaults["device_class"]

        if value_template or "value_template" in defaults:
            discovery["value_template"] = value_template or defaults.get("value_template")

        return discovery

    @staticmethod
    def create_all_sensor_discoveries(
        device_id: str,
        device_name: str = "Air Quality Monitor",
    ) -> Dict[str, Dict]:
        """
        Create discovery messages for all supported sensors.

        Args:
            device_id: Device identifier
            device_name: Human-readable device name

        Returns:
            Dict of sensor_type -> discovery_message
        """
        discoveries = {}

        sensor_configs = [
            ("temperature", "Temperature (AHT21)"),
            ("humidity", "Humidity (AHT21)"),
            ("pressure", "Atmospheric Pressure"),
            ("pm1", "Particulate Matter 1.0"),
            ("pm25", "Particulate Matter 2.5"),
            ("pm10", "Particulate Matter 10"),
            ("co2", "Carbon Dioxide (SCD40)"),
            ("eco2", "Estimated CO2 (ENS160)"),
            ("tvoc", "Total VOCs"),
            ("aqi", "Air Quality Index"),
            ("light", "Light Intensity"),
            ("sound", "Sound Level"),
            ("gas", "Gas Resistance"),
        ]

        for sensor_type, custom_name in sensor_configs:
            discovery = HADiscoveryMessage.create_sensor_discovery(
                device_id=device_id,
                sensor_type=sensor_type,
                device_name=device_name,
                custom_name=custom_name,
            )
            if discovery:
                discoveries[sensor_type] = discovery

        return discoveries


class DiscoveryPublisher:
    """Publish Home Assistant MQTT discovery messages."""

    def __init__(self, mqtt_client, device_id: str, device_name: str = None):
        """
        Initialize discovery publisher.

        Args:
            mqtt_client: MQTTClient instance
            device_id: Device identifier
            device_name: Human-readable device name
        """
        self.mqtt_client = mqtt_client
        self.device_id = device_id
        self.device_name = device_name or "Air Quality Monitor"
        self.published_sensors = set()

    def publish_sensor_discovery(
        self,
        sensor_type: str,
        sensor_id: str = None,
        custom_name: str = None,
        custom_unit: str = None,
        custom_icon: str = None,
    ) -> bool:
        """
        Publish discovery message for a sensor.

        Args:
            sensor_type: Type of sensor (temperature, humidity, pm25, etc.)
            sensor_id: Sensor ID (if None, uses sensor_type)
            custom_name: Override default sensor name
            custom_unit: Override default unit
            custom_icon: Override default icon

        Returns:
            True if published successfully
        """
        if sensor_id is None:
            sensor_id = sensor_type

        discovery = HADiscoveryMessage.create_sensor_discovery(
            device_id=self.device_id,
            sensor_type=sensor_type,
            sensor_id=sensor_id,
            device_name=self.device_name,
            custom_name=custom_name,
            custom_unit=custom_unit,
            custom_icon=custom_icon,
        )

        if not discovery:
            return False

        # Publish via mqtt_client's publish_discovery method
        success = self.mqtt_client.publish_discovery(
            self.device_id, sensor_id, discovery
        )

        if success:
            self.published_sensors.add(sensor_id)
            logger.info(f"Published discovery for sensor: {sensor_type}")
        else:
            logger.error(f"Failed to publish discovery for sensor: {sensor_type}")

        return success

    def publish_all_sensor_discoveries(self) -> bool:
        """
        Publish discovery messages for all standard sensors.

        Returns:
            True if all successfully published
        """
        sensor_types = [
            "temperature",
            "humidity",
            "pressure",
            "pm1",
            "pm25",
            "pm10",
            "co2",
            "eco2",
            "tvoc",
            "aqi",
            "light",
            "sound",
            "gas",
        ]

        all_success = True
        for sensor_type in sensor_types:
            if not self.publish_sensor_discovery(sensor_type):
                all_success = False

        return all_success
