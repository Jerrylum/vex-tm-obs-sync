#!/usr/bin/env python3
"""
VEX Tournament Manager OBS Sync
Main application entry point for synchronizing OBS scenes with VEX Tournament Manager audience display.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from obsws_python import ReqClient as OBSClient, events
from vex_tm_bridge import get_bridge_engine
from vex_tm_bridge.base import Competition

try:
    from .config import Config, load_config, validate_config
    from .sync import OBSTMSync
except ImportError:
    # When running as PyInstaller executable, use absolute imports
    from vex_tm_obs_sync.config import Config, load_config, validate_config
    from vex_tm_obs_sync.sync import OBSTMSync


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def find_settings_file(custom_path: Optional[str] = None) -> Path:
    """Find the settings file to use."""
    if custom_path:
        settings_path = Path(custom_path)
        if not settings_path.exists():
            raise FileNotFoundError(f"Custom settings file not found: {custom_path}")
        return settings_path
    
    # For executable, look in the same directory as the executable
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        exe_dir = Path(sys.executable).parent
        settings_path = exe_dir / "settings.yml"
    else:
        # Running as Python script, look in current working directory
        settings_path = Path.cwd() / "settings.yml"
    
    if not settings_path.exists():
        raise FileNotFoundError(
            f"Settings file not found: {settings_path}\n"
            f"Please create a settings.yml file in the same directory as the executable "
            f"or specify a custom path using --config"
        )
    
    return settings_path


def main() -> None:
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="VEX Tournament Manager OBS Sync - Synchronize OBS scenes with VEX TM audience display"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to the configuration file (default: settings.yml in current directory)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Find and load configuration
        settings_path = find_settings_file(args.config)
        logger.info(f"Loading configuration from: {settings_path}")
        
        config = load_config(settings_path)
        validate_config(config)
        
        logger.info("Configuration loaded successfully")
        logger.info(f"OBS WebSocket: {config.obs.host}:{config.obs.port}")
        logger.info(f"VEX TM Bridge: {config.vex_tm.host}")
        logger.info(f"Competition: {config.vex_tm.competition}")
        logger.info(f"Fieldset: {config.vex_tm.fieldset_title}")
        logger.info(f"Field scenes: {len(config.field_scene_mappings)} configured")
        logger.info(f"Other scenes: {len(config.other_scene_mappings)} configured")
        
        # Initialize and run the sync application
        sync_app = OBSTMSync(config)
        sync_app.run()
        
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=args.debug)
        sys.exit(1)


if __name__ == "__main__":
    main() 