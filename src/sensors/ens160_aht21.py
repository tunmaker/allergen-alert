"""ENS160 Air Quality & AHT21 Temp/Humidity Sensor Drivers."""

import logging
import os
import struct
import time
from typing import Dict, Optional

try:
    import smbus2
except ImportError:
    smbus2 = None

logger = logging.getLogger(__name__)


class AHT21Sensor:
    """AHT21 temperature and humidity sensor (high accuracy)."""

    I2C_ADDRESS = 0x38
    COMMAND_INITIALIZE = [0xBE, 0x08, 0x00]
    COMMAND_TRIGGER_MEASUREMENT = [0xAC, 0x33, 0x00]

    def __init__(self, i2c_bus: int = 1, i2c_address: int = I2C_ADDRESS, temp_offset: float = 0):
        """
        Initialize AHT21 sensor.

        Args:
            i2c_bus: I2C bus number (default 1 on Raspberry Pi)
            i2c_address: I2C address (default 0x38)
            temp_offset: Temperature offset correction in °C
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.temp_offset = float(os.getenv("AHT21_TEMP_OFFSET", temp_offset))

        self.bus = None
        self.initialized = False
        self.last_read_time = 0

        self._initialize()

    def _initialize(self):
        """Initialize the AHT21 sensor."""
        if smbus2 is None:
            logger.warning("smbus2 not installed, sensor will not function")
            return

        try:
            self.bus = smbus2.SMBus(self.i2c_bus)

            # Send initialization command
            self.bus.write_i2c_block_data(self.i2c_address, 0, self.COMMAND_INITIALIZE)
            time.sleep(0.1)

            self.initialized = True
            logger.info(f"AHT21 initialized at address 0x{self.i2c_address:02x}")

        except Exception as e:
            logger.error(f"Failed to initialize AHT21: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read temperature and humidity.

        Returns:
            Dict with keys: temperature, humidity
            or None if read failed
        """
        if not self.initialized or self.bus is None:
            logger.warning("AHT21 not initialized")
            return None

        try:
            # Trigger measurement
            self.bus.write_i2c_block_data(self.i2c_address, 0, self.COMMAND_TRIGGER_MEASUREMENT)

            # Wait for measurement
            time.sleep(0.08)

            # Read 6 bytes of data
            data = self.bus.read_i2c_block_data(self.i2c_address, 0, 6)

            # Parse humidity (first 2 bytes + upper 4 bits of 3rd byte)
            humidity_raw = (data[1] << 8 | data[2]) >> 4
            humidity = (humidity_raw / 1048576) * 100

            # Parse temperature (lower 4 bits of 3rd byte + next 2 bytes)
            temp_raw = ((data[2] & 0x0F) << 16 | data[3] << 8 | data[4])
            temperature = ((temp_raw / 1048576) * 200) - 50 + self.temp_offset

            self.last_read_time = time.time()

            return {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
            }

        except Exception as e:
            logger.error(f"Error reading AHT21: {e}")
            return None

    def read_temperature(self) -> Optional[float]:
        """Read temperature in °C."""
        data = self.read()
        return data["temperature"] if data else None

    def read_humidity(self) -> Optional[float]:
        """Read humidity in %."""
        data = self.read()
        return data["humidity"] if data else None

    def set_temp_offset(self, offset: float):
        """Set temperature offset correction."""
        self.temp_offset = offset
        logger.info(f"AHT21 temperature offset set to {offset}°C")

    def close(self):
        """Close the sensor connection."""
        if self.bus:
            try:
                self.bus.close()
                logger.info("AHT21 connection closed")
            except Exception as e:
                logger.error(f"Error closing AHT21: {e}")


