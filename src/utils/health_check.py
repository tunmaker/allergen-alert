"""Sensor health monitoring and validation."""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SensorHealth:
    """Health status of a sensor."""

    name: str
    is_healthy: bool
    last_read_time: Optional[float] = None
    last_error: Optional[str] = None
    error_count: int = 0
    consecutive_errors: int = 0
    status_message: str = "Unknown"


class SensorHealthMonitor:
    """Monitor and validate sensor health."""

    def __init__(self, max_consecutive_errors: int = 5):
        """
        Initialize health monitor.

        Args:
            max_consecutive_errors: Mark sensor unhealthy after this many consecutive errors
        """
        self.max_consecutive_errors = max_consecutive_errors
        self.sensors: Dict[str, SensorHealth] = {}

    def register_sensor(self, sensor_name: str):
        """
        Register a sensor for health monitoring.

        Args:
            sensor_name: Name of the sensor
        """
        self.sensors[sensor_name] = SensorHealth(
            name=sensor_name,
            is_healthy=True,
            status_message="Initializing",
        )
        logger.info(f"Registered sensor for health monitoring: {sensor_name}")

    def record_successful_read(self, sensor_name: str):
        """
        Record a successful sensor read.

        Args:
            sensor_name: Name of the sensor
        """
        if sensor_name not in self.sensors:
            self.register_sensor(sensor_name)

        health = self.sensors[sensor_name]
        health.last_read_time = time.time()
        health.consecutive_errors = 0
        health.status_message = "Operational"

        if not health.is_healthy:
            health.is_healthy = True
            logger.info(f"Sensor recovered: {sensor_name}")

    def record_error(self, sensor_name: str, error_msg: str):
        """
        Record a sensor read error.

        Args:
            sensor_name: Name of the sensor
            error_msg: Error message
        """
        if sensor_name not in self.sensors:
            self.register_sensor(sensor_name)

        health = self.sensors[sensor_name]
        health.last_error = error_msg
        health.error_count += 1
        health.consecutive_errors += 1

        if health.consecutive_errors >= self.max_consecutive_errors:
            health.is_healthy = False
            health.status_message = f"Failed ({health.consecutive_errors} errors)"
            logger.error(
                f"Sensor marked unhealthy: {sensor_name} "
                f"({health.consecutive_errors} consecutive errors)"
            )
        else:
            health.status_message = (
                f"Error ({health.consecutive_errors}/{self.max_consecutive_errors})"
            )
            logger.warning(f"Sensor error: {sensor_name} - {error_msg}")

    def get_health(self, sensor_name: str) -> Optional[SensorHealth]:
        """
        Get health status of a sensor.

        Args:
            sensor_name: Name of the sensor

        Returns:
            SensorHealth object or None if not registered
        """
        return self.sensors.get(sensor_name)

    def get_all_health(self) -> Dict[str, SensorHealth]:
        """
        Get health status of all sensors.

        Returns:
            Dictionary of sensor names to health status
        """
        return self.sensors

    def is_sensor_healthy(self, sensor_name: str) -> bool:
        """
        Check if a sensor is healthy.

        Args:
            sensor_name: Name of the sensor

        Returns:
            True if sensor is healthy, False otherwise
        """
        health = self.sensors.get(sensor_name)
        return health.is_healthy if health else False

    def get_healthy_sensors(self) -> list:
        """
        Get list of healthy sensors.

        Returns:
            List of healthy sensor names
        """
        return [name for name, health in self.sensors.items() if health.is_healthy]

    def get_unhealthy_sensors(self) -> list:
        """
        Get list of unhealthy sensors.

        Returns:
            List of unhealthy sensor names
        """
        return [name for name, health in self.sensors.items() if not health.is_healthy]

    def validate_value(
        self,
        sensor_name: str,
        value: float,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> bool:
        """
        Validate a sensor reading is within expected range.

        Args:
            sensor_name: Name of the sensor
            value: Value to validate
            min_val: Minimum acceptable value
            max_val: Maximum acceptable value

        Returns:
            True if value is valid, False otherwise
        """
        if min_val is not None and value < min_val:
            self.record_error(
                sensor_name, f"Value {value} below minimum {min_val}"
            )
            return False

        if max_val is not None and value > max_val:
            self.record_error(
                sensor_name, f"Value {value} exceeds maximum {max_val}"
            )
            return False

        return True

    def get_status_report(self) -> str:
        """
        Generate a health status report.

        Returns:
            Human-readable status report
        """
        lines = ["Sensor Health Status:"]
        lines.append("=" * 50)

        for name, health in self.sensors.items():
            status = "✓ OK" if health.is_healthy else "✗ FAILED"
            lines.append(
                f"{name:20} {status:8} - {health.status_message}"
            )
            if health.last_read_time:
                time_ago = time.time() - health.last_read_time
                lines.append(f"  Last read: {time_ago:.1f}s ago")
            if health.last_error:
                lines.append(f"  Last error: {health.last_error}")

        lines.append("=" * 50)
        healthy_count = len(self.get_healthy_sensors())
        total_count = len(self.sensors)
        lines.append(f"Overall: {healthy_count}/{total_count} sensors healthy")

        return "\n".join(lines)
