from .singleton import Singleton
from .envvars import EnvVars
from .linux_utils import run_command, kill_screen_session, start_screen_session, check_interface
from .linux_utils import set_tcp_interface, get_local_ip
from .mac_address import get_mac_address
from .logger import LogManager
from .vmc_types import JSON
from .system_status import get_git_branches, get_current_branch, COMMON_PATH

SERVICES = ["cellular-init", "iot-controller", "vmc-ui", "cmd-controller", "network-watchdog"]

