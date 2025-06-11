"""
Configuration management for VEX Tournament Manager OBS Sync.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml
from vex_tm_bridge.base import Competition

logger = logging.getLogger(__name__)


@dataclass
class OBSConfig:
    """OBS WebSocket configuration."""

    host: str = "localhost"
    port: int = 4455
    password: Optional[str] = None


@dataclass
class VEXTMConfig:
    """VEX Tournament Manager configuration."""

    host: str = "localhost"
    competition: Competition = Competition.V5RC
    fieldset_title: str = "Match Field Set #1"


@dataclass
class FieldSceneMapping:
    """Mapping for field-specific OBS scenes."""

    obs_scene: str


@dataclass
class OtherSceneMapping:
    """Mapping between OBS scene and TM audience display for non-field scenes."""

    obs_scene: str
    tm_display: str


@dataclass
class Config:
    """Main configuration class."""

    obs: OBSConfig
    vex_tm: VEXTMConfig
    field_scene_mappings: List[FieldSceneMapping]
    other_scene_mappings: List[OtherSceneMapping]
    sync_tm_to_obs: bool = True
    sync_obs_to_tm: bool = True


def load_config(config_path: Path) -> Config:
    """Load configuration from YAML file."""
    logger.debug(f"Loading configuration from: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError("Configuration file is empty")

    # Parse OBS configuration
    obs_data = data.get("obs", {})
    obs_config = OBSConfig(
        host=obs_data.get("host", "localhost"),
        port=obs_data.get("port", 4455),
        password=obs_data.get("password"),
    )

    # Parse VEX TM configuration
    vex_tm_data = data.get("vex_tm", {})
    competition_str = vex_tm_data.get("competition", "V5RC")
    try:
        competition = Competition[competition_str]
    except KeyError:
        raise ValueError(
            f"Invalid competition type: {competition_str}. Must be one of: {list(Competition.__members__.keys())}"
        )

    vex_tm_config = VEXTMConfig(
        host=vex_tm_data.get("host", "localhost"),
        competition=competition,
        fieldset_title=vex_tm_data.get("fieldset_title", "Match Field Set #1"),
    )

    # Parse field scene mappings
    field_mappings_data = data.get("field_scene_mappings", [])
    field_scene_mappings: List[FieldSceneMapping] = []
    for mapping in field_mappings_data:
        if not isinstance(mapping, dict):
            raise ValueError(f"Invalid field scene mapping format: {mapping}")

        obs_scene = mapping.get("obs_scene")
        if not obs_scene:
            raise ValueError(f"Field scene mapping must have 'obs_scene': {mapping}")

        field_scene_mappings.append(FieldSceneMapping(obs_scene=obs_scene))

    # Parse other scene mappings
    other_mappings_data = data.get("other_scene_mappings", [])
    other_scene_mappings: List[OtherSceneMapping] = []
    for mapping in other_mappings_data:
        if not isinstance(mapping, dict):
            raise ValueError(f"Invalid other scene mapping format: {mapping}")

        obs_scene = mapping.get("obs_scene")
        tm_display = mapping.get("tm_display")

        if not obs_scene or not tm_display:
            raise ValueError(
                f"Other scene mapping must have both 'obs_scene' and 'tm_display': {mapping}"
            )

        other_scene_mappings.append(
            OtherSceneMapping(obs_scene=obs_scene, tm_display=tm_display)
        )

    # Parse sync options
    sync_tm_to_obs = data.get("sync_tm_to_obs", True)
    sync_obs_to_tm = data.get("sync_obs_to_tm", True)

    return Config(
        obs=obs_config,
        vex_tm=vex_tm_config,
        field_scene_mappings=field_scene_mappings,
        other_scene_mappings=other_scene_mappings,
        sync_tm_to_obs=sync_tm_to_obs,
        sync_obs_to_tm=sync_obs_to_tm,
    )


def validate_config(config: Config) -> None:
    """Validate the configuration."""
    logger.debug("Validating configuration")

    # Validate required fields
    if not config.field_scene_mappings and not config.other_scene_mappings:
        raise ValueError(
            "At least one scene mapping (field or other) must be configured"
        )

    # Validate OBS configuration
    if not config.obs.host:
        raise ValueError("OBS host must be specified")

    if not (1 <= config.obs.port <= 65535):
        raise ValueError("OBS port must be between 1 and 65535")

    # Validate VEX TM configuration
    if not config.vex_tm.host:
        raise ValueError("VEX TM host must be specified")

    if not config.vex_tm.fieldset_title:
        raise ValueError("VEX TM fieldset title must be specified")

    # Validate field scene mappings
    field_obs_scenes = set()
    for mapping in config.field_scene_mappings:
        if not mapping.obs_scene.strip():
            raise ValueError("Field OBS scene name cannot be empty")

        if mapping.obs_scene in field_obs_scenes:
            raise ValueError(
                f"Duplicate field OBS scene in mappings: {mapping.obs_scene}"
            )

        field_obs_scenes.add(mapping.obs_scene)

    # Validate other scene mappings
    other_obs_scenes = set()
    tm_displays = set()

    for mapping in config.other_scene_mappings:
        if not mapping.obs_scene.strip():
            raise ValueError("Other OBS scene name cannot be empty")

        if not mapping.tm_display.strip():
            raise ValueError("TM display name cannot be empty")

        if mapping.obs_scene in other_obs_scenes:
            raise ValueError(
                f"Duplicate other OBS scene in mappings: {mapping.obs_scene}"
            )

        if mapping.tm_display in tm_displays:
            raise ValueError(f"Duplicate TM display in mappings: {mapping.tm_display}")

        other_obs_scenes.add(mapping.obs_scene)
        tm_displays.add(mapping.tm_display)

    # Validate no overlap between field and other scene names
    overlap = field_obs_scenes.intersection(other_obs_scenes)
    if overlap:
        raise ValueError(
            f"OBS scenes cannot be in both field and other mappings: {overlap}"
        )

    # Validate TM display names are valid
    from vex_tm_bridge.base import FieldsetAudienceDisplay

    valid_displays = {display.name for display in FieldsetAudienceDisplay}
    for mapping in config.other_scene_mappings:
        if mapping.tm_display not in valid_displays:
            raise ValueError(
                f"Invalid TM display '{mapping.tm_display}'. Valid options: {sorted(valid_displays)}"
            )

    # Validate sync options
    if not config.sync_tm_to_obs and not config.sync_obs_to_tm:
        raise ValueError("At least one sync direction must be enabled")

    logger.debug("Configuration validation successful")
