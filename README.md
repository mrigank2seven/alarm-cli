# Python CLI Alarm Clock

A simple, timezone-aware alarm clock CLI built entirely with Python standard library. Perfect for a 20-minute implementation exercise.

## Features

✅ **Add alarms** with timezone support (default: IST)
✅ **List alarms** with status indicators
✅ **Cancel alarms** by ID
✅ **Run daemon** that checks and triggers alarms
✅ **Timezone-aware** using `zoneinfo` (IANA timezones)
✅ **In-memory storage** (no database required)
✅ **Fully testable** with 38 unit/integration tests

## Installation

No external dependencies required! Only uses Python standard library (3.9+).

```bash
python alarm.py --help
```

## Usage

### Add an Alarm

```bash
# With timezone and label
python alarm.py add 30:09:2026 15:30:00 IST --label "Team Standup"

# With default timezone (IST)
python alarm.py add 30:09:2026 09:00:00 --label "Morning Standup"

# Different timezone
python alarm.py add 30:09:2026 10:15:00 UTC --label "Daily Sync"
```

**Format:**
```
add DD:MM:YYYY HH:MM:SS [timezone] [--label LABEL]
```

### List Alarms

```bash
python alarm.py list
```

Output shows:
- Status icons: ⏰ PENDING, ✅ TRIGGERED, ❌ CANCELLED
- Alarm ID, label, time, and status

### Cancel an Alarm

```bash
python alarm.py cancel <ALARM_ID>
```

### Run Alarm Daemon

```bash
python alarm.py run
```

Starts a checking loop that triggers alarms when due. Press Ctrl+C to stop.

## Architecture

```
Alarm (dataclass)
  ├─ id (UUID)
  ├─ time (datetime with timezone)
  ├─ label
  ├─ status (PENDING/TRIGGERED/CANCELLED)
  └─ timezone

AlarmManager
  ├─ add_alarm() → validates and stores
  ├─ list_alarms() → returns all
  ├─ cancel_alarm(id) → changes status
  └─ check_due_alarms() → triggers due alarms (once per alarm)

Notifier (dependency injection)
  └─ TerminalNotifier → prints to terminal with bell

TimeProvider (dependency injection)
  ├─ SystemTimeProvider → real system time
  └─ MockTimeProvider → for testing
```

## Design Decisions

1. **Dependency Injection**: `TimeProvider` and `Notifier` are injectable, making tests deterministic
2. **No Database**: In-memory list (data lost on exit), keeping it simple
3. **No time.sleep()**: Tests control time via MockTimeProvider
4. **Timezone Normalization**: "IST" → "Asia/Kolkata" for IANA compatibility
5. **Alarm Triggering Once**: Status changes PENDING → TRIGGERED, prevents duplicates
6. **UTC-agnostic**: Comparisons work correctly across timezones using datetime objects

## Running Tests

```bash
# All tests (38 total)
python -m unittest test_alarm -v

# Specific test class
python -m unittest test_alarm.TestAlarmManager -v

# Specific test
python -m unittest test_alarm.TestAlarmModel.test_alarm_creation_with_timezone -v
```

## Test Coverage

- **Alarm Model**: Creation, validation, timezone handling, uniqueness
- **AlarmManager**: CRUD, triggering logic, no-duplicate logic, timezone-aware comparisons
- **Timezone Handling**: Different timezones, DST compatibility, alias resolution
- **DateTime Parsing**: Format validation, timezone validation, error handling
- **Integration**: Complete workflows (add → list → cancel, add → trigger)

## Edge Cases Handled

- ✅ Alarm time in the past → rejected
- ✅ Invalid timezone → rejected with clear error
- ✅ Invalid date/time format → rejected
- ✅ Cancel non-existent alarm → returns False
- ✅ Alarm triggering twice → prevented via status tracking
- ✅ Ctrl+C interruption → clears alarms gracefully
- ✅ Timezone offset changes (DST) → handled by zoneinfo

## Non-Goals

❌ Database persistence
❌ Recurring alarms
❌ Snooze functionality  
❌ Sound/system notifications (text only)
❌ User authentication
❌ Config files

## Implementation Time

- **Design**: 3 minutes
- **Core Implementation**: 12 minutes  
- **Testing**: 5 minutes
- **Total**: ~20 minutes ✓

## Tech Stack

- **Language**: Python 3.9+
- **Modules**: `dataclasses`, `datetime`, `zoneinfo`, `uuid`, `abc`
- **Testing**: `unittest` (standard library)
- **CLI**: `sys.argv` (standard library)

## Example Session

```bash
# Add some alarms
$ python alarm.py add 30:09:2026 14:30:00 IST --label "Daily Standup"
✅ Alarm added! ID: 6ee8ee2b

$ python alarm.py add 30:09:2026 16:00:00 UTC --label "Sync with team"
✅ Alarm added! ID: f2a19c5d

# List them
$ python alarm.py list
📋 Alarms:
⏰ [6ee8ee2b] Daily Standup
   Time: 2026-09-30 14:30:00+05:30
   Timezone: Asia/Kolkata
   Status: PENDING
⏰ [f2a19c5d] Sync with team
   Time: 2026-09-30 16:00:00+00:00
   Timezone: UTC
   Status: PENDING

# Cancel one
$ python alarm.py cancel 6ee8ee2b
✅ Alarm 6ee8ee2b cancelled.

# Run daemon
$ python alarm.py run
🚀 Alarm daemon started. Press Ctrl+C to stop.
```

---

**Built for the 25-minute coding exercise challenge** 🎯
