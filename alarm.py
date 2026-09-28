#!/usr/bin/env python3
"""
Alarm Clock CLI - A simple timezone-aware alarm clock.

Components:
- Alarm: Data model for alarms
- AlarmManager: CRUD operations and alarm checking
- Notifier/TerminalNotifier: Dependency-injected notification system
- TimeProvider/SystemTimeProvider: Dependency-injected time source
- CLI: Command-line interface
"""

import sys
import uuid
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration & Utilities
# ============================================================================

# Alarm storage file (JSON format)
ALARMS_FILE = Path.home() / ".alarms.json"

# Map user-friendly timezone aliases to IANA timezone identifiers
TIMEZONE_ALIASES = {
    "IST": "Asia/Kolkata",  # India Standard Time
}

def normalize_timezone(tz: str) -> str:
    """
    Normalize timezone string using aliases if available.

    Args:
        tz: Timezone string (with or without alias)

    Returns:
        Normalized IANA timezone string
    """
    return TIMEZONE_ALIASES.get(tz, tz)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Alarm:
    """Represents a single alarm with timezone support."""

    time: datetime  # Required: datetime with timezone info
    timezone: str = "IST"  # Default timezone: IST
    label: str = "Alarm"
    status: str = "PENDING"  # Status: PENDING, TRIGGERED, CANCELLED
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __post_init__(self):
        """Validate alarm data after initialization."""
        # Normalize timezone (handle aliases like IST -> Asia/Kolkata)
        self.timezone = normalize_timezone(self.timezone)

        # Validate timezone
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid timezone '{self.timezone}': {e}")

        # Validate status
        if self.status not in ("PENDING", "TRIGGERED", "CANCELLED"):
            raise ValueError(f"Invalid status: {self.status}")

        # Validate time has timezone info
        if self.time.tzinfo is None:
            raise ValueError("Alarm time must have timezone info")

    def to_dict(self) -> dict:
        """Convert alarm to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "time": self.time.isoformat(),
            "label": self.label,
            "status": self.status,
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        """Create alarm from dictionary (from JSON deserialization)."""
        return cls(
            id=data["id"],
            time=datetime.fromisoformat(data["time"]),
            label=data["label"],
            status=data["status"],
            timezone=data["timezone"],
        )


# ============================================================================
# Notifier (Dependency Injection)
# ============================================================================

class Notifier(ABC):
    """Abstract notifier interface for dependency injection."""

    @abstractmethod
    def notify(self, alarm: Alarm) -> None:
        """Notify user about an alarm."""
        pass


class TerminalNotifier(Notifier):
    """Notifies user via terminal output with visual and audio cues."""

    def notify(self, alarm: Alarm) -> None:
        """Print alarm notification to terminal."""
        bell = "\a"  # ASCII bell character
        print(f"\n{bell}🔔 ALARM TRIGGERED!")
        print(f"   Label: {alarm.label}")
        print(f"   Alarm ID: {alarm.id}")
        print(f"   Scheduled Time: {alarm.time}")
        print(f"   Timezone: {alarm.timezone}\n")


# ============================================================================
# Time Provider (Dependency Injection)
# ============================================================================

class TimeProvider(ABC):
    """Abstract time provider for dependency injection and testability."""

    @abstractmethod
    def now(self, tz: str) -> datetime:
        """Get current time in specified timezone."""
        pass


class SystemTimeProvider(TimeProvider):
    """Uses system clock for current time."""

    def now(self, tz: str) -> datetime:
        """Return current time in specified timezone."""
        try:
            zone = ZoneInfo(tz)
        except (KeyError, ValueError):
            raise ValueError(f"Invalid timezone: {tz}")
        return datetime.now(zone)


class MockTimeProvider(TimeProvider):
    """Mock time provider for testing - returns a fixed time."""

    def __init__(self, mock_time: datetime):
        self.mock_time = mock_time

    def now(self, tz: str) -> datetime:
        """Return mocked time."""
        return self.mock_time


# ============================================================================
# Alarm Manager
# ============================================================================

class AlarmManager:
    """Manages alarm CRUD operations and checking for due alarms."""

    def __init__(self, time_provider: TimeProvider, notifier: Notifier, persist: bool = True):
        """
        Initialize alarm manager with dependency injection.

        Args:
            time_provider: TimeProvider instance for getting current time
            notifier: Notifier instance for triggering alarms
            persist: If True, load/save alarms from disk (default: True)
        """
        self.alarms: List[Alarm] = []
        self.time_provider = time_provider
        self.notifier = notifier
        self.persist = persist
        if persist:
            self.load_alarms()  # Load persisted alarms from disk

    def add_alarm(
        self,
        dt: datetime,
        timezone: str = "IST",
        label: str = "Alarm"
    ) -> Alarm:
        """
        Add a new alarm.

        Args:
            dt: datetime object representing alarm time (with or without timezone)
            timezone: IANA timezone string or alias (default: "IST")
            label: Human-readable label for the alarm

        Returns:
            Created Alarm object

        Raises:
            ValueError: If timezone is invalid or time is in the past
        """
        # Normalize timezone (handle aliases like IST -> Asia/Kolkata)
        timezone = normalize_timezone(timezone)

        # Validate timezone
        try:
            zone = ZoneInfo(timezone)
        except (KeyError, ValueError):
            raise ValueError(f"Invalid timezone: {timezone}")

        # Ensure datetime has timezone info
        # If naive, assume it's in the provided timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=zone)

        # Check if alarm time is in the past
        now = self.time_provider.now(timezone)
        if dt <= now:
            raise ValueError("Alarm time cannot be in the past or present")

        # Create and store alarm
        alarm = Alarm(
            time=dt,
            timezone=timezone,
            label=label,
            status="PENDING"
        )
        self.alarms.append(alarm)
        self.save_alarms()
        return alarm

    def list_alarms(self) -> List[Alarm]:
        """
        Get all alarms.

        Returns:
            List of all alarms (pending, triggered, and cancelled)
        """
        return self.alarms.copy()

    def cancel_alarm(self, alarm_id: str) -> bool:
        """
        Cancel an alarm by ID.

        Args:
            alarm_id: ID of the alarm to cancel

        Returns:
            True if alarm was cancelled, False if not found
        """
        for alarm in self.alarms:
            if alarm.id == alarm_id:
                alarm.status = "CANCELLED"
                self.save_alarms()
                return True
        return False

    def check_due_alarms(self) -> List[Alarm]:
        """
        Check for alarms that are due and trigger them.

        Important: Each alarm triggers only once. After triggering,
        its status changes from PENDING to TRIGGERED and won't trigger again.

        Returns:
            List of alarms that just triggered
        """
        triggered = []
        for alarm in self.alarms:
            # Skip if alarm is already triggered or cancelled
            if alarm.status != "PENDING":
                continue

            # Check if current time >= alarm time
            now = self.time_provider.now(alarm.timezone)
            if now >= alarm.time:
                # Mark as triggered (prevents duplicate triggers)
                alarm.status = "TRIGGERED"
                self.notifier.notify(alarm)
                triggered.append(alarm)

        # Save if any alarms were triggered
        if triggered:
            self.save_alarms()

        return triggered

    def clear(self) -> None:
        """Clear all alarms (used for Ctrl+C cleanup)."""
        self.alarms.clear()

    def save_alarms(self) -> None:
        """Save alarms to JSON file for persistence."""
        if not self.persist:
            return
        try:
            data = [alarm.to_dict() for alarm in self.alarms]
            with open(ALARMS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save alarms to {ALARMS_FILE}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to serialize alarms as JSON: {e}")

    def load_alarms(self) -> None:
        """Load alarms from JSON file if it exists."""
        try:
            if ALARMS_FILE.exists():
                with open(ALARMS_FILE, "r") as f:
                    data = json.load(f)
                    self.alarms = [Alarm.from_dict(item) for item in data]
        except (IOError, OSError) as e:
            logger.warning(f"Failed to load alarms from {ALARMS_FILE}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Alarms file is corrupted (invalid JSON): {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"Alarms file has invalid alarm data: {e}")


# ============================================================================
# CLI Utilities
# ============================================================================

def parse_datetime(date_str: str, time_str: str, tz: str) -> datetime:
    """
    Parse date and time strings into a timezone-aware datetime object.

    Args:
        date_str: Date in DD:MM:YYYY format
        time_str: Time in HH:MM:SS format
        tz: IANA timezone string or alias (e.g., "IST")

    Returns:
        datetime object with timezone info

    Raises:
        ValueError: If format is invalid
    """
    # Normalize timezone (handle aliases)
    tz = normalize_timezone(tz)

    # Validate timezone
    try:
        zone = ZoneInfo(tz)
    except (KeyError, ValueError):
        raise ValueError(f"Invalid timezone: {tz}")

    try:
        # Parse date: DD:MM:YYYY
        date_parts = date_str.split(":")
        if len(date_parts) != 3:
            raise ValueError("Date format should be DD:MM:YYYY")
        day, month, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

        # Parse time: HH:MM:SS
        time_parts = time_str.split(":")
        if len(time_parts) != 3:
            raise ValueError("Time format should be HH:MM:SS")
        hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])

        # Create timezone-aware datetime
        dt = datetime(year, month, day, hour, minute, second, tzinfo=zone)
        return dt

    except ValueError as e:
        if "Invalid timezone" in str(e):
            raise
        raise ValueError(f"Invalid date/time: {e}")


# ============================================================================
# CLI Commands
# ============================================================================

def handle_add(args: List[str], manager: AlarmManager) -> None:
    """
    Handle 'add' command.

    Usage: add DD:MM:YYYY HH:MM:SS [timezone] [--label LABEL]

    Examples:
        add 28:09:2026 14:30:00 IST --label "Meeting"
        add 28:09:2026 09:00:00  # Uses default IST and label
        add 28:09:2026 15:30:00 UTC --label "Call"
    """
    if len(args) < 2:
        print("❌ Error: add requires at least date and time")
        print("Usage: add DD:MM:YYYY HH:MM:SS [timezone] [--label LABEL]")
        return

    date_str = args[0]
    time_str = args[1]
    timezone = "IST"  # Default timezone
    label = "Alarm"

    # Parse optional arguments
    i = 2
    while i < len(args):
        if args[i] == "--label":
            if i + 1 >= len(args):
                print("❌ Error: --label requires a value")
                return
            label = args[i + 1]
            i += 2
        else:
            # Treat as timezone
            timezone = args[i]
            i += 1

    try:
        dt = parse_datetime(date_str, time_str, timezone)
        alarm = manager.add_alarm(dt, timezone, label)
        print(f"✅ Alarm added!")
        print(f"   ID: {alarm.id}")
        print(f"   Label: {alarm.label}")
        print(f"   Time: {alarm.time}")
        print(f"   Timezone: {alarm.timezone}")
    except ValueError as e:
        print(f"❌ Error: {e}")


def handle_list(manager: AlarmManager) -> None:
    """Handle 'list' command: display all alarms."""
    alarms = manager.list_alarms()

    if not alarms:
        print("📭 No alarms set.")
        return

    print("\n📋 Alarms:")
    print("-" * 70)
    for alarm in alarms:
        # Status icon
        if alarm.status == "PENDING":
            icon = "⏰"
        elif alarm.status == "TRIGGERED":
            icon = "✅"
        else:  # CANCELLED
            icon = "❌"

        print(f"{icon} [{alarm.id}] {alarm.label}")
        print(f"   Time: {alarm.time}")
        print(f"   Timezone: {alarm.timezone}")
        print(f"   Status: {alarm.status}")
    print("-" * 70 + "\n")


def handle_cancel(args: List[str], manager: AlarmManager) -> None:
    """
    Handle 'cancel' command.

    Usage: cancel <ALARM_ID>

    Example: cancel abc12345
    """
    if len(args) < 1:
        print("❌ Error: cancel requires alarm ID")
        print("Usage: cancel <ALARM_ID>")
        return

    alarm_id = args[0]
    if manager.cancel_alarm(alarm_id):
        print(f"✅ Alarm {alarm_id} cancelled.")
    else:
        print(f"❌ Alarm {alarm_id} not found.")


def handle_run(manager: AlarmManager) -> None:
    """
    Handle 'run' command: start alarm checking loop.

    This blocks until Ctrl+C is pressed.

    Note: For testing, mock the TimeProvider and call check_due_alarms()
    directly. Do not rely on actual time.sleep() in tests.
    """
    print("🚀 Alarm daemon started.")
    print("Press Ctrl+C to stop.\n")

    try:
        # Check for due alarms in a loop with 1-second polling interval
        while True:
            manager.check_due_alarms()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⛔ Alarm daemon stopped.")
        manager.clear()


def print_help() -> None:
    """Print help message."""
    help_text = """
