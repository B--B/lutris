"""DuckStation Runner"""

import os.path
from gettext import gettext as _

from lutris.exceptions import MissingBiosError, MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger


class duckstation(Runner):
    human_name = _("DuckStation")
    description = _("PlayStation 1 Emulator")
    platforms = [_("Sony PlayStation")]
    runnable_alone = True
    runner_executable = "duckstation/DuckStation-x64.AppImage"
    flatpak_id = "org.duckstation.DuckStation"
    config_dir = os.path.expanduser("~/.local/share/duckstation/")
    config_file = os.path.join(config_dir, "settings.ini")
    bios_dir = os.path.join(config_dir, "bios")
    download_url = "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage"
    eu_bios_url = (
        "https://github.com/Abdess/retroarch_system/raw/5f96368f6dbad5851cdb16a5041fefec4bdcd305"
        "/Sony%20-%20PlayStation/scph1002.bin"
    )
    jp_bios_url = (
        "https://github.com/Abdess/retroarch_system/raw/5f96368f6dbad5851cdb16a5041fefec4bdcd305"
        "/Sony%20-%20PlayStation/scph1000.bin"
    )
    us_bios_url = (
        "https://github.com/Abdess/retroarch_system/raw/5f96368f6dbad5851cdb16a5041fefec4bdcd305"
        "/Sony%20-%20PlayStation/scph1001.bin"
    )
    bios_checksums = {
        "scph1000.bin": "239665b1a3dade1b5a52c06338011044",
        "scph1001.bin": "924e392ed05558ffdb115408c263dccf",
        "scph1002.bin": "54847e693405ffeb0359c6287434cbef",
    }
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "section": _("Graphics"),
            "help": _("Enters fullscreen mode immediately after starting."),
            "default": True,
        },
        {
            "option": "nofullscreen",
            "type": "bool",
            "label": _("No Fullscreen"),
            "section": _("Graphics"),
            "help": _("Prevents fullscreen mode from triggering if enabled."),
            "default": False,
        },
        {
            "option": "nogui",
            "type": "bool",
            "label": _("Batch Mode"),
            "section": _("Boot"),
            "help": _("Enables batch mode (exits after powering off)."),
            "default": True,
            "advanced": True,
        },
        {
            "option": "fastboot",
            "type": "bool",
            "label": _("Force Fastboot"),
            "section": _("Boot"),
            "help": _("Force fast boot."),
            "default": False,
        },
        {
            "option": "slowboot",
            "type": "bool",
            "label": _("Force Slowboot"),
            "section": _("Boot"),
            "help": _("Force slow boot."),
            "default": False,
        },
        {
            "option": "nocontroller",
            "type": "bool",
            "label": _("No Controllers"),
            "section": _("Controllers"),
            "help": _(
                "Prevents the emulator from polling for controllers. Try this option if you're "
                "having difficulties starting the emulator."
            ),
            "default": False,
        },
        {
            "option": "settings",
            "type": "file",
            "label": _("Custom configuration file"),
            "help": _(
                "Loads a custom settings configuration from the specified filename. "
                "Default settings applied if file not found."
            ),
            "default": config_file,
            "advanced": True,
        },
    ]

    def install(self, install_ui_delegate, version=None, callback=None):
        def on_runner_installed(*_args):
            bios_path = system.create_folder(self.bios_dir)
            bios_files = [
                (self.eu_bios_url, os.path.join(bios_path, "scph1002.bin")),
                (self.jp_bios_url, os.path.join(bios_path, "scph1000.bin")),
                (self.us_bios_url, os.path.join(bios_path, "scph1001.bin")),
            ]
            for url, path in bios_files:
                install_ui_delegate.download_install_file(url, path)
            if not self.bioses_checksum(bios_path):
                raise RuntimeError(_("Bad BIOS checksum"))
            logger.debug("BIOS check passed, finishing installation")
            if callback:
                callback()

        super().install(install_ui_delegate, version, on_runner_installed)

    # Duckstation uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def bioses_checksum(self, bios_path):
        """Check for correct bios files"""
        good_bios = {}
        for bios_file, checksum in self.bios_checksums.items():
            bios_file_path = os.path.join(bios_path, bios_file)
            if system.path_exists(bios_file_path):
                real_hash = system.get_md5_hash(bios_file_path)
                if real_hash == checksum:
                    logger.debug("%s Checksum : OK", bios_file)
                    good_bios[bios_file] = bios_file
        return good_bios

    def play(self):
        if not system.path_exists(self.bios_dir):
            raise MissingBiosError()

        arguments = self.get_command()
        runner_flags = {
            "nogui": "-batch",
            "fastboot": "-fastboot",
            "slowboot": "-slowboot",
            "fullscreen": "-fullscreen",
            "nofullscreen": "-nofullscreen",
            "nocontroller": "-nocontroller",
        }
        for option, flag in runner_flags.items():
            if self.runner_config.get(option):
                arguments.append(flag)
        arguments += ["-settings", self.config_file, "--"]

        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)
        arguments.append(rom)
        logger.debug("DuckStation starting with args: %s", arguments)
        return {"command": arguments}
