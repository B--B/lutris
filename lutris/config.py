"""Handle the game, runner and global system configurations."""

import os
import time
from enum import Enum
from shutil import copyfile

from lutris import settings, sysoptions
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.system import path_exists
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file


class ConfigLevel(Enum):
    """Enum class used for config levels"""
    GAME = "game"
    RUNNER = "runner"
    SYSTEM = "system"


def make_game_config_id(game_slug: str, timestamp: int) -> str:
    """Return a unique config id to avoid clashes between multiple games"""
    logger.debug("Writing new config for %s with timestamp %s", game_slug, timestamp)
    return f"{game_slug}-{timestamp}"


def write_game_config(game_slug: str, config: dict):
    """Writes a game config to disk"""
    timestamp = int(time.time())
    configpath = make_game_config_id(game_slug, timestamp)
    logger.debug("Writing game config to %s", configpath)
    config_filename = os.path.join(settings.CONFIG_DIR, f"games/{configpath}.yml")
    write_yaml_to_file(config, config_filename)
    return configpath


def duplicate_game_config(game_slug: str, source_config_id: str):
    """Copies an existing configuration file, giving it a new id that this function returns."""
    timestamp = int(time.time())
    new_config_id = make_game_config_id(game_slug, timestamp)
    logger.debug("Game config dupicated with id %s", new_config_id)
    src_path = os.path.join(settings.CONFIG_DIR, f"games/{source_config_id}.yml")
    dest_path = os.path.join(settings.CONFIG_DIR, f"games/{new_config_id}.yml")
    copyfile(src_path, dest_path)
    return new_config_id


