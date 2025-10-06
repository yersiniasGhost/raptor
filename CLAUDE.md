# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raptor is IIoT firmware that runs on a single-board computer interfacing with solar microgrid hardware components. It collects data via Modbus, CANbus, and sensors, then sends telemetry to an MQTT server.

## System Architecture

### Core Components

**Three Main Services** (configured as systemd services via install/08-services.sh):

1. **VMC-UI** (`src/api/v2/vmc.py`) - FastAPI web interface for engineers to monitor and control the Raptor
   - Runs on port 8002 via uvicorn
   - Routes in `src/api/v2/routes/`
   - Templates in `src/api/v2/templates/`
   - Uses Jinja2 templating with static files

2. **IoT Controller** (`src/jobs/iot_controller.py`) - Data acquisition and telemetry
   - Periodically reads hardware devices (PV, Meter, BMS, Converters, IoT, Charge Controller, Generation)
   - Implements distributed sampling with configurable averaging (mean/median/mode)
   - Formats data as InfluxDB line protocol
   - Uploads to MQTT server with exponential backoff on failure
   - Stores local CSV files for debugging

3. **Command Controller** (`src/jobs/cmd_controller.py`) - MQTT command listener
   - Listens for commands on MQTT topics
   - Executes actions via ActionFactory pattern
   - Sends responses back to cloud

### Action System

Actions are defined in `src/actions/` following a plugin architecture:
- All actions inherit from `Action` base class (src/actions/base_action.py)
- Must implement `execute()` method returning `(ActionStatus, JSON)`
- Dynamically loaded by `ActionFactory` using naming convention: `{action_name}_action.py` → `{ActionName}Action` class
- Examples: firmware_update_action.py, reboot_action.py, systemctl_action.py

### Hardware Abstraction

Hardware devices are configured in SQLite database and instantiated via:
- `HardwareDeployment` dataclass wraps hardware instances with device configs and scan groups
- `instantiate_hardware_from_dict()` dynamically creates hardware instances from DB configuration
- Hardware drivers in `src/hardware/`:
  - `modbus/` - Modbus devices (InviewGateway, EveBattery, Tristar charge controller)
  - `simulators/` - Software simulators for testing without physical hardware
  - `adc/` - Analog-to-digital converters
  - `gpio_controller/` - GPIO relay control
  - `iot/` - IoT sensor interfaces

Each hardware instance has:
- `devices`: List of device configurations (MAC addresses, unit IDs)
- `scan_groups`: Organized register groups (DATA, ALARM, DIAGNOSTIC, CONTROL)
- `data_acquisition()`: Returns dict of register values

### Configuration & Database

- **SQLite3** (`src/database/database_manager.py`) - Single connection with WAL mode
  - Singleton pattern ensures one connection per process
  - Stores: hardware configs, telemetry buffer, MQTT config, raptor config
  - Schema: `src/database/` (migrations via database_migrator.py)

- **Config Classes** (`src/config/`):
  - `RaptorConfig` - raptor_id, firmware_tag, api_key
  - `MQTTConfig` - MQTT broker connection settings
  - `TelemetryConfig` - Sampling interval, averaging method, upload mode

### Modbus Device Operating Modes

For CE+T Converters (Sierra 25), the system supports 4 operating modes controlled via Modbus registers (see CLAUDE.md lines 5-226):
1. AC for Load + Battery Charging (registers 40090, 41071, 45501, etc.)
2. AC Only - Batteries Disconnected
3. Low Batteries - Split Load (50% Battery + 50% AC)
4. Batteries Charged - Handle Load from Battery

Key control registers: 45301 (AC power limit), 45501 (DC voltage), 45503 (DC power), 45511/45512 (DC bus on/off)

## Development Commands

### Environment Setup
```bash
# Activate Python environment
conda activate raptor  # Local development
# OR on device:
source /root/raptor/venv/bin/activate
```

