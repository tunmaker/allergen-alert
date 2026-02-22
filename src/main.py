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
from utils.health_check import SensorHealthMonitor
from utils.data_aggregation import TemperatureAggregator, HumidityAggregator
from utils.calibration import CalibrationManager, ENS160BurnInTracker, SCD40CalibrationTracker
from utils.data_processing import (
    MovingAverageFilter,
    AQICalculator,
    MultiSensorAQI,
)
from utils.duty_cycle import PMS5003DutyCycleManager, DutyCycleScheduler

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

        # Health monitoring
        self.health_monitor = SensorHealthMonitor(max_consecutive_errors=5)

        # Data aggregation
        self.temp_aggregator = TemperatureAggregator(use_offsets=True)
        self.humidity_aggregator = HumidityAggregator()

        # Phase 3: Calibration and optimization
        self.calibration_manager = CalibrationManager()
        self.ens160_tracker = None  # Initialized in initialize()
        self.scd40_tracker = None  # Initialized in initialize()
        self.pms5003_duty_cycle = None  # Initialized in initialize()
        self.duty_cycle_scheduler = None  # Initialized in initialize()

        # Data processing
        self.pm_moving_average = MovingAverageFilter(window_size=5)
        self.multi_sensor_aqi = MultiSensorAQI()

        # Configuration
        self.device_id = os.getenv("DEVICE_ID", "rpi_main")
        self.device_name = os.getenv("PI_HOSTNAME", "Raspberry Pi Air Quality Monitor")
        self.simple_sensor_interval = int(os.getenv("SIMPLE_SENSOR_INTERVAL", 300))
        self.air_quality_sensor_interval = int(
            os.getenv("AIR_QUALITY_SENSOR_INTERVAL", 60)
        )
        self.pm_sensor_interval = int(os.getenv("PM_SENSOR_INTERVAL", 300))
        self.sound_sensor_interval = int(os.getenv("SOUND_SENSOR_INTERVAL", 60))
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", 600))

        # Last read times
        self.last_simple_sensor_read = 0
        self.last_air_quality_read = 0
        self.last_pm_read = 0
        self.last_sound_read = 0
        self.last_health_check = 0

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

        # Initialize Phase 3 components (calibration and optimization)
        logger.info("Initializing calibration and optimization...")
        try:
            self.ens160_tracker = ENS160BurnInTracker(self.calibration_manager)
            self.scd40_tracker = SCD40CalibrationTracker(self.calibration_manager)
            self.pms5003_duty_cycle = PMS5003DutyCycleManager(
                pattern=os.getenv("PMS5003_DUTY_CYCLE_PATTERN", "extended")
            )
            self.duty_cycle_scheduler = DutyCycleScheduler(self.pms5003_duty_cycle)
            logger.info("Calibration and optimization initialized")
            logger.info(self.ens160_tracker.get_status_report())
            logger.info(self.pms5003_duty_cycle.get_status_report())
        except Exception as e:
            logger.error(f"Error initializing Phase 3 components: {e}")
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
            self._publish_aqi()  # Publish comprehensive AQI after reading sensors
            self.last_air_quality_read = now

        # PM sensor (low frequency due to duty cycle)
        if now - self.last_pm_read >= self.pm_sensor_interval:
            self._read_pm_sensor()
            self.last_pm_read = now

        # Health check (periodic monitoring)
        if now - self.last_health_check >= self.health_check_interval:
            self._perform_health_check()
            self.last_health_check = now

    def _read_simple_sensors(self):
        """Read BME680 and TSL2591."""
        # BME680
        if self.bme680:
            try:
                data = self.bme680.read()
                if data:
                    self.health_monitor.record_successful_read("bme680")
                    self.mqtt_client.publish_data("temperature_bme680", data["temperature"])
                    self.mqtt_client.publish_data("humidity_bme680", data["humidity"])
                    self.mqtt_client.publish_data("pressure", data["pressure"])
                    self.mqtt_client.publish_data("gas_resistance", data["gas_resistance"])
                    # Add to aggregators
                    self.temp_aggregator.add_reading("temperature_bme680", data["temperature"])
                    self.humidity_aggregator.add_reading("humidity_bme680", data["humidity"])
            except Exception as e:
                logger.error(f"Error reading BME680: {e}")
                self.health_monitor.record_error("bme680", str(e))

        # TSL2591
        if self.tsl2591:
            try:
                data = self.tsl2591.read()
                if data:
                    self.health_monitor.record_successful_read("tsl2591")
                    self.mqtt_client.publish_data("light", data["lux"])
            except Exception as e:
                logger.error(f"Error reading TSL2591: {e}")
                self.health_monitor.record_error("tsl2591", str(e))

    def _read_air_quality_sensors(self):
        """Read AHT21, ENS160, SCD40."""
        # AHT21
        if self.aht21:
            try:
                data = self.aht21.read()
                if data:
                    self.health_monitor.record_successful_read("aht21")
                    self.mqtt_client.publish_data("temperature", data["temperature"])
                    self.mqtt_client.publish_data("humidity", data["humidity"])
                    # Add to aggregators (AHT21 is reference, no offset)
                    self.temp_aggregator.add_reading("temperature", data["temperature"])
                    self.humidity_aggregator.add_reading("humidity", data["humidity"])
            except Exception as e:
                logger.error(f"Error reading AHT21: {e}")
                self.health_monitor.record_error("aht21", str(e))

        # ENS160
        if self.ens160:
            try:
                data = self.ens160.read()
                if data:
                    self.health_monitor.record_successful_read("ens160")
                    self.mqtt_client.publish_data("aqi", data["aqi"])
                    self.mqtt_client.publish_data("tvoc", data["tvoc"])
                    self.mqtt_client.publish_data("eco2", data["eco2"])

                    # Track ENS160 burn-in status
                    if self.ens160_tracker:
                        accuracy = self.ens160_tracker.get_accuracy_level()
                        progress = self.ens160_tracker.get_burn_in_progress()
                        self.mqtt_client.publish_data("ens160_accuracy", accuracy)
                        self.mqtt_client.publish_data("ens160_burn_in_progress", progress)

                    # Update multi-sensor AQI with TVOC
                    self.multi_sensor_aqi.update(tvoc=data["tvoc"])

                    logger.debug(
                        f"ENS160: AQI={data['aqi']}, eCO2={data['eco2']} ppm, "
                        f"TVOC={data['tvoc']} ppb (accuracy: {self.ens160_tracker.get_accuracy_level() if self.ens160_tracker else 'unknown'})"
                    )
            except Exception as e:
                logger.error(f"Error reading ENS160: {e}")
                self.health_monitor.record_error("ens160", str(e))

        # SCD40
        if self.scd40:
            try:
                data = self.scd40.read()
                if data:
                    self.health_monitor.record_successful_read("scd40")
                    co2 = data["co2"]
                    self.mqtt_client.publish_data("co2", co2)

                    # Track SCD40 calibration status
                    if self.scd40_tracker:
                        if self.scd40_tracker.needs_recalibration():
                            logger.warning(
                                "SCD40 needs fresh air exposure for calibration. "
                                "Expose to outdoor air for 10-15 minutes."
                            )

                    # Add temperature reading if available (SCD40 includes temperature)
                    if "temperature" in data:
                        self.temp_aggregator.add_reading("temperature_scd40", data["temperature"])
                    if "humidity" in data:
                        self.humidity_aggregator.add_reading("humidity_scd40", data["humidity"])

                    # Update multi-sensor AQI with CO2
                    self.multi_sensor_aqi.update(co2=co2)

                    logger.debug(f"SCD40: CO2={co2:.0f} ppm")
            except Exception as e:
                logger.error(f"Error reading SCD40: {e}")
                self.health_monitor.record_error("scd40", str(e))

        # Publish temperature and humidity consensus
        self._publish_sensor_consensus()

    def _read_pm_sensor(self):
        """Read PMS5003 with duty cycle management and moving average filtering."""
        # Check duty cycle state change
        if self.duty_cycle_scheduler:
            self.duty_cycle_scheduler.check_and_log_state_change()

        # Only read if laser is on
        if self.pms5003_duty_cycle and not self.pms5003_duty_cycle.should_laser_be_on():
            logger.debug("PMS5003 laser in rest mode, skipping read")
            return

        if self.pms5003:
            try:
                data = self.pms5003.read()
                if data:
                    self.health_monitor.record_successful_read("pms5003")

                    # Apply moving average filter to smooth noisy PM data
                    pm1_avg = self.pm_moving_average.add_reading(data["pm1_0"])
                    pm2_5 = data["pm2_5"]
                    pm10 = data["pm10"]

                    # Publish raw readings
                    self.mqtt_client.publish_data("pm1_0", data["pm1_0"])
                    self.mqtt_client.publish_data("pm2_5", pm2_5)
                    self.mqtt_client.publish_data("pm10", pm10)

                    # Publish smoothed PM1.0 if filter is ready
                    if self.pm_moving_average.is_ready():
                        self.mqtt_client.publish_data("pm1_0_smoothed", pm1_avg)

                    # Update multi-sensor AQI with PM2.5
                    self.multi_sensor_aqi.update(pm2_5=pm2_5)

                    logger.debug(
                        f"PMS5003: PM1.0={data['pm1_0']:.1f}, PM2.5={pm2_5:.1f}, "
                        f"PM10={pm10:.1f} µg/m³"
                    )
            except Exception as e:
                logger.error(f"Error reading PMS5003: {e}")
                self.health_monitor.record_error("pms5003", str(e))

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

    def _publish_sensor_consensus(self):
        """Publish temperature and humidity consensus."""
        # Temperature consensus
        consensus_temp = self.temp_aggregator.get_consensus_temperature()
        if consensus_temp is not None:
            self.mqtt_client.publish_data("temperature_consensus", consensus_temp)
            logger.debug(f"Published temperature consensus: {consensus_temp}°C")

        # Humidity consensus
        consensus_humidity = self.humidity_aggregator.get_consensus_humidity()
        if consensus_humidity is not None:
            self.mqtt_client.publish_data("humidity_consensus", consensus_humidity)
            logger.debug(f"Published humidity consensus: {consensus_humidity}%")

        # Clear aggregators for next reading
        self.temp_aggregator.clear()
        self.humidity_aggregator.clear()

    def _perform_health_check(self):
        """Perform periodic health check of sensors."""
        logger.info("Performing health check...")
        logger.info(self.health_monitor.get_status_report())

        # Publish health status to MQTT
        unhealthy = self.health_monitor.get_unhealthy_sensors()
        if unhealthy:
            logger.warning(f"Unhealthy sensors: {', '.join(unhealthy)}")
            self.mqtt_client.publish_data("unhealthy_sensors", ",".join(unhealthy))
        else:
            self.mqtt_client.publish_data("unhealthy_sensors", "none")

        # Publish calibration and optimization status
        if self.ens160_tracker:
            logger.info(self.ens160_tracker.get_status_report())

        if self.scd40_tracker:
            days_since = self.scd40_tracker.get_days_since_calibration()
            if days_since is not None:
                self.mqtt_client.publish_data("scd40_days_since_calibration", days_since)

        if self.pms5003_duty_cycle:
            logger.info(self.pms5003_duty_cycle.get_status_report())

    def _publish_aqi(self):
        """Publish comprehensive AQI information."""
        overall_aqi = self.multi_sensor_aqi.calculate_overall_aqi()
        if overall_aqi is not None:
            self.mqtt_client.publish_data("overall_aqi", overall_aqi)
            logger.debug(f"Published overall AQI: {overall_aqi}")

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
