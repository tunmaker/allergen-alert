"""Data aggregation and sensor consensus calculations."""

import logging
import statistics
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TemperatureAggregator:
    """
    Aggregate temperature readings from multiple sensors.

    The Raspberry Pi's CPU heat can affect sensor readings:
    - BME680: Often reads 2-5°C high due to proximity to CPU
    - SCD40: Moderate impact, typically 1-3°C high
    - AHT21: Most accurate reference, minimal CPU heat effect
    """

    # Known temperature offsets (positive = sensor reads too high)
    TEMPERATURE_OFFSETS = {
        "temperature_bme680": 3.0,  # BME680 typically reads 3°C high
        "temperature_scd40": 1.5,   # SCD40 typically reads 1.5°C high
        "temperature": 0.0,          # AHT21 is the reference (0°C offset)
    }

    def __init__(self, use_offsets: bool = True):
        """
        Initialize temperature aggregator.

        Args:
            use_offsets: Apply known temperature offsets when calculating consensus
        """
        self.use_offsets = use_offsets
        self.readings: Dict[str, float] = {}

    def add_reading(self, sensor_name: str, temperature: float):
        """
        Add a temperature reading.

        Args:
            sensor_name: Name of the sensor (must match TEMPERATURE_OFFSETS keys)
            temperature: Temperature reading in Celsius
        """
        self.readings[sensor_name] = temperature
        logger.debug(f"Temperature: {sensor_name} = {temperature:.2f}°C")

    def get_corrected_temperature(self, sensor_name: str) -> Optional[float]:
        """
        Get temperature reading with offset correction applied.

        Args:
            sensor_name: Name of the sensor

        Returns:
            Corrected temperature or None if sensor not in readings
        """
        if sensor_name not in self.readings:
            return None

        raw_temp = self.readings[sensor_name]
        offset = self.TEMPERATURE_OFFSETS.get(sensor_name, 0.0) if self.use_offsets else 0.0
        corrected = raw_temp - offset

        return round(corrected, 2)

    def get_consensus_temperature(self) -> Optional[float]:
        """
        Calculate consensus temperature using median of corrected readings.

        Only includes readings from sensors with valid offsets.

        Returns:
            Median temperature (corrected) or None if no valid readings
        """
        corrected_temps = []

        for sensor_name, temp in self.readings.items():
            if sensor_name in self.TEMPERATURE_OFFSETS:
                corrected = self.get_corrected_temperature(sensor_name)
                if corrected is not None:
                    corrected_temps.append(corrected)

        if not corrected_temps:
            logger.warning("No valid temperature readings for consensus")
            return None

        consensus = statistics.median(corrected_temps)
        logger.debug(
            f"Temperature consensus: {consensus:.2f}°C "
            f"(from {len(corrected_temps)} sensors: {corrected_temps})"
        )
        return round(consensus, 2)

    def get_average_temperature(self) -> Optional[float]:
        """
        Calculate average temperature using mean of corrected readings.

        Returns:
            Mean temperature (corrected) or None if no valid readings
        """
        corrected_temps = []

        for sensor_name, temp in self.readings.items():
            if sensor_name in self.TEMPERATURE_OFFSETS:
                corrected = self.get_corrected_temperature(sensor_name)
                if corrected is not None:
                    corrected_temps.append(corrected)

        if not corrected_temps:
            return None

        average = statistics.mean(corrected_temps)
        return round(average, 2)

    def get_temperature_range(self) -> Optional[tuple]:
        """
        Get min and max corrected temperatures.

        Returns:
            Tuple of (min_temp, max_temp) or None if no valid readings
        """
        corrected_temps = []

        for sensor_name, temp in self.readings.items():
            if sensor_name in self.TEMPERATURE_OFFSETS:
                corrected = self.get_corrected_temperature(sensor_name)
                if corrected is not None:
                    corrected_temps.append(corrected)

        if not corrected_temps:
            return None

        return (min(corrected_temps), max(corrected_temps))

    def get_temperature_report(self) -> str:
        """
        Get a detailed temperature report.

        Returns:
            Human-readable temperature report
        """
        lines = ["Temperature Report:"]
        lines.append("=" * 50)

        for sensor_name in sorted(self.TEMPERATURE_OFFSETS.keys()):
            if sensor_name in self.readings:
                raw_temp = self.readings[sensor_name]
                corrected = self.get_corrected_temperature(sensor_name)
                offset = self.TEMPERATURE_OFFSETS.get(sensor_name, 0.0)

                lines.append(
                    f"{sensor_name:25} Raw: {raw_temp:6.2f}°C "
                    f"Offset: {offset:+.1f}°C → {corrected:6.2f}°C"
                )
            else:
                lines.append(f"{sensor_name:25} (No reading)")

        lines.append("=" * 50)
        consensus = self.get_consensus_temperature()
        if consensus is not None:
            lines.append(f"Consensus Temperature: {consensus:.2f}°C (median)")

        temp_range = self.get_temperature_range()
        if temp_range:
            lines.append(f"Temperature Range: {temp_range[0]:.2f}°C to {temp_range[1]:.2f}°C")

        return "\n".join(lines)

    def clear(self):
        """Clear all readings."""
        self.readings.clear()