class LutrisConfig:
    """Class where all the configuration handling happens.

    Description
    ===========
    Lutris' configuration uses a cascading mechanism where
    each higher, more specific level overrides the lower ones

    The levels are (highest to lowest): `game`, `runner` and `system`.
    Each level has its own set of options (config section), available to and
    overridden by upper levels:
    ```
     level | Config sections
    -------|----------------------
      game | system, runner, game
    runner | system, runner
    system | system
    ```
    Example: if requesting runner options at game level, their returned value
    will be from the game level config if it's set at this level; if not it
    will be the value from runner level if available; and if not, the default
    value set in the runner's module, or None.

    The config levels are stored in separate YAML format text files.

    Usage
    =====
    The config level will be auto set depending on what you pass to __init__:
    - For game level, pass game_config_id and optionally runner_slug (better perfs)
    - For runner level, pass runner_slug
    - For system level, pass nothing
    If need be, you can pass the level manually.

    To read, use the config sections dicts: game_config, runner_config and
    system_config.

    To write, modify the relevant `raw_*_config` section dict, then run
    `save()`.

    """

    def __init__(
        self,
        runner_slug: str = None,
        game_config_id: str = None,
        level: ConfigLevel = None
    ):
        self.game_config_id = game_config_id
        self.runner_slug = runner_slug
        self.level = level or (
            ConfigLevel.GAME if game_config_id
            else ConfigLevel.RUNNER if runner_slug
            else ConfigLevel.SYSTEM
        )

        self.game_level = {}
        self.runner_level = {}
        self.system_level = {}

        # Cascaded config sections (for reading)
        self.game_config = {}
        self.runner_config = {}
        self.system_config = {}

        # Raw (non-cascaded) sections (for writing)
        self.raw_game_config = {}
        self.raw_runner_config = {}
        self.raw_system_config = {}

        self.raw_config = {}

        self.initialize_config()

    def __repr__(self):
        return (
            f"LutrisConfig(level={self.level}, "
            f"game_config_id={self.game_config_id}, "
            f"runner={self.runner_slug})"
        )

    @property
    def system_config_path(self):
        return os.path.join(settings.CONFIG_DIR, "system.yml")

    @property
    def runner_config_path(self):
        if not self.runner_slug:
            return None
        return os.path.join(settings.RUNNERS_CONFIG_DIR, f"{self.runner_slug}.yml")

    @property
    def game_config_path(self):
        if not self.game_config_id:
            return None
        return os.path.join(settings.CONFIG_DIR, f"games/{self.game_config_id}.yml")

    def get_config(self, config_type: ConfigLevel):
        """Retrieve configuration based on type (game, runner, system)."""
        if config_type == ConfigLevel.GAME:
            path = self.game_config_path
        elif config_type == ConfigLevel.RUNNER:
            path = self.runner_config_path
        elif config_type == ConfigLevel.SYSTEM:
            path = self.system_config_path
        else:
            raise ValueError("Invalid config type specified.")

        # Load configuration from file
        config_data = read_yaml_from_file(path)
        return config_data

    def initialize_config(self):
        """Init and load config files"""
        config_levels = {
            ConfigLevel.GAME: self.game_level,
            ConfigLevel.RUNNER: self.runner_level,
            ConfigLevel.SYSTEM: self.system_level,
        }

        for config_type, config_dict in config_levels.items():
            config_dict.update(self.get_config(config_type))

        self.update_cascaded_config()
        self.update_raw_config()

    def update_cascaded_config(self):
        if self.system_level.get(ConfigLevel.SYSTEM.value) is None:
            self.system_level[ConfigLevel.SYSTEM.value] = {}
        self.system_config.clear()
        self.system_config.update(self.get_defaults(ConfigLevel.SYSTEM))
        self.system_config.update(self.system_level.get(ConfigLevel.SYSTEM.value))

        if self.level in [ConfigLevel.RUNNER, ConfigLevel.GAME] and self.runner_slug:
            if self.runner_level.get(self.runner_slug) is None:
                self.runner_level[self.runner_slug] = {}
            if self.runner_level.get(ConfigLevel.SYSTEM.value) is None:
                self.runner_level[ConfigLevel.SYSTEM.value] = {}
            self.runner_config.clear()
            self.runner_config.update(self.get_defaults(ConfigLevel.RUNNER))
            self.runner_config.update(self.runner_level.get(self.runner_slug))
            self.merge_to_system_config(self.runner_level.get(ConfigLevel.SYSTEM.value))

        if self.level == ConfigLevel.GAME and self.runner_slug:
            if self.game_level.get(ConfigLevel.GAME.value) is None:
                self.game_level[ConfigLevel.GAME.value] = {}
            if self.game_level.get(self.runner_slug) is None:
                self.game_level[self.runner_slug] = {}
            if self.game_level.get(ConfigLevel.SYSTEM.value) is None:
                self.game_level[ConfigLevel.SYSTEM.value] = {}
            self.game_config.clear()
            self.game_config.update(self.get_defaults(ConfigLevel.GAME))
            self.game_config.update(self.game_level.get(ConfigLevel.GAME.value))
            self.runner_config.update(self.game_level.get(self.runner_slug))
            self.merge_to_system_config(self.game_level.get(ConfigLevel.SYSTEM.value))

    def merge_env(self, new_env):
        """Merge environment variables from a new configuration into the system configuration."""
        if not new_env:
            return

        existing_env = self.system_config.get("env", {})
        # Merge environment variables
        existing_env.update(new_env)
        # Update system config
        self.system_config["env"] = existing_env

    def merge_to_system_config(self, config):
        """Merge a configuration to the system configuration"""
        if not config:
            return

        if "env" in config:
            self.merge_env(config["env"])
        # Merge the remaining configuration
        self.system_config.update(config)

    def update_raw_config(self):
        # Select the right level of config
        if self.level == ConfigLevel.GAME:
            raw_config = self.game_level
        elif self.level == ConfigLevel.RUNNER:
            raw_config = self.runner_level
        else:
            raw_config = self.system_level

        # Load config sections
        self.raw_system_config = raw_config[ConfigLevel.SYSTEM.value]
        if self.level in [ConfigLevel.RUNNER, ConfigLevel.GAME]:
            self.raw_runner_config = raw_config[self.runner_slug]
        if self.level == ConfigLevel.GAME:
            self.raw_game_config = raw_config[ConfigLevel.GAME.value]

        self.raw_config = raw_config

    def remove(self):
        """Delete the configuration file from disk."""
        if not path_exists(self.game_config_path):
            logger.debug("No config file at %s", self.game_config_path)
            return
        os.remove(self.game_config_path)
        logger.debug("Removed config %s", self.game_config_path)

    def save(self):
        """Save configuration file according to its type"""
        if self.level == ConfigLevel.SYSTEM:
            config = self.system_level
            config_path = self.system_config_path
        elif self.level == ConfigLevel.RUNNER:
            config = self.runner_level
            config_path = self.runner_config_path
        elif self.level == ConfigLevel.GAME:
            config = self.game_level
            config_path = self.game_config_path
        else:
            raise ValueError(f"Invalid config level '{self.level}'")

        # Check if the configuration path is valid
        if config_path is None:
            logger.warning("Cannot save config: config_path is None for level '%s'", self.level)
            return

        # Remove keys with no values from config before saving
        config = {key: value for key, value in config.items() if value}
        logger.debug("Saving %s config to %s", self, config_path)
        write_yaml_to_file(config, config_path)
        self.initialize_config()

    def get_defaults(self, options_type):
        """Return a dict of options' default value."""
        options_dict = self.options_as_dict(options_type)
        defaults = {}
        for option, params in options_dict.items():
            if "default" in params:
                default = params["default"]
                if callable(default):
                    try:
                        default = default()
                    except Exception as ex:
                        logger.exception("Unable to generate a default for '%s': %s", option, ex)
                        continue
                defaults[option] = default
        return defaults

    def options_as_dict(self, options_type: ConfigLevel) -> dict:
        """Convert the option list to a dict with option name as keys"""
        if options_type == ConfigLevel.SYSTEM:
            options = (
                sysoptions.with_runner_overrides(self.runner_slug)
                if self.runner_slug
                else sysoptions.system_options
            )
        else:
            if not self.runner_slug:
                return {}
            # Convert options_type to string before concatenating
            attribute_name = f"{options_type.name.lower()}_options"

            try:
                runner = import_runner(self.runner_slug)
            except InvalidRunnerError:
                options = {}
            else:
                if not getattr(runner, attribute_name):
                    runner = runner()

                options = getattr(runner, attribute_name)
        return dict((opt["option"], opt) for opt in options)
