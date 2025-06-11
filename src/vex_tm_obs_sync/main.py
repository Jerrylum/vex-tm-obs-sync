#!/usr/bin/env python3
"""
VEX Tournament Manager OBS Sync
Main application entry point for synchronizing OBS scenes with VEX Tournament Manager audience display.
"""

import logging
import sys
from pathlib import Path

import click

# Import modules with error handling for PyInstaller
try:
    from .config import load_config
    from .sync import OBSTMSync
except ImportError:
    # When running as PyInstaller executable, use absolute imports
    from vex_tm_obs_sync.config import load_config
    from vex_tm_obs_sync.sync import OBSTMSync


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Set specific log levels for external libraries
    logging.getLogger("obsws_python").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)

    if debug:
        logging.getLogger("vex_tm_obs_sync").setLevel(logging.DEBUG)


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="settings.yml",
    help="Path to configuration file",
)
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
def main(config: Path, debug: bool) -> None:
    """VEX Tournament Manager OBS Sync Application."""
    try:
        # Set up logging
        setup_logging(debug)
        logger = logging.getLogger(__name__)

        logger.info("Starting VEX Tournament Manager OBS Sync")

        # Load configuration
        logger.info(f"Loading configuration from: {config}")
        app_config = load_config(config)

        # Create and run sync application
        sync_app = OBSTMSync(app_config)
        sync_app.run()

    except FileNotFoundError:
        click.echo(f"Error: Configuration file '{config}' not found.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