### Running Services Locally
```bash
# Run VMC-UI (web interface)
cd src/api/v2
python vmc.py
# Access at http://localhost:8002

# Run IoT Controller (data acquisition)
python src/jobs/iot_controller.py -l  # -l for local CSV storage

# Run Command Controller (MQTT listener)
python src/jobs/cmd_controller.py
```

### Testing
```bash
# Run hardware-specific tests
python src/hardware/test_modbus_integration.py
python tests/modbus/test_modbus_device.py
```

### Deployment
```bash
# Installation scripts in install/
./install/01-setup-wifi.sh
./install/04-setup-cell.sh
./install/08-services.sh  # Creates systemd services

# Service management on device
sudo systemctl status vmc-ui
sudo systemctl status iot-controller
sudo systemctl status cmd-controller
sudo systemctl restart vmc-ui
```

### Viewing Logs
```bash
# Application logs (with rotation)
tail -f /root/raptor/src/jobs/iot-controller.log
tail -f /root/raptor/src/jobs/cmd-controller.log
tail -f /root/raptor/src/api/v2/vmc-ui.log

# Systemd journal
journalctl -u vmc-ui -f
journalctl -u iot-controller -f
```

## Key Design Patterns

### Singleton Pattern
- `DatabaseManager` - Ensures single DB connection per process
- `LogManager` - Centralized logging configuration
- Used via metaclass: `class Foo(metaclass=Singleton)`

### Factory Pattern
- `ActionFactory` - Dynamically loads and executes actions by name
- Converts snake_case action names to CamelCase class names

### Distributed Sampling
IoTController implements synchronized sampling across all hardware:
- Takes N samples distributed evenly over the telemetry interval
- Averages samples using configurable method (mean/median/mode)
- Single synchronized snapshot ensures temporal consistency across devices

### Simulator Mode
- Enabled via `EnvVars().enable_simulators`
- Allows testing without physical hardware
- Simulators in `src/hardware/simulators/` (PV panels, BMS, loads, weather)
- Historical data playback from CSV files in `data/weather/`

## Important Notes

- **Modbus Locking**: Hardware access is synchronized to prevent concurrent access conflicts
- **MQTT Resilience**: Both controllers implement exponential backoff and auto-reconnection
- **Telemetry Buffering**: Telemetry stored in SQLite before upload, cleared after successful transmission
- **Git Version**: UI displays firmware version from git tags via `git describe --tags --abbrev=0`
- **MAC Address**: Used as device identifier, obtained via `utils.get_mac_address()`

## File Structure
- `/data/` - Hardware Modbus maps, state configurations (e.g., Sierra25/sierra25_states.json)
- `/install/` - Bash scripts for Raptor provisioning and service setup
- `/src/actions/` - Command actions executed via MQTT
- `/src/api/v2/` - VMC-UI FastAPI application
- `/src/cloud/` - MQTT communication, firmware updates
- `/src/config/` - Configuration dataclasses
- `/src/database/` - SQLite management and schema
- `/src/hardware/` - Hardware driver implementations
- `/src/jobs/` - Entry points for main services
- `/src/utils/` - Utility functions and classes
- `/tests/` - Test files

## Adding a New Hardware Device

1. Create driver class in `src/hardware/{category}/` inheriting from `HardwareBase`
2. Implement required methods: `data_acquisition()`, `get_points()`, etc.
3. Add Modbus map JSON file to `/data/` if applicable
4. Add device configuration to database via VMC-UI or direct SQL
5. Configure scan_groups (DATA, ALARM, DIAGNOSTIC, CONTROL) in device config

## Adding a New Action

1. Create `src/actions/{action_name}_action.py`
2. Define class `{ActionName}Action(Action)`
3. Implement `async def execute(self, telemetry_config, mqtt_config) -> Tuple[ActionStatus, JSON]`
4. ActionFactory will automatically discover and load it
5. Trigger via MQTT: `{"action": "{action_name}", "params": {...}, "action_id": "..."}`
