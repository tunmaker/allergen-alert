"""Sensor calibration and burn-in tracking."""

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class CalibrationData:
    """Calibration status for a sensor."""

    sensor_name: str
    last_calibration: float  # Unix timestamp
    calibration_status: str  # "pending", "in_progress", "complete"
    notes: str = ""

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict):
        """Create from dictionary."""
        return CalibrationData(**data)


class CalibrationManager:
    """Manage sensor calibration status and persistence."""

    def __init__(self, calibration_file: str = "/var/lib/allergen-alert/calibration.json"):
        """
        Initialize calibration manager.

        Args:
            calibration_file: Path to persistent calibration data file
        """
        self.calibration_file = Path(calibration_file)
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)
        self.calibrations: Dict[str, CalibrationData] = {}
        self._load_calibrations()

    def _load_calibrations(self):
        """Load calibration data from disk."""
        if self.calibration_file.exists():
            try:
                with open(self.calibration_file, "r") as f:
                    data = json.load(f)
                    for sensor_name, calib_data in data.items():
                        self.calibrations[sensor_name] = CalibrationData.from_dict(
                            calib_data
                        )
                    logger.info(f"Loaded calibration data for {len(self.calibrations)} sensors")
            except Exception as e:
                logger.error(f"Failed to load calibration data: {e}")

    def _save_calibrations(self):
        """Save calibration data to disk."""
        try:
            with open(self.calibration_file, "w") as f:
                data = {
                    name: calib.to_dict()
                    for name, calib in self.calibrations.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calibration data: {e}")

    def start_calibration(self, sensor_name: str, notes: str = ""):
        """
        Mark a sensor as starting calibration.

        Args:
            sensor_name: Name of the sensor
            notes: Optional notes about calibration
        """
        self.calibrations[sensor_name] = CalibrationData(
            sensor_name=sensor_name,
            last_calibration=time.time(),
            calibration_status="in_progress",
            notes=notes,
        )
        self._save_calibrations()
        logger.info(f"Started calibration for {sensor_name}: {notes}")

    def complete_calibration(self, sensor_name: str, notes: str = ""):
        """
        Mark a sensor as calibration complete.

        Args:
            sensor_name: Name of the sensor
            notes: Optional notes about calibration
        """
        if sensor_name not in self.calibrations:
            self.calibrations[sensor_name] = CalibrationData(
                sensor_name=sensor_name,
                last_calibration=time.time(),
                calibration_status="complete",
                notes=notes,
            )
        else:
            self.calibrations[sensor_name].calibration_status = "complete"
            self.calibrations[sensor_name].last_calibration = time.time()
            self.calibrations[sensor_name].notes = notes

        self._save_calibrations()
        logger.info(f"Completed calibration for {sensor_name}")

    def get_calibration_status(self, sensor_name: str) -> Optional[CalibrationData]:
        """
        Get calibration status of a sensor.

        Args:
            sensor_name: Name of the sensor

        Returns:
            CalibrationData or None if not found
        """
        return self.calibrations.get(sensor_name)

    def is_calibrated(self, sensor_name: str) -> bool:
        """
        Check if sensor is fully calibrated.

        Args:
            sensor_name: Name of the sensor

        Returns:
            True if sensor is complete, False otherwise
        """
        calib = self.calibrations.get(sensor_name)
        return calib is not None and calib.calibration_status == "complete"


class ENS160BurnInTracker:
    """Track ENS160 sensor burn-in and accuracy improvement."""

    # ENS160 requires burn-in periods
    INITIAL_BURN_IN_HOURS = 1  # Initial burn-in period
    FULL_ACCURACY_DAYS = 7  # Days to reach full accuracy

    def __init__(self, calibration_manager: CalibrationManager):
        """
        Initialize ENS160 burn-in tracker.

        Args:
            calibration_manager: CalibrationManager instance for persistence
        """
        self.calib_manager = calibration_manager
        self.start_time: Optional[float] = None
        self.accuracy_level: str = "unknown"
        self._initialize_tracking()

    def _initialize_tracking(self):
        """Initialize burn-in tracking from saved state."""
        status = self.calib_manager.get_calibration_status("ens160")

        if status is None:
            # First time - start tracking
            self.calib_manager.start_calibration("ens160", "Initial 1-hour burn-in period")
            self.start_time = time.time()
            self.accuracy_level = "initializing"
            logger.info("ENS160 burn-in tracking started")
        elif status.calibration_status == "in_progress":
            # Already tracking - restore from saved state
            self.start_time = status.last_calibration
            self.accuracy_level = "burn_in"
            logger.info("ENS160 burn-in tracking resumed")
        else:
            # Already complete - track accuracy level
            self.start_time = status.last_calibration
            elapsed_days = (time.time() - self.start_time) / (24 * 3600)
            if elapsed_days >= self.FULL_ACCURACY_DAYS:
                self.accuracy_level = "full"
            else:
                self.accuracy_level = "improving"

    def get_accuracy_level(self) -> str:
        """
        Get current accuracy level of ENS160.

        Returns:
            "initializing", "burn_in", "improving", or "full"
        """
        if self.start_time is None:
            return "unknown"

        elapsed_seconds = time.time() - self.start_time
        elapsed_hours = elapsed_seconds / 3600
        elapsed_days = elapsed_seconds / (24 * 3600)

        if elapsed_hours < self.INITIAL_BURN_IN_HOURS:
            return "initializing"
        elif elapsed_days < self.FULL_ACCURACY_DAYS:
            return "burn_in"
        else:
            if self.accuracy_level != "full":
                self.accuracy_level = "full"
                self.calib_manager.complete_calibration(
                    "ens160", "7-day burn-in complete - full accuracy reached"
                )
                logger.info("ENS160 reached full accuracy after 7 days")
            return "full"

    def get_burn_in_progress(self) -> float:
        """
        Get burn-in progress as percentage (0-100).

        Returns:
            Progress percentage
        """
        if self.start_time is None:
            return 0

        elapsed_seconds = time.time() - self.start_time
        full_accuracy_seconds = self.FULL_ACCURACY_DAYS * 24 * 3600
        progress = min((elapsed_seconds / full_accuracy_seconds) * 100, 100)

        return round(progress, 1)

    def get_time_remaining(self) -> Optional[timedelta]:
        """
        Get estimated time remaining for full accuracy.

        Returns:
            timedelta or None if already complete
        """
        if self.start_time is None:
            return None

        accuracy = self.get_accuracy_level()
        if accuracy == "full":
            return None

        elapsed = time.time() - self.start_time
        full_accuracy_seconds = self.FULL_ACCURACY_DAYS * 24 * 3600
        remaining_seconds = full_accuracy_seconds - elapsed

        if remaining_seconds <= 0:
            return None

        return timedelta(seconds=int(remaining_seconds))

    def get_status_report(self) -> str:
        """
        Get detailed ENS160 status report.

        Returns:
            Human-readable status report
        """
        accuracy = self.get_accuracy_level()
        progress = self.get_burn_in_progress()
        remaining = self.get_time_remaining()

        lines = ["ENS160 Burn-in Status:"]
        lines.append("=" * 50)
        lines.append(f"Accuracy Level: {accuracy.upper()}")
        lines.append(f"Progress: {progress}%")

        if remaining:
            days = remaining.days
            hours = remaining.seconds // 3600
            lines.append(f"Time Remaining: {days}d {hours}h")
        else:
            lines.append("Time Remaining: None (Full accuracy reached)")

        lines.append("=" * 50)
        lines.append("\nAccuracy levels:")
        lines.append("  initializing: First hour - sensor stabilizing")
        lines.append("  burn_in: 1-7 days - MOX sensor improving")
        lines.append("  improving: 1-7 days - Approaching full accuracy")
        lines.append("  full: 7+ days - Maximum accuracy")

        return "\n".join(lines)


class SCD40CalibrationTracker:
    """Track SCD40 auto-calibration status."""

    def __init__(self, calibration_manager: CalibrationManager):
        """
        Initialize SCD40 calibration tracker.

        Args:
            calibration_manager: CalibrationManager instance
        """
        self.calib_manager = calibration_manager
        self.last_fresh_air_exposure: Optional[float] = None
        self._initialize_tracking()

    def _initialize_tracking(self):
        """Initialize tracking from saved state."""
        status = self.calib_manager.get_calibration_status("scd40")

        if status is None:
            self.calib_manager.start_calibration(
                "scd40", "Waiting for fresh air exposure for auto-calibration"
            )
            logger.info("SCD40 auto-calibration tracking started")
        elif status.calibration_status == "in_progress":
            # Extract timestamp if in notes
            self.last_fresh_air_exposure = status.last_calibration
            logger.info("SCD40 calibration tracking resumed")

    def record_fresh_air_exposure(self):
        """Record a fresh air exposure for auto-calibration."""
        self.last_fresh_air_exposure = time.time()
        self.calib_manager.complete_calibration(
            "scd40", "Fresh air exposure recorded for auto-calibration"
        )
        logger.info("SCD40 fresh air exposure recorded")

    def get_days_since_calibration(self) -> Optional[float]:
        """
        Get days since last calibration exposure.

        Returns:
            Days or None if no exposure recorded
        """
        if self.last_fresh_air_exposure is None:
            return None

        elapsed_seconds = time.time() - self.last_fresh_air_exposure
        elapsed_days = elapsed_seconds / (24 * 3600)

        return round(elapsed_days, 1)

    def needs_recalibration(self, max_days: int = 7) -> bool:
        """
        Check if sensor needs recalibration.

        Args:
            max_days: Max days between calibrations

        Returns:
            True if needs recalibration, False otherwise
        """
        if self.last_fresh_air_exposure is None:
            return True

        days_since = self.get_days_since_calibration()
        return days_since > max_days if days_since else True

    def get_status_report(self) -> str:
        """
        Get SCD40 calibration status report.

        Returns:
            Human-readable status report
        """
        lines = ["SCD40 Auto-Calibration Status:"]
        lines.append("=" * 50)

        days_since = self.get_days_since_calibration()
        if days_since is None:
            lines.append("Last Calibration: Never")
            lines.append("Status: Needs fresh air exposure")
        else:
            lines.append(f"Last Calibration: {days_since} days ago")
            if self.needs_recalibration():
                lines.append("Status: ⚠ Recalibration recommended")
            else:
                lines.append("Status: ✓ Calibration current")

        lines.append("=" * 50)
        lines.append("\nInstructions:")
        lines.append("- Expose sensor to fresh air (outdoor) for 10-15 minutes")
        lines.append("- SCD40 will auto-calibrate to ~400 ppm CO2")
        lines.append("- Repeat monthly or after significant CO2 drift")

        return "\n".join(lines)
