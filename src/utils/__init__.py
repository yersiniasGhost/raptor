from .singleton import Singleton
from .envvars import EnvVars
from .linux_utils import run_command, kill_screen_session, start_screen_session
from .mac_address import get_mac_address
from .logger import LogManager
from .vmc_types import JSON

SERVICES = ["iot-controller", "vmc-ui", "cmd-controller", "network-watchdog", "reverse-tunnel"]

