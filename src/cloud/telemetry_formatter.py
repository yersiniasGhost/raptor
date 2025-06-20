#!/usr/bin/env python3
"""
Telemetry Data Formatter Utility
Provides common formatting functions for MQTT and other telemetry protocols
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from config.mqtt_config import FORMAT_LINE_PROTOCOL, FORMAT_FLAT, FORMAT_HIER


@dataclass
class TelemetryPoint:
    """Standard telemetry data point structure"""
    measurement: str
    tags: Dict[str, str]
    fields: Dict[str, Any]
    timestamp: Optional[int] = None



    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = int(time.time() * 1000000000)  # nanosecond precision


class TelemetryFormatter:
    """
    Utility class for formatting telemetry data in various protocols
    """



    def __init__(self, raptor_id: str, format_type: str = FORMAT_LINE_PROTOCOL):
        self.raptor_id = raptor_id
        self.format_type = format_type



    def format_line_protocol(self, telemetry_points: List[TelemetryPoint]) -> List[str]:
        """
        Format telemetry points as InfluxDB line protocol

        Args:
            telemetry_points: List of TelemetryPoint objects

        Returns:
            List of line protocol formatted strings
        """
        lines = []

        for point in telemetry_points:
            # Add raptor_id to tags
            all_tags = {"raptor": self.raptor_id, **point.tags}

            # Format tags
            tag_str = ','.join([f"{k}={v}" for k, v in all_tags.items()])

            # Format fields
            field_strs = []
            for key, value in point.fields.items():
                if isinstance(value, str):
                    field_strs.append(f'{key}="{value}"')
                elif isinstance(value, bool):
                    field_strs.append(f'{key}={str(value).lower()}')
                else:
                    field_strs.append(f'{key}={value}')

            field_str = ','.join(field_strs)

            # Create line protocol string
            line = f"{point.measurement},{tag_str} {field_str} {point.timestamp}"
            lines.append(line)

        return lines



    def format_hierarchical(self, telemetry_points: List[TelemetryPoint]) -> Dict[str, Any]:
        """
        Format telemetry points as hierarchical JSON structure

        Args:
            telemetry_points: List of TelemetryPoint objects

        Returns:
            Hierarchical dictionary structure
        """
        result = {
            "raptor_id": self.raptor_id,
            "timestamp": int(time.time() * 1000),
            "measurements": {}
        }

        for point in telemetry_points:
            measurement_name = point.measurement
            if measurement_name not in result["measurements"]:
                result["measurements"][measurement_name] = []

            measurement_data = {
                "tags": point.tags,
                "fields": point.fields,
                "timestamp": point.timestamp
            }
            result["measurements"][measurement_name].append(measurement_data)

        return result



    def format_flat(self, telemetry_points: List[TelemetryPoint]) -> Dict[str, Any]:
        """
        Format telemetry points as flat key-value structure

        Args:
            telemetry_points: List of TelemetryPoint objects

        Returns:
            Flat dictionary with dotted notation keys
        """
        result = {
            "raptor_id": self.raptor_id,
            "timestamp": int(time.time() * 1000)
        }

        for point in telemetry_points:
            base_key = point.measurement

            # Add tag information to key
            if point.tags:
                tag_suffix = "_".join([f"{k}_{v}" for k, v in point.tags.items()])
                base_key = f"{base_key}_{tag_suffix}"

            # Add fields with dotted notation
            for field_name, field_value in point.fields.items():
                key = f"{base_key}.{field_name}"
                result[key] = field_value

        return result



    def format_telemetry_data(self, telemetry_points: List[TelemetryPoint]) -> Dict[str, Any]:
        """
        Format telemetry data according to configured format type

        Args:
            telemetry_points: List of TelemetryPoint objects

        Returns:
            Formatted data with mode and data fields
        """
        if self.format_type == FORMAT_LINE_PROTOCOL:
            return {
                "mode": FORMAT_LINE_PROTOCOL,
                "data": self.format_line_protocol(telemetry_points)
            }
        elif self.format_type == FORMAT_HIER:
            return {
                "mode": FORMAT_HIER,
                "data": self.format_hierarchical(telemetry_points)
            }
        elif self.format_type == FORMAT_FLAT:
            return {
                "mode": FORMAT_FLAT,
                "data": self.format_flat(telemetry_points)
            }
        else:
            raise ValueError(f"Unsupported format type: {self.format_type}")


def create_system_telemetry_points(system_measurements: Dict[str, Any]) -> List[TelemetryPoint]:
    """
    Convert system measurements dictionary to TelemetryPoint objects

    Args:
        system_measurements: Dictionary with structure {system: {hardware: {device: {field: value}}}}

    Returns:
        List of TelemetryPoint objects
    """
    telemetry_points = []

    for system, system_data in system_measurements.items():
        measurement_name = system.replace(' ', '_')

        for hardware_id, hardware_data in system_data.items():
            for device_id, device_data in hardware_data.items():
                if device_data:  # Only process if there's actual data
                    tags = {
                        "hardware_id": str(hardware_id),
                        "device_id": str(device_id)
                    }

                    # Filter out non-numeric fields or convert them appropriately
                    fields = {}
                    for key, value in device_data.items():
                        if isinstance(value, (int, float, bool)):
                            fields[key] = value
                        elif isinstance(value, str):
                            # Only include string fields if they're meaningful
                            if value and value.lower() not in ['none', 'null', '']:
                                fields[f"{key}_str"] = value

                    if fields:  # Only create point if we have valid fields
                        point = TelemetryPoint(
                            measurement=measurement_name,
                            tags=tags,
                            fields=fields
                        )
                        telemetry_points.append(point)

    return telemetry_points


def create_actuator_telemetry_points(test_metrics_list: List[Dict[str, Any]],
                                     measurement_name: str = "actuator_stress_test") -> List[TelemetryPoint]:
    """
    Convert actuator test metrics to TelemetryPoint objects

    Args:
        test_metrics_list: List of TestMetrics dictionaries
        measurement_name: Base measurement name for the telemetry

    Returns:
        List of TelemetryPoint objects
    """
    telemetry_points = []

    for metrics in test_metrics_list:
        tags = {
            "actuator_id": str(metrics.get("actuator_id", "unknown")),
            "operation_type": str(metrics.get("operation_type", "unknown")),
            "cycle_number": str(metrics.get("cycle_number", 0))
        }

        fields = {}
        for key, value in metrics.items():
            if key not in ["actuator_id", "operation_type", "timestamp"]:
                if isinstance(value, (int, float, bool)):
                    fields[key] = value
                elif isinstance(value, str) and value:
                    if key == "error_flags" and value:
                        fields["has_errors"] = True
                        fields["error_count"] = len(value.split(","))
                    else:
                        fields[f"{key}_str"] = value

        if fields:
            # Use the timestamp from metrics if available
            timestamp = metrics.get("timestamp")
            if timestamp:
                timestamp = int(timestamp * 1000000000)  # Convert to nanoseconds

            point = TelemetryPoint(
                measurement=measurement_name,
                tags=tags,
                fields=fields,
                timestamp=timestamp
            )
            telemetry_points.append(point)

    return telemetry_points