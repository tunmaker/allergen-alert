"""PMS5003 laser duty cycle management to extend sensor lifetime."""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class PMS5003DutyCycleManager:
    """
    Manage PMS5003 duty cycle to extend laser lifetime.

    The PMS5003 laser has ~8,000 hour lifetime. This manager implements
    duty cycling to reduce continuous operation time:
    - Run laser for 30 seconds
    - Rest for 30 seconds
    - Results in 50% duty cycle = extended lifetime

    Alternative patterns can be configured for different use cases.
    """

    # Predefined duty cycle patterns
    PATTERNS = {
        "extended": {"run_seconds": 30, "rest_seconds": 30},  # 50% duty
        "balanced": {"run_seconds": 45, "rest_seconds": 15},  # 75% duty
        "normal": {"run_seconds": 60, "rest_seconds": 0},     # 100% duty (no cycling)
    }

    def __init__(
        self,
        pattern: str = "extended",
        run_seconds: Optional[int] = None,
        rest_seconds: Optional[int] = None,
    ):
        """
        Initialize duty cycle manager.

        Args:
            pattern: Pattern name ('extended', 'balanced', 'normal')
            run_seconds: Override pattern with custom run time
            rest_seconds: Override pattern with custom rest time
        """
        if pattern not in self.PATTERNS:
            raise ValueError(f"Unknown pattern: {pattern}. Valid: {list(self.PATTERNS.keys())}")

        config = self.PATTERNS[pattern].copy()

        if run_seconds is not None:
            config["run_seconds"] = run_seconds
        if rest_seconds is not None:
            config["rest_seconds"] = rest_seconds

        self.pattern = pattern
        self.run_seconds = config["run_seconds"]
        self.rest_seconds = config["rest_seconds"]
        self.cycle_seconds = self.run_seconds + self.rest_seconds

        self.cycle_start_time = time.time()
        self.is_laser_on = True
        self.total_on_time = 0.0  # Track total on time

        logger.info(
            f"PMS5003 duty cycle initialized: pattern={pattern}, "
            f"run={self.run_seconds}s, rest={self.rest_seconds}s, "
            f"duty_cycle={self.get_duty_cycle_percent():.0f}%"
        )

    def should_laser_be_on(self) -> bool:
        """
        Determine if laser should be on based on duty cycle.

        Returns:
            True if laser should be on, False if should rest
        """
        elapsed = time.time() - self.cycle_start_time
        position_in_cycle = elapsed % self.cycle_seconds

        if position_in_cycle < self.run_seconds:
            return True
        else:
            return False

    def get_status(self) -> dict:
        """
        Get current duty cycle status.

        Returns:
            Dictionary with status information
        """
        elapsed = time.time() - self.cycle_start_time
        position_in_cycle = elapsed % self.cycle_seconds

        if position_in_cycle < self.run_seconds:
            state = "ON"
            time_in_state = position_in_cycle
        else:
            state = "REST"
            time_in_state = position_in_cycle - self.run_seconds

        return {
            "pattern": self.pattern,
            "state": state,
            "time_in_state": round(time_in_state, 1),
            "cycle_progress_percent": round((position_in_cycle / self.cycle_seconds) * 100, 1),
            "duty_cycle_percent": self.get_duty_cycle_percent(),
            "estimated_lifetime_hours": self.get_estimated_lifetime(),
        }

    def get_duty_cycle_percent(self) -> float:
        """
        Get duty cycle percentage.

        Returns:
            Duty cycle as percentage (0-100)
        """
        if self.cycle_seconds == 0:
            return 100.0

        return (self.run_seconds / self.cycle_seconds) * 100

    def get_estimated_lifetime(self, total_hours: float = 8000) -> float:
        """
        Get estimated remaining lifetime in years.

        Assumes continuous operation at current duty cycle.

        Args:
            total_hours: Total laser lifetime in hours (default 8000)

        Returns:
            Estimated lifetime in years
        """
        duty_cycle = self.get_duty_cycle_percent() / 100
        effective_hours = total_hours * (duty_cycle)
        years = effective_hours / (24 * 365)

        return round(years, 1)

    def get_status_report(self) -> str:
        """
        Get detailed duty cycle status report.

        Returns:
            Human-readable status report
        """
        status = self.get_status()

        lines = ["PMS5003 Duty Cycle Status:"]
        lines.append("=" * 50)
        lines.append(f"Pattern: {self.pattern}")
        lines.append(f"Laser State: {status['state']}")
        lines.append(f"Time in State: {status['time_in_state']:.1f}s")
        lines.append(f"Cycle Progress: {status['cycle_progress_percent']:.1f}%")
        lines.append(f"Duty Cycle: {status['duty_cycle_percent']:.0f}%")
        lines.append("=" * 50)

        lines.append(f"\nConfiguration:")
        lines.append(f"  Run Time: {self.run_seconds}s")
        lines.append(f"  Rest Time: {self.rest_seconds}s")
        lines.append(f"  Total Cycle: {self.cycle_seconds}s")

        lines.append(f"\nEstimated Lifetime:")
        lifetime_years = self.get_estimated_lifetime()
        lines.append(f"  {lifetime_years} years at current duty cycle")
        lines.append(f"  ({lifetime_years * 365 * 24:.0f} hours)")

        lines.append("\nPatterns available:")
        for name, config in self.PATTERNS.items():
            duty = (config["run_seconds"] / (config["run_seconds"] + config["rest_seconds"])) * 100
            lifetime = (duty / 100) * self.get_estimated_lifetime()
            lines.append(f"  {name:12} {duty:5.0f}% duty → {lifetime:.1f} years")

        return "\n".join(lines)

    def get_next_state_change_in(self) -> float:
        """
        Get seconds until next duty cycle state change.

        Returns:
            Seconds until next change
        """
        elapsed = time.time() - self.cycle_start_time
        position_in_cycle = elapsed % self.cycle_seconds

        if position_in_cycle < self.run_seconds:
            # Currently ON, return time until REST
            return self.run_seconds - position_in_cycle
        else:
            # Currently REST, return time until ON
            return self.cycle_seconds - position_in_cycle


class DutyCycleScheduler:
    """
    Helper to integrate duty cycle checks into sensor reading loops.
    """

    def __init__(self, duty_cycle_manager: PMS5003DutyCycleManager):
        """
        Initialize scheduler.

        Args:
            duty_cycle_manager: PMS5003DutyCycleManager instance
        """
        self.manager = duty_cycle_manager
        self.last_state = self.manager.should_laser_be_on()

    def check_and_log_state_change(self) -> bool:
        """
        Check if laser state has changed and log it.

        Returns:
            True if state changed, False otherwise
        """
        current_state = self.manager.should_laser_be_on()

        if current_state != self.last_state:
            self.last_state = current_state
            state_str = "ON" if current_state else "REST"
            logger.info(f"PMS5003 laser state changed to: {state_str}")
            return True

        return False

    def get_next_check_delay(self) -> float:
        """
        Get recommended delay before next check (seconds).

        Returns scheduling hint to optimize check frequency.

        Returns:
            Seconds to wait before next check
        """
        # Check frequently enough to catch state changes
        # but not so frequently as to spam logs
        time_until_change = self.manager.get_next_state_change_in()

        # Check at 25%, 50%, 75%, 100% of remaining time
        if time_until_change > 30:
            return time_until_change / 4
        elif time_until_change > 10:
            return time_until_change / 2
        else:
            return min(time_until_change, 1.0)
