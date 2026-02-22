"""TSL2591 Light Sensor Driver."""

import logging
import time
from typing import Dict, Optional

try:
    import board
    import busio
    import adafruit_tsl2591
except ImportError:
    adafruit_tsl2591 = None

logger = logging.getLogger(__name__)


class TSL2591Sensor:
    """TSL2591 light sensor."""

    def __init__(self, i2c_bus: int = 1, i2c_address: int = 0x29):
        """
        Initialize TSL2591 sensor.

        Args:
            i2c_bus: I2C bus number (default 1 on Raspberry Pi)
            i2c_address: I2C address (default 0x29)
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        self.sensor = None
        self.initialized = False

        self._initialize()

    def _initialize(self):
        """Initialize the TSL2591 sensor."""
        if adafruit_tsl2591 is None:
            logger.warning("adafruit_tsl2591 not installed, sensor will not function")
            return

        try:
            # Use SMBus for I2C communication on Raspberry Pi
            import smbus2

            self.i2c = smbus2.SMBus(self.i2c_bus)
            self.sensor = adafruit_tsl2591.Adafruit_TSL2591(
                i2c_bus=self.i2c, address=self.i2c_address
            )

            # Give sensor time to initialize
            time.sleep(0.1)

            self.initialized = True
            logger.info(f"TSL2591 initialized at address 0x{self.i2c_address:02x}")
        except Exception as e:
            logger.error(f"Failed to initialize TSL2591: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read sensor data.

        Returns:
            Dict with keys: lux, ir, full_spectrum
            or None if read failed
        """
        if not self.initialized or self.sensor is None:
            logger.warning("TSL2591 not initialized")
            return None

        try:
            # Read light data
            lux = self.sensor.lux
            infrared = self.sensor.infrared
            full_spectrum = self.sensor.full_spectrum

            return {
                "lux": round(lux, 2),
                "infrared": round(infrared, 0),
                "full_spectrum": round(full_spectrum, 0),
            }
        except Exception as e:
            logger.error(f"Error reading TSL2591: {e}")
            return None

    def read_lux(self) -> Optional[float]:
        """Read light intensity in lux."""
        data = self.read()
        return data["lux"] if data else None

    def read_infrared(self) -> Optional[float]:
        """Read infrared intensity."""
        data = self.read()
        return data["infrared"] if data else None

    def read_full_spectrum(self) -> Optional[float]:
        """Read full spectrum intensity."""
        data = self.read()
        return data["full_spectrum"] if data else None

    def set_gain(self, gain: int):
        """
        Set sensor gain.

        Args:
            gain: 0 (1x) or 1 (25x)
        """
        try:
            self.sensor.gain = gain
            logger.info(f"TSL2591 gain set to {gain}")
        except Exception as e:
            logger.error(f"Error setting TSL2591 gain: {e}")

    def set_integration_time(self, integration_time: int):
        """
        Set sensor integration time.

        Args:
            integration_time: 0 (100ms), 1 (200ms), 2 (300ms), 3 (400ms),
                            4 (500ms), or 5 (600ms)
        """
        try:
            self.sensor.integration_time = integration_time
            logger.info(f"TSL2591 integration time set to {integration_time}")
        except Exception as e:
            logger.error(f"Error setting TSL2591 integration time: {e}")

    def close(self):
        """Close the sensor connection."""
        if hasattr(self, "i2c"):
            try:
                self.i2c.close()
                logger.info("TSL2591 connection closed")
            except Exception as e:
                logger.error(f"Error closing TSL2591: {e}")


# Convenience function for testing
def test_tsl2591():
    """Test TSL2591 sensor."""
    sensor = TSL2591Sensor()
    if sensor.initialized:
        data = sensor.read()
        print(f"TSL2591 Data: {data}")
        sensor.close()
    else:
        print("TSL2591 initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_tsl2591()
