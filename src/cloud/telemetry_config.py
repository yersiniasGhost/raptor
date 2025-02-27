from dataclasses import dataclass

MQTT_MODE = "mqtt"
REST_MODE = "rest"


@dataclass(frozen=True)
class TelemetryConfig:
    mode: str
    interval: int
    status_path: str
    telemetry_path: str
    alarms_path: str
    messages_path: str
    response_path: str

    @classmethod
    def from_dict(cls, data: dict) -> 'TelemetryConfig':
        """Create an MQTTConfig instance from a dictionary"""
        return cls(
            mode=data['mode'],
            interval=int(data['interval']),
            status_path=data.get("status_path", ""),
            telemetry_path=data['telemetry_path'],
            alarms_path=data.get("alarms_path", ""),
            messages_path=data['messages_path'],
            response_path=data.get("response_path", "cmd_response")
        )

