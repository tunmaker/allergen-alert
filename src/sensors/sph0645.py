"""SPH0645 I2S MEMS Microphone Driver."""

import logging
import math
import os
from typing import Dict, Optional

try:
    import board
    import busio
    import audiobusio
    import array
except ImportError:
    audiobusio = None

logger = logging.getLogger(__name__)


class SPH0645Sensor:
    """SPH0645 MEMS microphone with dBA sound level measurement."""

    SAMPLE_RATE = 16000  # 16 kHz
    BLOCK_SIZE = 256
    REFERENCE_PRESSURE = 20e-6  # 20 µPa (reference pressure for dB calculation)

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        block_size: int = BLOCK_SIZE,
    ):
        """
        Initialize SPH0645 microphone.

        Args:
            sample_rate: Audio sample rate in Hz (default 16000)
            block_size: Audio block size for processing
        """
        self.sample_rate = sample_rate
        self.block_size = block_size

        self.i2s = None
        self.initialized = False
        self.reference_level = None

        self._initialize()

    def _initialize(self):
        """Initialize the SPH0645 microphone."""
        if audiobusio is None:
            logger.warning("audiobusio not installed, sensor will not function")
            return

        try:
            # Configure I2S for audio input
            i2s = audiobusio.I2SIn(
                clock=board.GP5,
                word_select=board.GP6,
                data=board.GP7,
                sample_rate=self.sample_rate,
                bits_per_sample=16,
                mono=True,
            )

            self.i2s = i2s
            self.initialized = True
            logger.info(f"SPH0645 initialized at sample rate {self.sample_rate} Hz")

        except Exception as e:
            logger.error(f"Failed to initialize SPH0645: {e}")
            self.initialized = False

    def read(self) -> Optional[Dict]:
        """
        Read audio level and calculate dBA.

        Returns:
            Dict with keys: dba, rms
            or None if read failed
        """
        if not self.initialized or self.i2s is None:
            logger.warning("SPH0645 not initialized")
            return None

        try:
            # Read audio block
            audio_data = array.array("h")
            self.i2s.readinto(audio_data)

            # Calculate RMS (root mean square)
            sum_squares = sum(x ** 2 for x in audio_data)
            rms = math.sqrt(sum_squares / len(audio_data))

            # Convert to dBA (decibels relative to reference pressure)
            # dB = 20 * log10(RMS / Reference)
            if rms > 0:
                db = 20 * math.log10(rms / self.REFERENCE_PRESSURE)
            else:
                db = 0

            # Apply A-weighting approximation (simplified)
            dba = self._apply_a_weighting(db)

            return {
                "dba": round(dba, 2),
                "rms": round(rms, 2),
            }

        except Exception as e:
            logger.error(f"Error reading SPH0645: {e}")
            return None

    def _apply_a_weighting(self, db: float) -> float:
        """
        Apply A-weighting correction for human hearing.

        A-weighting approximates human ear response to sound.
        This is a simplified approximation.
        """
        # Simplified A-weighting filter (frequency dependent)
        # In a real implementation, this would require FFT analysis
        # For now, return the raw dB with a small adjustment
        return db + 2

    def read_dba(self) -> Optional[float]:
        """Read sound level in dBA."""
        data = self.read()
        return data["dba"] if data else None

    def read_rms(self) -> Optional[float]:
        """Read RMS (root mean square) amplitude."""
        data = self.read()
        return data["rms"] if data else None

    def set_reference_level(self, reference: float):
        """Set reference pressure for dB calculation."""
        self.reference_level = reference
        logger.info(f"SPH0645 reference level set to {reference}")

    def close(self):
        """Close the microphone connection."""
        if self.i2s:
            try:
                self.i2s.deinit()
                logger.info("SPH0645 connection closed")
            except Exception as e:
                logger.error(f"Error closing SPH0645: {e}")


# Convenience function for testing
def test_sph0645():
    """Test SPH0645 microphone."""
    sensor = SPH0645Sensor()
    if sensor.initialized:
        for i in range(10):
            data = sensor.read()
            if data:
                print(f"SPH0645 Data {i+1}: {data}")
        sensor.close()
    else:
        print("SPH0645 initialization failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_sph0645()
