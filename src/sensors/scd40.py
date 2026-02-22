"""SCD40 CO2 Sensor Driver (NDIR)."""

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


class SCD40Sensor:
    """SCD40 NDIR CO2 sensor with temperature and humidity."""

    I2C_ADDRESS = 0x62

    # Command codes
    START_PERIODIC_MEASUREMENT = 0x21B1
    READ_MEASUREMENT = 0xEC05
    STOP_PERIODIC_MEASUREMENT = 0x3F86
    SET_MEASUREMENT_INTERVAL = 0x4600
    SET_AMBIENT_PRESSURE = 0x61E0
    GET_SENSOR_INFO = 0xD025
    GET_SERIAL_NUMBER = 0x3682

    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_address: int = I2C_ADDRESS,
        measurement_interval: int = 5,
        temp_offset: float = 0,
    ):
        """
        Initialize SCD40 sensor.

        Args:
            i2c_bus: I2C bus number (default 1 on Raspberry Pi)
            i2c_address: I2C address (default 0x62)
            measurement_interval: Measurement interval in seconds (2-1800)
            temp_offset: Temperature offset correction in °C
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.measurement_interval = measurement_interval
        self.temp_offset = float(os.getenv("SCD40_TEMP_OFFSET", temp_offset))

        self.bus = None
        self.initialized = False
        self.started = False
        self.last_read_time = 0
        self.serial_number = None

        self._initialize()

    def _initialize(self):
        """Initialize the SCD40 sensor."""
        if smbus2 is None:
            logger.warning("smbus2 not installed, sensor will not function")
            return

        try:
            self.bus = smbus2.SMBus(self.i2c_bus)

            # Get sensor info
            self.serial_number = self._read_register(self.GET_SERIAL_NUMBER)
            logger.info(f"SCD40 initialized with serial: {self.serial_number}")

            # Start periodic measurement
            self._write_register(self.START_PERIODIC_MEASUREMENT)
            time.sleep(1)
            self.started = True

            self.initialized = True
            logger.info(f"SCD40 periodic measurement started at 0x{self.i2c_address:02x}")

        except Exception as e:
            logger.error(f"Failed to initialize SCD40: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read sensor data.

        Returns:
            Dict with keys: co2, temperature, humidity
            or None if read failed
        """
        if not self.initialized or self.bus is None:
            logger.warning("SCD40 not initialized")
            return None

        try:
            # Check if enough time has passed since last read
            now = time.time()
            if now - self.last_read_time < self.measurement_interval:
                return None

            # Read measurement
            data = self._read_measurement()
            if data:
                self.last_read_time = now
            return data

        except Exception as e:
            logger.error(f"Error reading SCD40: {e}")
            return None

    def _read_measurement(self) -> Optional[Dict]:
        """Read CO2, temperature, and humidity from sensor."""
        try:
            # Write read measurement command
            self.bus.write_i2c_block_data(
                self.i2c_address,
                (self.READ_MEASUREMENT >> 8) & 0xFF,
                [(self.READ_MEASUREMENT & 0xFF)],
            )

            # Wait for measurement to be ready
            time.sleep(0.01)

            # Read 9 bytes (3 parameters × 3 bytes: value + checksum)
            data = self.bus.read_i2c_block_data(self.i2c_address, 0, 9)

            if len(data) < 9:
                logger.warning("SCD40: Incomplete measurement data")
                return None

            # Parse CO2 (ppm)
            co2 = struct.unpack(">H", bytes(data[0:2]))[0]

            # Parse temperature (°C, raw value / 200)
            temp_raw = struct.unpack(">H", bytes(data[3:5]))[0]
            temperature = -45 + (175 * temp_raw) / 65536
            temperature += self.temp_offset

            # Parse humidity (%, raw value / 100)
            humidity_raw = struct.unpack(">H", bytes(data[6:8]))[0]
            humidity = (100 * humidity_raw) / 65536

            return {
                "co2": co2,
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
            }

        except Exception as e:
            logger.error(f"Error reading SCD40 measurement: {e}")
            return None

    def read_co2(self) -> Optional[int]:
        """Read CO2 concentration in ppm."""
        data = self.read()
        return data["co2"] if data else None

    def read_temperature(self) -> Optional[float]:
        """Read temperature in °C."""
        data = self.read()
        return data["temperature"] if data else None

    def read_humidity(self) -> Optional[float]:
        """Read humidity in %."""
        data = self.read()
        return data["humidity"] if data else None

    def _write_register(self, command: int):
        """Write a command to the sensor."""
        high_byte = (command >> 8) & 0xFF
        low_byte = command & 0xFF

        self.bus.write_i2c_block_data(self.i2c_address, high_byte, [low_byte])

    def _read_register(self, command: int) -> Optional[int]:
        """Read a register from the sensor."""
        try:
            high_byte = (command >> 8) & 0xFF
            low_byte = command & 0xFF

            self.bus.write_i2c_block_data(self.i2c_address, high_byte, [low_byte])
            time.sleep(0.05)

            data = self.bus.read_i2c_block_data(self.i2c_address, 0, 3)
            return struct.unpack(">H", bytes(data[0:2]))[0]

        except Exception as e:
            logger.error(f"Error reading SCD40 register: {e}")
            return None

    def set_temp_offset(self, offset: float):
        """Set temperature offset correction."""
        self.temp_offset = offset
        logger.info(f"SCD40 temperature offset set to {offset}°C")

    def close(self):
        """Close the sensor connection."""
        if self.bus:
            try:
                if self.started:
                    self._write_register(self.STOP_PERIODIC_MEASUREMENT)
                self.bus.close()
                logger.info("SCD40 connection closed")
            except Exception as e:
                logger.error(f"Error closing SCD40: {e}")


# Convenience function for testing
def test_scd40():
    """Test SCD40 sensor."""
    sensor = SCD40Sensor(measurement_interval=1)
    if sensor.initialized:
        for i in range(10):
            data = sensor.read()
            if data:
                print(f"SCD40 Data {i+1}: {data}")
            time.sleep(1)
        sensor.close()
    else:
        print("SCD40 initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scd40()
