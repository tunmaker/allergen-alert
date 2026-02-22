"""Advanced data processing: moving averages, AQI calculations, filtering."""

import logging
import statistics
from collections import deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MovingAverageFilter:
    """
    Moving average filter for smoothing noisy sensor data.

    Useful for particulate matter (PM) data which is inherently noisy.
    """

    def __init__(self, window_size: int = 5):
        """
        Initialize moving average filter.

        Args:
            window_size: Number of samples to average (default 5)
        """
        self.window_size = window_size
        self.readings: deque = deque(maxlen=window_size)

    def add_reading(self, value: float) -> Optional[float]:
        """
        Add a reading and get the moving average.

        Args:
            value: New sensor reading

        Returns:
            Moving average (or None if not enough readings yet)
        """
        self.readings.append(value)

        if len(self.readings) < self.window_size:
            return None  # Not enough readings yet

        return round(statistics.mean(self.readings), 2)

    def get_average(self) -> Optional[float]:
        """
        Get current moving average.

        Returns:
            Moving average or None if not enough readings
        """
        if len(self.readings) < self.window_size:
            return None

        return round(statistics.mean(self.readings), 2)

    def get_readings_count(self) -> int:
        """Get number of readings collected."""
        return len(self.readings)

    def is_ready(self) -> bool:
        """Check if filter has enough readings for averaging."""
        return len(self.readings) >= self.window_size

    def reset(self):
        """Clear all readings."""
        self.readings.clear()


class AQICalculator:
    """
    Calculate Air Quality Index from particulate matter measurements.

    Uses US EPA AQI standard for PM2.5 concentrations.
    """

    # AQI breakpoints for PM2.5 (µg/m³) - US EPA standard
    AQI_BREAKPOINTS = [
        # (pm2_5_low, pm2_5_high, aqi_low, aqi_high, category)
        (0, 12, 0, 50, "Good"),
        (12.1, 35.4, 51, 100, "Moderate"),
        (35.5, 55.4, 101, 150, "Unhealthy for Sensitive Groups"),
        (55.5, 150.4, 151, 200, "Unhealthy"),
        (150.5, 250.4, 201, 300, "Very Unhealthy"),
        (250.5, 500, 301, 500, "Hazardous"),
    ]

    @staticmethod
    def calculate_aqi(pm2_5: float) -> Tuple[int, str]:
        """
        Calculate AQI from PM2.5 concentration.

        Args:
            pm2_5: PM2.5 concentration in µg/m³

        Returns:
            Tuple of (AQI value, category string)
        """
        for pm_low, pm_high, aqi_low, aqi_high, category in AQICalculator.AQI_BREAKPOINTS:
            if pm_low <= pm2_5 <= pm_high:
                # Linear interpolation
                aqi = aqi_low + ((pm2_5 - pm_low) / (pm_high - pm_low)) * (
                    aqi_high - aqi_low
                )
                return (int(aqi), category)

        # If above highest breakpoint
        return (501, "Hazardous")

    @staticmethod
    def get_health_effects(aqi: int) -> str:
        """
        Get health effects description for AQI value.

        Args:
            aqi: AQI value

        Returns:
            Health effects description
        """
        if aqi <= 50:
            return "Air quality is satisfactory, and air pollution poses little or no risk"
        elif aqi <= 100:
            return "Air quality is acceptable, but there may be risk for some groups"
        elif aqi <= 150:
            return "Sensitive groups (children, elderly, people with heart/lung disease) may experience health effects"
        elif aqi <= 200:
            return "General public may begin to experience health effects"
        elif aqi <= 300:
            return "Health effects may be serious. General public should minimize outdoor exposure"
        else:
            return "Health alert: Everyone is at risk. General public should avoid outdoor exposure"

    @staticmethod
    def get_health_recommendations(aqi: int) -> List[str]:
        """
        Get health recommendations for AQI value.

        Args:
            aqi: AQI value

        Returns:
            List of health recommendations
        """
        recommendations = []

        if aqi <= 50:
            recommendations.append("No health risks. Enjoy outdoor activities.")
        elif aqi <= 100:
            recommendations.append("Unusually sensitive people should consider limiting prolonged outdoor exposure")
        elif aqi <= 150:
            recommendations.append("Sensitive groups should limit prolonged outdoor activities")
            recommendations.append("General public less likely to be affected")
        elif aqi <= 200:
            recommendations.append("Everyone should limit prolonged outdoor exposure")
            recommendations.append("Wear N95 mask if going outdoors")
        elif aqi <= 300:
            recommendations.append("Avoid outdoor activities")
            recommendations.append("Keep windows and doors closed")
            recommendations.append("Use air filtration if available")
        else:
            recommendations.append("Everyone must minimize outdoor exposure")
            recommendations.append("Stay indoors in an air-conditioned space with high-efficiency filters")
            recommendations.append("Wear N95/P100 mask if must go outside")

        return recommendations


