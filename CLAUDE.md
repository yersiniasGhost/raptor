# Project: Raptor IIoT firmware code base.
## Project description
This code runs on a single board computer (called raptor) and interfaces with hardware components in a solar microgrid.  Data is collected through modbus, canbus and sensor readings.
Data is sent periodically to a MQTT server for processing.   
# CE+T Converter Operating Modes - Modbus Configuration Guide

## Overview
This guide provides Modbus register configurations for setting up your Sierra 25 CE+T converter in four different operating modes using the Inview S interface.

## Key Control Registers Reference

### Primary Control Registers
- **45301** - Override Maximum Consumed Power (AC-input Power Limitation)
- **45501** - Override Voltage SetPoint (DC Bus 1)
- **45503** - Override Power SetPoint (DC Bus 1)
- **45511** - Turn All Converters ON (DC Bus 1)
- **45512** - Turn All Converters OFF (DC Bus 1)
- **45101** - Turn All Converters ON (AC-output Global)
- **45102** - Turn All Converters OFF (AC-output Global)

### Configuration Registers (Key Settings)
- **41044** - Reinjection allowed (AC-input Modes)
- **41068** - Max Consumed Power (AC-input Power Limitation)
- **41071** - Sierra Mode (DC Modes - Battery charger activation)
- **40090** - Battery Presence (DC System)

---

## Mode 1: AC for Load + Battery Charging

**Purpose:** Comprehensive AC mode where grid power handles the load while simultaneously charging batteries.

### Modbus Configuration Sequence:

1. **Enable Battery Presence and Charging**
   ```
   Write to 40090: 1    # Enable battery presence
   Write to 41071: 1    # Activate battery charger mode
   ```

2. **Set AC Input Parameters**
   ```
   Write to 41044: 1    # Enable AC-in reinjection
   Write to 41068: -1   # No maximum power consumed (system capacity)
   Write to 45301: -1   # No peak shaving limit
   ```

3. **Configure DC Voltage for Charging**
   ```
   Write to 45501: 542  # Set DC voltage to 54.2V (multiplied by 10)
   Write to 45503: 0    # No power setpoint limitation
   ```

4. **Turn ON Systems**
   ```
   Write to 45101: 1    # Turn ON AC-output
   Write to 45511: 1    # Turn ON DC Bus (charger)
   ```

### Expected Behavior:
- Grid power supplies the load
- Batteries charge automatically based on voltage settings
- System switches between float and boost charging as needed

---

## Mode 2: AC Only - Batteries Disconnected

**Purpose:** Full AC power mode with battery charging disabled and minimal battery interaction.

### Modbus Configuration Sequence:

1. **Disable Battery Charging**
   ```
   Write to 41071: 0    # Deactivate battery charger mode
   Write to 45512: 1    # Turn OFF DC Bus
   ```

2. **Set AC-Only Operation**
   ```
   Write to 41044: 0    # Disable AC-in reinjection
   Write to 41068: -1   # No maximum power consumed
   Write to 45301: -1   # No peak shaving
   ```

3. **Ensure AC Output is Active**
   ```
   Write to 45101: 1    # Turn ON AC-output
   ```

4. **Optional: Disconnect Battery Physically**
   ```
   Write to 40090: 0    # Disable battery presence (if applicable)
   ```

### Expected Behavior:
- Grid handles entire electrical load
- No battery charging occurs
- System operates as AC pass-through
- Batteries remain in standby

---

## Mode 3: Low Batteries - Split Load (50% Battery + 50% AC)

**Purpose:** Balanced mode splitting load between battery power and AC input (50/50 split).

### Modbus Configuration Sequence:

1. **Enable Battery System**
   ```
   Write to 40090: 1    # Enable battery presence
   Write to 41071: 1    # Activate battery charger mode
   ```

2. **Set Power Limitation for 50% Split**
   ```
   # Calculate 50% of your total load capacity
   # Example: If total load is 4500W, set AC limit to 2250W
   Write to 41068: 225000  # 2250W (divided by 100 format)
   Write to 45301: 225000  # Set peak shaving to 2250W
   ```

