"""Utility functions for MAME"""

# Standard Library
import json
import os
from lxml import etree

# Lutris Modules
from lutris import settings
from lutris.util.log import logger

CACHE_DIR = os.path.join(settings.CACHE_DIR, "mame")


def simplify_manufacturer(manufacturer):
    """Give simplified names for some manufacturers"""
    manufacturer_map = {
        "Amstrad plc": "Amstrad",
        "Apple Computer": "Apple",
        "Commodore Business Machines": "Commodore",
    }
    return manufacturer_map.get(manufacturer, manufacturer)


def is_game(machine):
    """Return True if the given machine game is an original arcade game
    Clones return False
    """
    return (
        machine.attrib["isbios"] == "no"
        and machine.attrib["isdevice"] == "no"
        and machine.attrib["runnable"] == "yes"
        and "romof" not in machine.attrib
        # FIXME: Filter by the machines that accept coins, but not like that
        # and "coin" in machine.find("input").attrib
    )


def has_software_list(machine):
    """Return True if the machine has an associated software list"""
    _has_software_list = False
    for elem in machine:
        if elem.tag == "device_ref" and elem.attrib["name"] == "software_list":
            _has_software_list = True
    return _has_software_list


def is_system(machine):
    """Given a machine XML tag, return True if it is a computer, console or
    handheld.
    """
    if (
        machine.attrib.get("runnable") == "no"
        or machine.attrib.get("isdevice") == "yes"
        or machine.attrib.get("isbios") == "yes"
    ):
        return False
    return has_software_list(machine)


def iter_machines(xml_path, filter_func=None):
    """Iterate through machine nodes in the MAME XML"""
    try:
        context = etree.iterparse(xml_path, events=("end",), tag="machine")
        for _, machine in context:
            if filter_func and not filter_func(machine):
                continue
            yield machine
            machine.clear()  # Release memory for the processed node
        del context  # Clean context at the end
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Failed to read MAME XML: %s", ex)
        return []


def get_machine_info(machine):
    """Return human readable information about a machine node"""

    def attrib_to_dict(element):
        """Convert lxml _Attrib to a Python dictionary"""
        return dict(element.attrib) if element is not None else {}

    return {
        "description": machine.find("description").text if machine.find("description") is not None else None,
        "manufacturer": simplify_manufacturer(
            machine.find("manufacturer").text if machine.find("manufacturer") is not None else None
        ),
        "year": machine.find("year").text if machine.find("year") is not None else None,
        "roms": [attrib_to_dict(rom) for rom in machine.findall("rom")],
        "ports": [attrib_to_dict(port) for port in machine.findall("port")],
        "devices": [
            {
                "info": attrib_to_dict(device),
                "name": "".join([instance.attrib["name"] for instance in device.findall("instance")]),
                "briefname": "".join([instance.attrib["briefname"] for instance in device.findall("instance")]),
                "extensions": [extension.attrib["name"] for extension in device.findall("extension")],
            }
            for device in machine.findall("device")
        ],
        "input": attrib_to_dict(machine.find("input")),
        "driver": attrib_to_dict(machine.find("driver")),
    }


def get_supported_systems(xml_path, force=False):
    """Return supported systems (computers and consoles) supported.
    From the full XML list extracted from MAME, filter the systems that are
    runnable, not clones and have the ability to run software.
    """
    systems_cache_path = os.path.join(CACHE_DIR, "systems.json")
    if os.path.exists(systems_cache_path) and not force:
        with open(systems_cache_path, "r", encoding="utf-8") as systems_cache_file:
            try:
                systems = json.load(systems_cache_file)
            except json.JSONDecodeError:
                logger.error("Failed to read systems cache %s", systems_cache_path)
                systems = None
        if systems:
            return systems
    systems = {machine.attrib["name"]: get_machine_info(machine) for machine in iter_machines(xml_path, is_system)}
    if not systems:
        return {}
    with open(systems_cache_path, "w", encoding="utf-8") as systems_cache_file:
        json.dump(systems, systems_cache_file, indent=2)
    return systems


def cache_supported_systems(xml_path, force=False):
    """
    Create or update the cache of supported systems.
    Populates the cache file with runnable, non-clone systems that can run software.
    """
    systems_cache_path = os.path.join(CACHE_DIR, "systems.json")
    if os.path.exists(systems_cache_path) and not force:
        logger.info("Cache already exists and force is not set. Skipping update.")
        return

    systems = {machine.attrib["name"]: get_machine_info(machine) for machine in iter_machines(xml_path, is_system)}
    if not systems:
        logger.warning("No systems found to cache.")
        return

    try:
        with open(systems_cache_path, "w", encoding="utf-8") as systems_cache_file:
            json.dump(systems, systems_cache_file, indent=2)
        logger.info("Cache successfully created at %s", systems_cache_path)
    except (IOError, OSError) as e:
        logger.error("Failed to write systems cache: %s", e)


def get_games(xml_path):
    """Return a list of all games"""
    return {machine.attrib["name"]: get_machine_info(machine) for machine in iter_machines(xml_path, is_game)}
