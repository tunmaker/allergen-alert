"""PMS5003 Particulate Matter Sensor Driver."""

import logging
import os
import struct
import time
from typing import Dict, Optional

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger(__name__)


class PMS5003Sensor:
    """PMS5003 laser particulate matter sensor with duty cycle management."""

    FRAME_LENGTH = 32
    START_BYTE_1 = 0x42
    START_BYTE_2 = 0x4D

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baudrate: int = 9600,
        timeout: float = 2.0,
        duty_cycle_enabled: bool = True,
        duty_cycle_on: int = 30,
        duty_cycle_off: int = 30,
    ):
        """
        Initialize PMS5003 sensor.

        Args:
            port: Serial port (e.g., /dev/ttyAMA0)
            baudrate: Serial baudrate (9600 for PMS5003)
            timeout: Serial read timeout in seconds
            duty_cycle_enabled: Enable duty cycle to extend laser lifetime
            duty_cycle_on: Seconds to keep sensor on
            duty_cycle_off: Seconds to keep sensor off
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.duty_cycle_enabled = duty_cycle_enabled or os.getenv(
            "PMS5003_DUTY_CYCLE_ENABLED", "true"
        ).lower() == "true"
        self.duty_cycle_on = duty_cycle_on or int(
            os.getenv("PMS5003_DUTY_CYCLE_ON_SECONDS", duty_cycle_on)
        )
        self.duty_cycle_off = duty_cycle_off or int(
            os.getenv("PMS5003_DUTY_CYCLE_OFF_SECONDS", duty_cycle_off)
        )

        self.serial = None
        self.initialized = False
        self.last_read_time = 0
        self.duty_cycle_state = "off"
        self.duty_cycle_start = time.time()

        self._initialize()

    def _initialize(self):
        """Initialize the PMS5003 sensor."""
        if serial is None:
            logger.warning("pyserial not installed, sensor will not function")
            return

        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )

            self.initialized = True
            logger.info(f"PMS5003 initialized on port {self.port}")

            if self.duty_cycle_enabled:
                logger.info(
                    f"Duty cycle enabled: {self.duty_cycle_on}s on, "
                    f"{self.duty_cycle_off}s off"
                )
        except Exception as e:
            logger.error(f"Failed to initialize PMS5003: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read sensor data.

        Returns:
            Dict with PM1.0, PM2.5, PM10 concentrations and particle counts
            or None if read failed
        """
        if not self.initialized or self.serial is None:
            logger.warning("PMS5003 not initialized")
            return None

        # Handle duty cycle
        if self.duty_cycle_enabled:
            self._update_duty_cycle()
            if self.duty_cycle_state == "off":
                logger.debug("PMS5003 in sleep mode (duty cycle off)")
                return None

        try:
            # Try to read a complete frame
            for _ in range(10):  # Try up to 10 times
                byte = self.serial.read(1)
                if not byte:
                    continue

                if byte[0] == self.START_BYTE_1:
                    # Found start byte 1, check for byte 2
                    byte2 = self.serial.read(1)
                    if byte2 and byte2[0] == self.START_BYTE_2:
                        # Valid start bytes, read rest of frame
                        frame_data = self.serial.read(self.FRAME_LENGTH - 2)
                        if len(frame_data) == self.FRAME_LENGTH - 2:
                            return self._parse_frame(byte + byte2 + frame_data)

            logger.warning("PMS5003: Could not read valid frame")
            return None

        except Exception as e:
            logger.error(f"Error reading PMS5003: {e}")
            return None

    def _parse_frame(self, frame: bytes) -> Optional[Dict]:
        """
        Parse PMS5003 data frame.

        Frame format (32 bytes total):
        - Bytes 0-1: Start bytes (0x42, 0x4D)
        - Bytes 2-3: Frame length (0x001D = 29 bytes)
        - Bytes 4-29: PM data
        - Bytes 30-31: Checksum
        """
        if len(frame) != self.FRAME_LENGTH:
            return None

        try:
            # Verify checksum
            checksum = sum(frame[0:30])
            frame_checksum = struct.unpack(">H", frame[30:32])[0]

            if checksum != frame_checksum:
                logger.warning("PMS5003: Checksum mismatch")
                return None

            # Parse PM concentrations (µg/m³)
            pm1_0 = struct.unpack(">H", frame[4:6])[0]
            pm2_5 = struct.unpack(">H", frame[6:8])[0]
            pm10 = struct.unpack(">H", frame[8:10])[0]

            # Parse particle counts (per 0.1L)
            particles_0_3 = struct.unpack(">H", frame[10:12])[0]
            particles_0_5 = struct.unpack(">H", frame[12:14])[0]
            particles_1_0 = struct.unpack(">H", frame[14:16])[0]
            particles_2_5 = struct.unpack(">H", frame[16:18])[0]

            self.last_read_time = time.time()

            return {
                "pm1_0": pm1_0,
                "pm2_5": pm2_5,
                "pm10": pm10,
                "particles_0_3": particles_0_3,
                "particles_0_5": particles_0_5,
                "particles_1_0": particles_1_0,
                "particles_2_5": particles_2_5,
            }

        except Exception as e:
            logger.error(f"Error parsing PMS5003 frame: {e}")
            return None

    def read_pm(self) -> Optional[Dict]:
        """Read just PM concentrations (PM1.0, PM2.5, PM10)."""
        data = self.read()
        if data:
            return {k: data[k] for k in ["pm1_0", "pm2_5", "pm10"]}
        return None

    def _update_duty_cycle(self):
        """Update duty cycle state based on elapsed time."""
        elapsed = time.time() - self.duty_cycle_start

        if self.duty_cycle_state == "off":
            if elapsed > self.duty_cycle_off:
                self.duty_cycle_state = "on"
                self.duty_cycle_start = time.time()
                logger.debug("PMS5003 duty cycle: turning ON")
        else:  # on
            if elapsed > self.duty_cycle_on:
                self.duty_cycle_state = "off"
                self.duty_cycle_start = time.time()
                logger.debug("PMS5003 duty cycle: turning OFF")

    def set_duty_cycle(self, enabled: bool, on_seconds: int = 30, off_seconds: int = 30):
        """Configure duty cycle parameters."""
        self.duty_cycle_enabled = enabled
        self.duty_cycle_on = on_seconds
        self.duty_cycle_off = off_seconds
        logger.info(
            f"PMS5003 duty cycle: {'enabled' if enabled else 'disabled'} "
            f"({on_seconds}s on, {off_seconds}s off)"
        )

    def close(self):
        """Close the sensor connection."""
        if self.serial:
            try:
                self.serial.close()
                logger.info("PMS5003 connection closed")
            except Exception as e:
                logger.error(f"Error closing PMS5003: {e}")


# Convenience function for testing
def test_pms5003():
    """Test PMS5003 sensor."""
    sensor = PMS5003Sensor()
    if sensor.initialized:
        for i in range(5):
            data = sensor.read()
            if data:
                print(f"PMS5003 Data {i+1}: {data}")
            time.sleep(1)
        sensor.close()
    else:
        print("PMS5003 initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_pms5003()
