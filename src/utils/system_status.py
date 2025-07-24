from typing import Optional
import psutil
import subprocess

COMMON_PATH = "/root/raptor-common"


def collect_system_stats():
    # Get CPU usage as a percentage
    cpu_percent = psutil.cpu_percent(interval=1)

    # Get memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent

    # Get disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent

    # Get network info - bytes sent/received
    network = psutil.net_io_counters()
    bytes_sent = network.bytes_sent
    bytes_recv = network.bytes_recv

    # Temperature (if available)
    try:
        temperature = psutil.sensors_temperatures()['cpu_thermal'][0].current
    except:
        temperature = 0  # Set to 0 if not available

    return {
        'cpu_percent': cpu_percent,
        'memory_percent': memory_percent,
        'disk_percent': disk_percent,
        'bytes_sent': bytes_sent,
        'bytes_recv': bytes_recv,
        'temperature': temperature
    }


def get_git_branches(repo_path: Optional[str] = None, logger = None):
    """Get list of available git branches without fetching content"""
    cmd = ["git", "ls-remote", "--heads", "origin"]
    if repo_path:
        cmd = ["git", "-C", repo_path] + cmd[1:]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )
    if logger:
        logger.info(f"git ls-remote --heads origin returns: {result}")

    branches = []
    for line in result.stdout.splitlines():
        # Each line has format: "commit_hash refs/heads/branch_name"
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) >= 2:
            # Extract branch name from refs/heads/branch_name
            branch = parts[1].replace("refs/heads/", "")
            if branch and branch not in branches and not branch == "HEAD":
                branches.append(branch)

    return branches


def get_current_branch(repo_path: Optional[str] = None) -> str:
    """Get the name of the current git branch"""
    cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]

    if repo_path:
        # Use git -C to run command in different directory
        cmd = ["git", "-C", repo_path] + cmd[1:]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()
