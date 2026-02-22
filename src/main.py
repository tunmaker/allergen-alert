"""Main daemon for Allergen Alert air quality monitoring."""

import logging
import os
import signal
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

from mqtt.client import create_mqtt_client_from_env
from mqtt.discovery import DiscoveryPublisher
from sensors.ens160_aht21 import AHT21Sensor, ENS160Sensor
from sensors.pms5003 import PMS5003Sensor
from sensors.scd40 import SCD40Sensor
from sensors.bme680 import BME680Sensor
from sensors.tsl2591 import TSL2591Sensor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.getenv("LOG_FILE", "/var/log/allergen-alert.log")),
    ],
)

logger = logging.getLogger(__name__)


class AllergenAlertDaemon:
    """Main daemon for air quality monitoring."""

    def __init__(self):
        """Initialize the daemon."""
        self.running = False
        self.mqtt_client = None
        self.discovery_publisher = None

        # Sensor instances
        self.aht21 = None
        self.ens160 = None
        self.scd40 = None
        self.bme680 = None
        self.tsl2591 = None
        self.pms5003 = None

        # Configuration
        self.device_id = os.getenv("DEVICE_ID", "rpi_main")
        self.device_name = os.getenv("PI_HOSTNAME", "Raspberry Pi Air Quality Monitor")
        self.simple_sensor_interval = int(os.getenv("SIMPLE_SENSOR_INTERVAL", 300))
        self.air_quality_sensor_interval = int(
            os.getenv("AIR_QUALITY_SENSOR_INTERVAL", 60)
        )
        self.pm_sensor_interval = int(os.getenv("PM_SENSOR_INTERVAL", 300))
        self.sound_sensor_interval = int(os.getenv("SOUND_SENSOR_INTERVAL", 60))

        # Last read times
        self.last_simple_sensor_read = 0
        self.last_air_quality_read = 0
        self.last_pm_read = 0
        self.last_sound_read = 0

    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info(f"Allergen Alert v1.0.0 Starting")
        logger.info(f"Device: {self.device_name} ({self.device_id})")
        logger.info("=" * 60)

        # Initialize MQTT client
        try:
            self.mqtt_client = create_mqtt_client_from_env()
            self.mqtt_client.connect()
            if not self.mqtt_client.wait_for_connection(timeout=10):
                logger.error("Failed to connect to MQTT broker within timeout")
                return False
            logger.info("MQTT connection established")
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            return False

        # Initialize discovery publisher
        self.discovery_publisher = DiscoveryPublisher(
            self.mqtt_client, self.device_id, self.device_name
        )

        # Publish discovery messages
        if not self.discovery_publisher.publish_all_sensor_discoveries():
            logger.warning("Some discovery messages failed to publish")

        # Publish online status
        self.mqtt_client.publish_availability(True)

        # Initialize sensors
        logger.info("Initializing sensors...")
        try:
            self.aht21 = AHT21Sensor()
            self.ens160 = ENS160Sensor()
            self.scd40 = SCD40Sensor(measurement_interval=1)
            self.bme680 = BME680Sensor()
            self.tsl2591 = TSL2591Sensor()
            self.pms5003 = PMS5003Sensor()
            logger.info("All sensors initialized")
        except Exception as e:
            logger.error(f"Error initializing sensors: {e}")
            return False

        return True

    def read_sensors(self):
        """Read all sensors and publish data."""
        now = time.time()

        # Simple sensors (low frequency: BME680, TSL2591)
        if now - self.last_simple_sensor_read >= self.simple_sensor_interval:
            self._read_simple_sensors()
            self.last_simple_sensor_read = now

        # Air quality sensors (high frequency: AHT21, ENS160, SCD40)
        if now - self.last_air_quality_read >= self.air_quality_sensor_interval:
            self._read_air_quality_sensors()
            self.last_air_quality_read = now

        # PM sensor (low frequency due to duty cycle)
        if now - self.last_pm_read >= self.pm_sensor_interval:
            self._read_pm_sensor()
            self.last_pm_read = now

    def _read_simple_sensors(self):
        """Read BME680 and TSL2591."""
        # BME680
        if self.bme680:
            try:
                data = self.bme680.read()
                if data:
                    self.mqtt_client.publish_data("temperature_bme680", data["temperature"])
                    self.mqtt_client.publish_data("humidity_bme680", data["humidity"])
                    self.mqtt_client.publish_data("pressure", data["pressure"])
                    self.mqtt_client.publish_data("gas_resistance", data["gas_resistance"])
            except Exception as e:
                logger.error(f"Error reading BME680: {e}")

        # TSL2591
        if self.tsl2591:
            try:
                data = self.tsl2591.read()
                if data:
                    self.mqtt_client.publish_data("light", data["lux"])
            except Exception as e:
                logger.error(f"Error reading TSL2591: {e}")

    def _read_air_quality_sensors(self):
        """Read AHT21, ENS160, SCD40."""
        # AHT21
        if self.aht21:
            try:
                data = self.aht21.read()
                if data:
                    self.mqtt_client.publish_data("temperature", data["temperature"])
                    self.mqtt_client.publish_data("humidity", data["humidity"])
            except Exception as e:
                logger.error(f"Error reading AHT21: {e}")

        # ENS160
        if self.ens160:
            try:
                data = self.ens160.read()
                if data:
                    self.mqtt_client.publish_data("aqi", data["aqi"])
                    self.mqtt_client.publish_data("tvoc", data["tvoc"])
                    self.mqtt_client.publish_data("eco2", data["eco2"])
                    logger.debug(
                        f"ENS160: AQI={data['aqi']}, eCO2={data['eco2']} ppm, "
                        f"TVOC={data['tvoc']} ppb ({data['burn_in_status']})"
                    )
            except Exception as e:
                logger.error(f"Error reading ENS160: {e}")

        # SCD40
        if self.scd40:
            try:
                data = self.scd40.read()
                if data:
                    self.mqtt_client.publish_data("co2", data["co2"])
                    logger.debug(f"SCD40: CO2={data['co2']} ppm")
            except Exception as e:
                logger.error(f"Error reading SCD40: {e}")

    def _read_pm_sensor(self):
        """Read PMS5003."""
        if self.pms5003:
            try:
                data = self.pms5003.read()
                if data:
                    self.mqtt_client.publish_data("pm1_0", data["pm1_0"])
                    self.mqtt_client.publish_data("pm2_5", data["pm2_5"])
                    self.mqtt_client.publish_data("pm10", data["pm10"])
                    logger.debug(
                        f"PMS5003: PM1.0={data['pm1_0']}, PM2.5={data['pm2_5']}, "
                        f"PM10={data['pm10']} µg/m³"
                    )
            except Exception as e:
                logger.error(f"Error reading PMS5003: {e}")

    def run(self):
        """Main event loop."""
        self.running = True
        logger.info("Starting main event loop")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Main loop
        while self.running:
            try:
                self.read_sensors()
                time.sleep(1)  # Check every second
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                self.stop()
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying

    def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self.running = False

        # Publish offline status
        if self.mqtt_client:
            self.mqtt_client.publish_availability(False)
            self.mqtt_client.disconnect()

        # Close sensors
        sensors_to_close = [
            self.aht21,
            self.ens160,
            self.scd40,
            self.bme680,
            self.tsl2591,
            self.pms5003,
        ]
        for sensor in sensors_to_close:
            if sensor:
                try:
                    sensor.close()
                except Exception as e:
                    logger.error(f"Error closing sensor: {e}")

        logger.info("Daemon stopped")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point."""
    daemon = AllergenAlertDaemon()

    if not daemon.initialize():
        logger.error("Failed to initialize daemon")
        sys.exit(1)

    try:
        daemon.run()
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
