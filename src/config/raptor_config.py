from dataclasses import dataclass


@dataclass(frozen=True)
class RaptorConfig:
    raptor_id: str
    firmware_tag: str
    api_key: str


    @classmethod
    def from_dict(cls, data: dict) -> 'RaptorConfig':
        """Create an RaptorConfig instance from a dictionary"""
        return cls(
            raptor_id=data['raptor_id'],
            firmware_tag=data['firmware_tag'],
            api_key=data['api_key']
        )

