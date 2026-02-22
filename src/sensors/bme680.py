"""BME680 4-in-1 Environmental Sensor Driver."""

import logging
import os
from typing import Dict, Optional

try:
    import board
    import busio
    import adafruit_bme680
except ImportError:
    adafruit_bme680 = None

logger = logging.getLogger(__name__)


class BME680Sensor:
    """BME680 environmental sensor (temperature, humidity, pressure, gas)."""

    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_address: int = 0x76,
        sea_level_pressure: float = 1013.25,
        temp_offset: float = 0,
    ):
        """
        Initialize BME680 sensor.

        Args:
            i2c_bus: I2C bus number (default 1 on Raspberry Pi)
            i2c_address: I2C address (0x76 or 0x77)
            sea_level_pressure: Sea level pressure for altitude calculation
            temp_offset: Temperature offset correction in °C
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.sea_level_pressure = sea_level_pressure
        self.temp_offset = float(os.getenv("BME680_TEMP_OFFSET", temp_offset))

        self.sensor = None
        self.initialized = False

        self._initialize()

    def _initialize(self):
        """Initialize the BME680 sensor."""
        if adafruit_bme680 is None:
            logger.warning("adafruit_bme680 not installed, sensor will not function")
            return

        try:
            # Use SMBus for I2C communication on Raspberry Pi
            import smbus2

            self.i2c = smbus2.SMBus(self.i2c_bus)
            self.sensor = adafruit_bme680.Adafruit_BME680_I2C(
                i2c=self.i2c, address=self.i2c_address
            )

            # Configure sensor settings
            self.sensor.sea_level_pressure = self.sea_level_pressure

            self.initialized = True
            logger.info(f"BME680 initialized at address 0x{self.i2c_address:02x}")
        except Exception as e:
            logger.error(f"Failed to initialize BME680: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read sensor data.

        Returns:
            Dict with keys: temperature, humidity, pressure, gas_resistance
            or None if read failed
        """
        if not self.initialized or self.sensor is None:
            logger.warning("BME680 not initialized")
            return None

        try:
            # Read all values
            temperature = self.sensor.temperature + self.temp_offset
            humidity = self.sensor.humidity
            pressure = self.sensor.pressure
            gas_resistance = self.sensor.gas

            return {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
                "pressure": round(pressure, 2),
                "gas_resistance": round(gas_resistance, 0),
            }
        except Exception as e:
            logger.error(f"Error reading BME680: {e}")
            return None

    def read_temperature(self) -> Optional[float]:
        """Read temperature in °C."""
        data = self.read()
        return data["temperature"] if data else None

    def read_humidity(self) -> Optional[float]:
        """Read humidity in %."""
        data = self.read()
        return data["humidity"] if data else None

    def read_pressure(self) -> Optional[float]:
        """Read pressure in hPa."""
        data = self.read()
        return data["pressure"] if data else None

    def read_gas_resistance(self) -> Optional[float]:
        """Read gas resistance in Ohms."""
        data = self.read()
        return data["gas_resistance"] if data else None

    def set_temp_offset(self, offset: float):
        """Set temperature offset correction."""
        self.temp_offset = offset
        logger.info(f"BME680 temperature offset set to {offset}°C")

    def close(self):
        """Close the sensor connection."""
        if hasattr(self, "i2c"):
            try:
                self.i2c.close()
                logger.info("BME680 connection closed")
            except Exception as e:
                logger.error(f"Error closing BME680: {e}")


# Convenience function for testing
def test_bme680():
    """Test BME680 sensor."""
    sensor = BME680Sensor()
    if sensor.initialized:
        data = sensor.read()
        print(f"BME680 Data: {data}")
        sensor.close()
    else:
        print("BME680 initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_bme680()