╔════════════════════════════════════════════════════════════════╗
║          Alarm Clock CLI - Timezone-Aware Alarms              ║
╚════════════════════════════════════════════════════════════════╝

COMMANDS:

  add DD:MM:YYYY HH:MM:SS [timezone] [--label LABEL]
    Add a new alarm

    Examples:
      python alarm.py add 28:09:2026 14:30:00 IST --label "Meeting"
      python alarm.py add 28:09:2026 09:00:00          # Uses default IST
      python alarm.py add 28:09:2026 15:30:00 UTC      # Different timezone

  list
    Show all alarms (pending, triggered, and cancelled)

    Example:
      python alarm.py list

  cancel <ALARM_ID>
    Cancel an alarm by its ID

    Example:
      python alarm.py cancel abc12345

  run
    Start the alarm checking daemon (blocks until Ctrl+C)

    Example:
      python alarm.py run

DEFAULTS:
  - Timezone: IST (India Standard Time)
  - Label: "Alarm"

NOTES:
  - Date format: DD:MM:YYYY (day:month:year)
  - Time format: HH:MM:SS (24-hour)
  - Alarms cannot be set in the past
  - Each alarm triggers only once
  - Ctrl+C stops the daemon and clears all alarms
"""
    print(help_text)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main CLI entry point."""
    # Create manager with system time provider and terminal notifier
    time_provider = SystemTimeProvider()
    notifier = TerminalNotifier()
    manager = AlarmManager(time_provider, notifier)

    # Handle no arguments
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    try:
        if command == "add":
            handle_add(args, manager)
        elif command == "list":
            handle_list(manager)
        elif command == "cancel":
            handle_cancel(args, manager)
        elif command == "run":
            handle_run(manager)
        elif command in ("-h", "--help", "help"):
            print_help()
        else:
            print(f"❌ Unknown command: {command}")
            print("Run 'python alarm.py --help' for usage information.")

    except KeyboardInterrupt:
        print("\n⛔ Interrupted by user.")
        manager.clear()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