3. **Configure DC Operation**
   ```
   Write to 45501: 480   # Set lower DC voltage (48.0V) to encourage battery use
   Write to 45503: 225000 # Set DC power setpoint to 2250W (50% of capacity)
   ```

4. **Enable Both Systems**
   ```
   Write to 45101: 1     # Turn ON AC-output
   Write to 45511: 1     # Turn ON DC Bus
   ```

### Expected Behavior:
- AC input limited to 50% of total capacity
- Battery provides remaining 50% of load
- System maintains power balance between sources
- Extends battery life during moderate discharge

---

## Mode 4: Batteries Charged - Handle Load from Battery

**Purpose:** Battery-priority mode where DC power handles the load with AC input disabled.

### Modbus Configuration Sequence:

1. **Prioritize Battery Operation**
   ```
   Write to 40090: 1    # Enable battery presence
   Write to 41071: 1    # Activate battery charger mode (for monitoring)
   ```

2. **Disable/Limit AC Input**
   ```
   Write to 41068: 0    # Set maximum consumed power to 0 (no AC consumption)
   Write to 45301: 0    # Set peak shaving to 0 (force battery operation)
   Write to 41044: 0    # Disable AC-in reinjection
   ```

3. **Configure Battery-Priority DC Settings**
   ```
   Write to 45501: 520   # Set DC voltage to 52.0V (battery discharge level)
   Write to 45503: -450000 # Negative power setpoint to force discharge
   ```

4. **Enable DC Output, Monitor AC**
   ```
   Write to 45511: 1     # Turn ON DC Bus
   Write to 45101: 1     # Keep AC-output available for monitoring
   ```

### Expected Behavior:
- Battery provides primary power to load
- AC input consumption minimized or disabled
- System monitors battery voltage and current
- Low voltage protection remains active

---

## Important Notes and Safety Considerations

### Battery Protection Settings
Always verify these protection settings are properly configured:

- **Low Voltage Disconnect:** Register 40311 (42.0V default)
- **High Voltage Stop:** Register 41005 (61.0V default)
- **Temperature Monitoring:** Registers 40121-40123

### Monitoring Registers
Monitor these key status registers:

- **30501** - DC Bus Voltage (multiplied by 10)
- **30502** - DC Bus Current (multiplied by 10)
- **30503** - DC Bus Power (divided by 100)
- **30321** - AC Input Voltage Phase 1
- **30121** - AC Output Voltage Phase 1

### Configuration Application
After making changes:
```
Write to 45601: 1    # Apply Configuration to Gateway
Write to 45021: 1    # Save XML User Configuration
```

### Mode Switching Best Practices

1. **Always check battery voltage before switching modes**
2. **Allow 10-15 seconds between mode changes**
3. **Monitor system status registers during transitions**
4. **Verify load requirements match mode capabilities**
5. **Test mode changes during low-load periods when possible**

### Emergency Procedures

**To immediately return to safe AC-only mode:**
```
Write to 45301: -1   # Remove AC power limitations
Write to 41068: -1   # Remove max consumed power limit
Write to 45101: 1    # Ensure AC output is ON
Write to 45512: 1    # Turn OFF DC bus if needed
```

This configuration guide should allow you to safely switch between operating modes while maintaining system protection and monitoring capabilities.

### Jobs running on raptor
* A UI called VMC-UI runs which allows users to see
all the data and control the raptor remotely.  It interfaces with the configuration, and hardware components
* A cmd-controller which listens to a MQTT server for commands.  All commands are implemented by src/actions.
* A iot-controller which reads and aggregates data and sends to the MQTT server.

## Project structure
- /data/*/ - Files used for hardware modbus maps, etc.
- /install - bash scripts used to configure new raptors.
- /src - main source code
  - /actions - actions the raptor can take through UI, commands and schedules
  - /api/v2 - vmc UI for engineering purposes
  - /cloud - code dealing with git, mqtt, and cloud interaction
  - /config - configuration classes
  - /database - SQLite3 database tools, and schema
  - /hardware - code to interact with hardware of different types
  - /jobs - entry point for iot-controller and cmd-controller
  - /utils - utility methods and classes

## Environment setup
- python environment set up on each raptor
- local development uses conda activate raptor
- 

