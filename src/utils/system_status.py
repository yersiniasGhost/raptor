import psutil


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