class ENS160Sensor:
    """ENS160 air quality sensor (eCO2, TVOC, AQI)."""

    I2C_ADDRESS = 0x53
    COMMAND_NOP = 0x00
    COMMAND_DEVICE_RESET = 0xF6
    DATA_STATUS = 0x02
    DATA_AQI = 0x03
    DATA_TVOC = 0x04
    DATA_ECO2 = 0x05

    def __init__(self, i2c_bus: int = 1, i2c_address: int = I2C_ADDRESS):
        """
        Initialize ENS160 sensor.

        Args:
            i2c_bus: I2C bus number (default 1 on Raspberry Pi)
            i2c_address: I2C address (default 0x53)
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        self.bus = None
        self.initialized = False
        self.burn_in_start_time = None
        self.burn_in_complete = False

        self._initialize()

    def _initialize(self):
        """Initialize the ENS160 sensor."""
        if smbus2 is None:
            logger.warning("smbus2 not installed, sensor will not function")
            return

        try:
            self.bus = smbus2.SMBus(self.i2c_bus)

            # Reset device
            self.bus.write_byte_data(self.i2c_address, self.COMMAND_DEVICE_RESET, 0)
            time.sleep(0.5)

            # Start burn-in period
            self.burn_in_start_time = time.time()
            burn_in_hours = int(os.getenv("ENS160_BURN_IN_HOURS", 1))
            self.burn_in_complete = False

            self.initialized = True
            logger.info(
                f"ENS160 initialized at address 0x{self.i2c_address:02x} "
                f"(burn-in: {burn_in_hours}h initial, 7 days for full accuracy)"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ENS160: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read air quality data.

        Returns:
            Dict with keys: aqi, tvoc, eco2, burn_in_status
            or None if read failed
        """
        if not self.initialized or self.bus is None:
            logger.warning("ENS160 not initialized")
            return None

        try:
            # Read AQI status
            status = self.bus.read_byte_data(self.i2c_address, self.DATA_STATUS)
            data_valid = (status & 0x01) == 0

            aqi = self.bus.read_byte_data(self.i2c_address, self.DATA_AQI)
            tvoc = self.bus.read_word_data(self.i2c_address, self.DATA_TVOC)
            eco2 = self.bus.read_word_data(self.i2c_address, self.DATA_ECO2)

            # Calculate burn-in progress
            if self.burn_in_start_time and not self.burn_in_complete:
                elapsed_hours = (time.time() - self.burn_in_start_time) / 3600
                full_accuracy_hours = 24 * 7  # 7 days

                if elapsed_hours >= 1:
                    if not self.burn_in_complete and elapsed_hours >= full_accuracy_hours:
                        self.burn_in_complete = True
                        logger.info("ENS160 burn-in complete - full accuracy achieved")

                burn_in_status = f"{elapsed_hours:.1f}h (full accuracy in 7 days)"
            else:
                burn_in_status = "complete" if self.burn_in_complete else "active"

            return {
                "aqi": aqi,
                "tvoc": tvoc,
                "eco2": eco2,
                "data_valid": data_valid,
                "burn_in_status": burn_in_status,
            }

        except Exception as e:
            logger.error(f"Error reading ENS160: {e}")
            return None

    def read_aqi(self) -> Optional[int]:
        """Read Air Quality Index (0-500)."""
        data = self.read()
        return data["aqi"] if data else None

    def read_tvoc(self) -> Optional[int]:
        """Read TVOC in ppb."""
        data = self.read()
        return data["tvoc"] if data else None

    def read_eco2(self) -> Optional[int]:
        """Read estimated CO2 in ppm."""
        data = self.read()
        return data["eco2"] if data else None

    def close(self):
        """Close the sensor connection."""
        if self.bus:
            try:
                self.bus.close()
                logger.info("ENS160 connection closed")
            except Exception as e:
                logger.error(f"Error closing ENS160: {e}")


# Convenience function for testing
def test_ens160_aht21():
    """Test ENS160 and AHT21 sensors."""
    aht21 = AHT21Sensor()
    ens160 = ENS160Sensor()

    if aht21.initialized and ens160.initialized:
        for i in range(10):
            aht_data = aht21.read()
            ens_data = ens160.read()

            if aht_data:
                print(f"AHT21 Data {i+1}: {aht_data}")
            if ens_data:
                print(f"ENS160 Data {i+1}: {ens_data}")

            time.sleep(1)

        aht21.close()
        ens160.close()
    else:
        print("Sensor initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ens160_aht21()
