from dataclasses import dataclass

MQTT_MODE = "mqtt"
REST_MODE = "rest"


@dataclass(frozen=True)
class TelemetryConfig:
    mode: str
    interval: int
    root_path: str
    status_path: str
    telemetry_path: str
    alarms_path: str
    messages_path: str
    response_path: str
    sampling: int
    averaging_method: str

    @classmethod
    def from_dict(cls, data: dict) -> 'TelemetryConfig':
        """Create an MQTTConfig instance from a dictionary"""
        return cls(
            mode=data['mode'],
            interval=int(data['interval']),
            root_path=data['root_path'],
            status_path=data.get("status_path", ""),
            telemetry_path=data['telemetry_path'],
            alarms_path=data.get("alarms_path", ""),
            messages_path=data['messages_path'],
            response_path=data.get("response_path", "cmd_response"),
            sampling=data.get("sampling", 3),
            averaging_method=data.get('averaging_method', "mean")
        )

    @property
    def telemetry_topic(self):
        return f"{self.root_path}/{self.telemetry_path}"

    @property
    def status_topic(self):
        return f"{self.root_path}/{self.status_path}"

    @property
    def response_topic(self):
        return f"{self.root_path}/{self.response_path}"

    @property
    def alarms_topic(self):
        return f"{self.root_path}/{self.alarms_path}"

    @property
    def messages_topic(self):
        return f"{self.root_path}/{self.messages_path}"
