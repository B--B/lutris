"""Observer for monitor display connection/disconnection events"""

import threading
import time
import pyudev

from lutris.util.graphics.xrandr import get_outputs, get_resolutions
from lutris.util.log import logger

_cache_lock = threading.Lock()  # Lock for cache updates


def reset_cache_on_display_event():
    """Clear cache when a display event is detected."""
    with _cache_lock:  # Ensure thread-safety while modifying the cache
        get_outputs.cache_clear()
        get_resolutions.cache_clear()
    time.sleep(1)
    update_cache()
    logger.debug("Display cache reset due to display connection or disconnection.")


def update_cache():
    """Force an update of the cache."""
    get_outputs()
    get_resolutions()


def device_event_handler(action, device):
    """Manage device add, remove, and change events."""
    logger.info("Received event: %s for device %s", action, device.sys_name)
    if action in {"add", "remove", "change"}:
        reset_cache_on_display_event()


def monitor_display_events():
    """Monitor udev for display connect/disconnect events and reset cache."""
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="drm")
    logger.debug("Starting Xrandr display observer...")

    def callback_wrapper(device):
        """Wrapper that passes the two arguments"""
        action = device.action
        device_event_handler(action, device)

    observer = pyudev.MonitorObserver(monitor, callback=callback_wrapper)
    observer.start()
    logger.info("Xrandr display observer started...")

    observer.join()


def start_monitor_thread():
    """Start monitoring in a separate thread."""
    monitor_thread = threading.Thread(target=monitor_display_events, daemon=True)
    monitor_thread.start()