class HumidityAggregator:
    """
    Aggregate humidity readings from multiple sensors.

    Humidity accuracy varies by sensor:
    - AHT21: ±2% RH (best)
    - BME680: ±3% RH
    - SCD40: ±6% RH (least accurate for humidity)
    """

    # Sensor accuracy weights (higher = more trusted)
    HUMIDITY_WEIGHTS = {
        "humidity": 3,          # AHT21: ±2% RH (best)
        "humidity_bme680": 2,   # BME680: ±3% RH
        "humidity_scd40": 1,    # SCD40: ±6% RH (least accurate)
    }

    def __init__(self):
        """Initialize humidity aggregator."""
        self.readings: Dict[str, float] = {}

    def add_reading(self, sensor_name: str, humidity: float):
        """
        Add a humidity reading.

        Args:
            sensor_name: Name of the sensor
            humidity: Humidity reading in % RH
        """
        if not 0 <= humidity <= 100:
            logger.warning(
                f"Invalid humidity reading: {sensor_name} = {humidity}% "
                "(expected 0-100%)"
            )
            return

        self.readings[sensor_name] = humidity
        logger.debug(f"Humidity: {sensor_name} = {humidity:.1f}%")

    def get_consensus_humidity(self) -> Optional[float]:
        """
        Calculate weighted consensus humidity.

        Uses weighting based on sensor accuracy.

        Returns:
            Weighted consensus humidity or None if no valid readings
        """
        if not self.readings:
            logger.warning("No humidity readings for consensus")
            return None

        total_weight = 0
        weighted_sum = 0

        for sensor_name, humidity in self.readings.items():
            weight = self.HUMIDITY_WEIGHTS.get(sensor_name, 1)
            weighted_sum += humidity * weight
            total_weight += weight

        if total_weight == 0:
            return None

        consensus = weighted_sum / total_weight
        logger.debug(
            f"Humidity consensus: {consensus:.1f}% "
            f"(weighted from {len(self.readings)} sensors)"
        )
        return round(consensus, 1)

    def get_humidity_report(self) -> str:
        """
        Get a detailed humidity report.

        Returns:
            Human-readable humidity report
        """
        lines = ["Humidity Report:"]
        lines.append("=" * 50)

        for sensor_name in sorted(self.HUMIDITY_WEIGHTS.keys()):
            if sensor_name in self.readings:
                humidity = self.readings[sensor_name]
                weight = self.HUMIDITY_WEIGHTS.get(sensor_name, 1)
                lines.append(
                    f"{sensor_name:25} {humidity:6.1f}% (weight: {weight})"
                )
            else:
                lines.append(f"{sensor_name:25} (No reading)")

        lines.append("=" * 50)
        consensus = self.get_consensus_humidity()
        if consensus is not None:
            lines.append(f"Consensus Humidity: {consensus:.1f}%")

        return "\n".join(lines)

    def clear(self):
        """Clear all readings."""
        self.readings.clear()
