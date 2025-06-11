"""
OBS and VEX Tournament Manager synchronization logic.
"""

import logging
import time
import threading
from typing import Dict, Optional

from obsws_python import ReqClient as OBSClient, events
from vex_tm_bridge import get_bridge_engine
from vex_tm_bridge.base import Competition, FieldsetAudienceDisplay, FieldsetState

try:
    from .config import Config
except ImportError:
    # When running as PyInstaller executable, use absolute imports
    from vex_tm_obs_sync.config import Config

logger = logging.getLogger(__name__)


class OBSTMSync:
    """Main synchronization class for OBS and VEX Tournament Manager."""
    
    def __init__(self, config: Config):
        """Initialize the sync application."""
        self.config = config
        self.obs_client: Optional[OBSClient] = None
        self.bridge_engine = None
        self.fieldset = None
        self.running = False
        
        # Create mapping dictionaries for quick lookups
        self.field_scenes = [mapping.obs_scene for mapping in config.field_scene_mappings]
        self.obs_to_tm = {mapping.obs_scene: mapping.tm_display for mapping in config.other_scene_mappings}
        self.tm_to_obs = {mapping.tm_display: mapping.obs_scene for mapping in config.other_scene_mappings}
        
        # Keep track of last known states to avoid infinite loops
        self.last_obs_scene: Optional[str] = None
        self.last_tm_display: Optional[str] = None
        self._sync_lock = threading.Lock()
        
        logger.info("OBSTMSync initialized")
        logger.debug(f"Field scenes: {self.field_scenes}")
        logger.debug(f"OBS->TM mappings: {self.obs_to_tm}")
        logger.debug(f"TM->OBS mappings: {self.tm_to_obs}")
    
    def connect_obs(self) -> None:
        """Connect to OBS WebSocket."""
        try:
            logger.info(f"Connecting to OBS at {self.config.obs.host}:{self.config.obs.port}")
            self.obs_client = OBSClient(
                host=self.config.obs.host,
                port=self.config.obs.port,
                password=self.config.obs.password
            )
            
            # Test the connection
            version_info = self.obs_client.get_version()
            logger.info(f"Connected to OBS {version_info.obs_version} (WebSocket {version_info.obs_web_socket_version})")
            
            # Get current scene
            current_scene = self.obs_client.get_current_program_scene()
            self.last_obs_scene = current_scene.scene_name
            logger.info(f"Current OBS scene: {self.last_obs_scene}")
            
            # Register event handlers if sync is enabled
            if self.config.sync_obs_to_tm:
                self.obs_client.callback.register(self._on_obs_scene_changed)
                logger.info("Registered OBS scene change handler")
            
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            raise
    
    def connect_vex_tm(self) -> None:
        """Connect to VEX Tournament Manager."""
        try:
            logger.info(f"Connecting to VEX TM at {self.config.vex_tm.host}")
            self.bridge_engine = get_bridge_engine(self.config.vex_tm.competition, low_cpu_usage=True)
            self.bridge_engine.start()
            
            # Get fieldset
            logger.info(f"Getting fieldset: {self.config.vex_tm.fieldset_title}")
            self.fieldset = self.bridge_engine.get_fieldset(self.config.vex_tm.fieldset_title)
            
            # Get current display state
            overview = self.fieldset.get_overview()
            self.last_tm_display = overview.audience_display.name
            logger.info(f"Current TM audience display: {self.last_tm_display}")
            
            # Register event handlers if sync is enabled
            if self.config.sync_tm_to_obs:
                self.fieldset.overview_updated_event.on(self._on_tm_overview_updated)
                logger.info("Registered TM overview update handler")
            
        except Exception as e:
            logger.error(f"Failed to connect to VEX TM: {e}")
            raise
    
    def _on_obs_scene_changed(self, event_data) -> None:
        """Handle OBS scene change events."""
        if not self.config.sync_obs_to_tm:
            return
        
        # Extract scene name from event
        scene_name = None
        if hasattr(event_data, 'scene_name'):
            scene_name = event_data.scene_name
        elif isinstance(event_data, events.CurrentProgramSceneChanged):
            scene_name = event_data.scene_name
        
        if not scene_name:
            logger.warning(f"Could not extract scene name from OBS event: {event_data}")
            return
        
        logger.debug(f"OBS scene changed to: {scene_name}")
        
        with self._sync_lock:
            # Avoid infinite loops
            if scene_name == self.last_obs_scene:
                return
            
            self.last_obs_scene = scene_name
            
            # Check if this is a field scene
            if scene_name in self.field_scenes:
                # For field scenes, determine appropriate TM display based on match state
                try:
                    match_state = self.fieldset.get_match_state()
                    if match_state == FieldsetState.Disabled:
                        # No active match, set to Intro
                        tm_display_name = FieldsetAudienceDisplay.Intro.name
                    else:
                        # Match is running or paused, set to In-Match
                        tm_display_name = FieldsetAudienceDisplay.InMatch.name
                    
                    logger.info(f"Syncing field scene '{scene_name}' -> TM display '{tm_display_name}' (match state: {match_state})")
                    
                    # Convert name to FieldsetAudienceDisplay enum
                    tm_display = FieldsetAudienceDisplay.by_name(tm_display_name)
                    self.fieldset.set_audience_display(tm_display)
                    self.last_tm_display = tm_display_name
                    logger.info(f"Successfully updated TM audience display to: {tm_display_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to update TM audience display for field scene: {e}")
                    
            elif scene_name in self.obs_to_tm:
                # For other scenes, use direct mapping
                tm_display_name = self.obs_to_tm[scene_name]
                logger.info(f"Syncing OBS scene '{scene_name}' -> TM display '{tm_display_name}'")
                
                try:
                    tm_display = FieldsetAudienceDisplay.by_name(tm_display_name)
                    self.fieldset.set_audience_display(tm_display)
                    self.last_tm_display = tm_display_name
                    logger.info(f"Successfully updated TM audience display to: {tm_display_name}")
                except Exception as e:
                    logger.error(f"Failed to update TM audience display: {e}")
            else:
                logger.debug(f"No mapping found for OBS scene: {scene_name}")
    
    def _on_tm_overview_updated(self, overview) -> None:
        """Handle VEX TM overview update events."""
        if not self.config.sync_tm_to_obs:
            return
        
        audience_display_name = overview.audience_display.name
        logger.debug(f"TM audience display changed to: {audience_display_name}")
        
        with self._sync_lock:
            # Avoid infinite loops
            if audience_display_name == self.last_tm_display:
                return
            
            self.last_tm_display = audience_display_name
            
            # Check if this is Intro or In-Match display (field-related)
            if audience_display_name in [FieldsetAudienceDisplay.Intro.name, FieldsetAudienceDisplay.InMatch.name]:
                # For field-related displays, switch to the field scene based on current field ID
                try:
                    current_field_id = overview.current_field_id
                    if current_field_id is not None and 0 <= current_field_id < len(self.field_scenes):
                        obs_scene = self.field_scenes[current_field_id]
                        logger.info(f"Syncing TM display '{audience_display_name}' -> Field scene '{obs_scene}' (field {current_field_id})")
                        
                        try:
                            self.obs_client.set_current_program_scene(obs_scene)
                            self.last_obs_scene = obs_scene
                            logger.info(f"Successfully updated OBS scene to: {obs_scene}")
                        except Exception as e:
                            logger.error(f"Failed to update OBS scene: {e}")
                    else:
                        logger.warning(f"Invalid or missing field ID: {current_field_id}, cannot map to field scene")
                        
                except Exception as e:
                    logger.error(f"Failed to get current field ID: {e}")
                    
            elif audience_display_name in self.tm_to_obs:
                # For other displays, use direct mapping
                obs_scene = self.tm_to_obs[audience_display_name]
                logger.info(f"Syncing TM display '{audience_display_name}' -> OBS scene '{obs_scene}'")
                
                try:
                    self.obs_client.set_current_program_scene(obs_scene)
                    self.last_obs_scene = obs_scene
                    logger.info(f"Successfully updated OBS scene to: {obs_scene}")
                except Exception as e:
                    logger.error(f"Failed to update OBS scene: {e}")
            else:
                logger.debug(f"No mapping found for TM audience display: {audience_display_name}")
    
    def disconnect(self) -> None:
        """Disconnect from all services."""
        logger.info("Disconnecting from services...")
        
        if self.obs_client:
            try:
                self.obs_client.disconnect()
                logger.info("Disconnected from OBS")
            except Exception as e:
                logger.error(f"Error disconnecting from OBS: {e}")
            finally:
                self.obs_client = None
        
        if self.bridge_engine:
            try:
                # Note: VEX TM Bridge doesn't have an explicit disconnect method
                # The engine will be cleaned up when the object is destroyed
                logger.info("Disconnected from VEX TM")
            except Exception as e:
                logger.error(f"Error disconnecting from VEX TM: {e}")
            finally:
                self.bridge_engine = None
                self.fieldset = None
    
    def run(self) -> None:
        """Run the synchronization application."""
        logger.info("Starting VEX TM OBS Sync...")
        
        try:
            # Connect to services
            self.connect_obs()
            self.connect_vex_tm()
            
            self.running = True
            logger.info("Synchronization started. Press Ctrl+C to stop.")
            
            # Initial sync - sync current states
            if self.config.sync_obs_to_tm and self.last_obs_scene:
                # Handle field scenes
                if self.last_obs_scene in self.field_scenes:
                    try:
                        match_state = self.fieldset.get_match_state()
                        target_display = FieldsetAudienceDisplay.Intro.name if match_state == FieldsetState.Disabled else FieldsetAudienceDisplay.InMatch.name
                        if target_display != self.last_tm_display:
                            logger.info(f"Initial sync: Field scene '{self.last_obs_scene}' -> TM display '{target_display}'")
                            tm_display = FieldsetAudienceDisplay.by_name(target_display)
                            self.fieldset.set_audience_display(tm_display)
                            self.last_tm_display = target_display
                    except Exception as e:
                        logger.error(f"Failed initial TM sync for field scene: {e}")
                # Handle other scenes
                elif self.last_obs_scene in self.obs_to_tm:
                    tm_display_name = self.obs_to_tm[self.last_obs_scene]
                    if tm_display_name != self.last_tm_display:
                        logger.info(f"Initial sync: OBS scene '{self.last_obs_scene}' -> TM display '{tm_display_name}'")
                        try:
                            tm_display = FieldsetAudienceDisplay.by_name(tm_display_name)
                            self.fieldset.set_audience_display(tm_display)
                            self.last_tm_display = tm_display_name
                        except Exception as e:
                            logger.error(f"Failed initial TM sync: {e}")
            
            elif self.config.sync_tm_to_obs and self.last_tm_display:
                # Handle field-related displays
                if self.last_tm_display in [FieldsetAudienceDisplay.Intro.name, FieldsetAudienceDisplay.InMatch.name]:
                    try:
                        overview = self.fieldset.get_overview()
                        current_field_id = overview.current_field_id
                        if current_field_id is not None and 0 <= current_field_id < len(self.field_scenes):
                            obs_scene = self.field_scenes[current_field_id]
                            if obs_scene != self.last_obs_scene:
                                logger.info(f"Initial sync: TM display '{self.last_tm_display}' -> Field scene '{obs_scene}' (field {current_field_id})")
                                self.obs_client.set_current_program_scene(obs_scene)
                                self.last_obs_scene = obs_scene
                    except Exception as e:
                        logger.error(f"Failed initial OBS sync for field display: {e}")
                # Handle other displays
                elif self.last_tm_display in self.tm_to_obs:
                    obs_scene = self.tm_to_obs[self.last_tm_display]
                    if obs_scene != self.last_obs_scene:
                        logger.info(f"Initial sync: TM display '{self.last_tm_display}' -> OBS scene '{obs_scene}'")
                        try:
                            self.obs_client.set_current_program_scene(obs_scene)
                            self.last_obs_scene = obs_scene
                        except Exception as e:
                            logger.error(f"Failed initial OBS sync: {e}")
            
            # Keep running until interrupted
            while self.running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            self.running = False
            self.disconnect()
            logger.info("Application shutdown complete") 