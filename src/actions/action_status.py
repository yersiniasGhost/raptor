from enum import Enum


class ActionStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    INVALID_PARAMS = "invalid_parameters"
    NOT_IMPLEMENTED = "not_implemented"
    PERMISSION_DENIED = "permission_denied"
    NO_RESPONSE = "no_response"