class MultiSensorAQI:
    """
    Calculate comprehensive AQI using multiple air quality indicators.

    Combines PM2.5, CO2, and TVOC for overall assessment.
    """

    def __init__(self):
        """Initialize multi-sensor AQI calculator."""
        self.pm2_5: Optional[float] = None
        self.co2: Optional[float] = None
        self.tvoc: Optional[float] = None
        self.aqi_estimate: Optional[int] = None

    def update(
        self,
        pm2_5: Optional[float] = None,
        co2: Optional[float] = None,
        tvoc: Optional[float] = None,
    ):
        """
        Update air quality indicators.

        Args:
            pm2_5: PM2.5 concentration (µg/m³)
            co2: CO2 concentration (ppm)
            tvoc: TVOC concentration (ppb)
        """
        if pm2_5 is not None:
            self.pm2_5 = pm2_5
        if co2 is not None:
            self.co2 = co2
        if tvoc is not None:
            self.tvoc = tvoc

    def calculate_overall_aqi(self) -> Optional[int]:
        """
        Calculate overall AQI from all available indicators.

        Returns:
            Overall AQI value or None if insufficient data
        """
        if self.pm2_5 is None:
            return None  # PM2.5 is the primary indicator

        # Start with EPA AQI from PM2.5
        pm_aqi, _ = AQICalculator.calculate_aqi(self.pm2_5)
        scores = [pm_aqi]

        # Adjust for CO2 if available
        if self.co2 is not None:
            if self.co2 < 400:
                # Fresh outdoor air
                scores.append(0)
            elif self.co2 < 600:
                # Good indoor air
                scores.append(25)
            elif self.co2 < 1000:
                # Acceptable indoor air
                scores.append(50)
            elif self.co2 < 1500:
                # Poor indoor air
                scores.append(100)
            else:
                # Very poor
                scores.append(150)

        # Adjust for TVOC if available
        if self.tvoc is not None:
            if self.tvoc < 50:
                scores.append(0)
            elif self.tvoc < 100:
                scores.append(25)
            elif self.tvoc < 300:
                scores.append(50)
            elif self.tvoc < 500:
                scores.append(100)
            else:
                scores.append(150)

        # Use max of all indicators (worst case)
        self.aqi_estimate = max(scores)
        logger.debug(f"Multi-sensor AQI calculated: {self.aqi_estimate}")

        return self.aqi_estimate

    def get_air_quality_status(self) -> str:
        """
        Get air quality status summary.

        Returns:
            Status string
        """
        overall_aqi = self.calculate_overall_aqi()
        if overall_aqi is None:
            return "Insufficient data"

        _, pm_category = AQICalculator.calculate_aqi(self.pm2_5 or 0)

        status_parts = [f"PM2.5: {pm_category} (AQI {overall_aqi})"]

        if self.co2 is not None:
            if self.co2 < 400:
                status_parts.append("CO2: Fresh air")
            elif self.co2 < 1000:
                status_parts.append(f"CO2: {self.co2:.0f} ppm (Acceptable)")
            else:
                status_parts.append(f"CO2: {self.co2:.0f} ppm (Poor ventilation)")

        if self.tvoc is not None:
            if self.tvoc < 100:
                status_parts.append(f"TVOC: {self.tvoc:.0f} ppb (Low)")
            elif self.tvoc < 300:
                status_parts.append(f"TVOC: {self.tvoc:.0f} ppb (Moderate)")
            else:
                status_parts.append(f"TVOC: {self.tvoc:.0f} ppb (High)")

        return " | ".join(status_parts)

    def get_detailed_report(self) -> str:
        """
        Get detailed air quality analysis report.

        Returns:
            Human-readable report
        """
        overall_aqi = self.calculate_overall_aqi()

        lines = ["Air Quality Analysis Report:"]
        lines.append("=" * 60)

        if self.pm2_5 is not None:
            pm_aqi, pm_category = AQICalculator.calculate_aqi(self.pm2_5)
            lines.append(f"PM2.5: {self.pm2_5:.1f} µg/m³ → AQI {pm_aqi} ({pm_category})")

        if self.co2 is not None:
            lines.append(f"CO2: {self.co2:.0f} ppm")

        if self.tvoc is not None:
            lines.append(f"TVOC: {self.tvoc:.0f} ppb")

        lines.append("=" * 60)

        if overall_aqi is not None:
            lines.append(f"Overall AQI: {overall_aqi}")
            lines.append("")
            lines.append("Health Effects:")
            lines.append(f"  {AQICalculator.get_health_effects(overall_aqi)}")
            lines.append("")
            lines.append("Recommendations:")
            for i, rec in enumerate(
                AQICalculator.get_health_recommendations(overall_aqi), 1
            ):
                lines.append(f"  {i}. {rec}")
        else:
            lines.append("Insufficient data for AQI calculation")

        return "\n".join(lines)


class ExponentialMovingAverage:
    """
    Exponential Moving Average filter for data smoothing.

    Gives more weight to recent readings than older ones.
    """

    def __init__(self, alpha: float = 0.2):
        """
        Initialize EMA filter.

        Args:
            alpha: Smoothing factor (0-1). Higher = more responsive to changes
        """
        self.alpha = alpha
        self.ema: Optional[float] = None

    def add_reading(self, value: float) -> float:
        """
        Add a reading and get the EMA.

        Args:
            value: New sensor reading

        Returns:
            Exponential moving average
        """
        if self.ema is None:
            self.ema = value
        else:
            self.ema = (self.alpha * value) + ((1 - self.alpha) * self.ema)

        return round(self.ema, 2)

    def get_ema(self) -> Optional[float]:
        """Get current EMA value."""
        return self.ema

    def reset(self):
        """Reset the EMA."""
        self.ema = None
