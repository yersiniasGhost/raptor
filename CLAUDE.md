# Project: Raptor IIoT firmware code base.
## Project description
This code runs on a single board computer (called raptor) and interfaces with hardware components in a solar microgrid.  Data is collected through modbus, canbus and sensor readings.
Data is sent periodically to a MQTT server for processing.   
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

