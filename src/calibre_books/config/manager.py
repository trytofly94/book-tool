"""
Configuration management for Calibre Books CLI.

This module provides functionality for loading, validating, and managing
configuration files and profiles.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml

from ..utils.logging import LoggerMixin
from .schema import ConfigurationSchema


class ConfigManager(LoggerMixin):
    """
    Configuration manager for Calibre Books CLI.
    
    Handles loading, saving, and validating configuration files,
    as well as managing configuration profiles.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Custom path to configuration file
        """
        super().__init__()
        
        if config_path:
            self.config_path = Path(config_path).resolve()
        else:
            self.config_path = self.get_default_config_path()
        
        self.config_dir = self.config_path.parent
        self._config_data: Optional[Dict[str, Any]] = None
        
        self.logger.info(f"Initialized configuration manager with path: {self.config_path}")
    
    @staticmethod
    def get_default_config_path() -> Path:
        """Get the default configuration file path."""
        config_dir = Path.home() / '.book-tool'
        return config_dir / 'config.yml'
    
    def get_config_path(self) -> Path:
        """Get the current configuration file path."""
        return self.config_path
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get configuration data, loading from file if needed.
        
        Returns:
            Configuration dictionary
        """
        if self._config_data is None:
            self._config_data = self.load_config()
        
        return self._config_data
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yml', '.yaml']:
                    config_data = yaml.safe_load(f)
                elif self.config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {self.config_path.suffix}")
            
            # Validate configuration
            validated_config = ConfigurationSchema.validate_config(config_data)
            
            self.logger.info("Configuration loaded successfully")
            return validated_config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise ValueError(f"Invalid configuration file: {e}")
    
    def save_config(self, config_data: Dict[str, Any]) -> None:
        """
        Save configuration to file.
        
        Args:
            config_data: Configuration dictionary to save
        """
        # Validate before saving
        validated_config = ConfigurationSchema.validate_config(config_data)
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    validated_config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                )
            
            # Update cached config
            self._config_data = validated_config
            
            self.logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
    
    def create_config(self, config_data: Dict[str, Any], minimal: bool = False) -> None:
        """
        Create new configuration file.
        
        Args:
            config_data: Configuration data to save
            minimal: Whether to create minimal configuration
        """
        if minimal:
            config_data = ConfigurationSchema.get_minimal_config()
        
        self.save_config(config_data)
    
    def get_download_config(self) -> Dict[str, Any]:
        """Get download-specific configuration."""
        config = self.get_config()
        return config.get('download', {})
    
    def get_calibre_config(self) -> Dict[str, Any]:
        """Get Calibre-specific configuration."""
        config = self.get_config()
        return config.get('calibre', {})
    
    def get_asin_config(self) -> Dict[str, Any]:
        """Get ASIN lookup configuration."""
        config = self.get_config()
        return config.get('asin_lookup', {})
    
    def get_conversion_config(self) -> Dict[str, Any]:
        """Get conversion-specific configuration."""
        config = self.get_config()
        return config.get('conversion', {})
    
    def to_yaml(self, config_data: Dict[str, Any]) -> str:
        """Convert configuration to YAML string."""
        return yaml.dump(config_data, default_flow_style=False, sort_keys=False, indent=2)
    
    def to_json(self, config_data: Dict[str, Any]) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(config_data, indent=2, sort_keys=False)
    
    def check_dependencies(self) -> List[Any]:
        """Check availability of external dependencies."""
        from dataclasses import dataclass
        
        @dataclass
        class DependencyCheck:
            name: str
            available: bool
            status: str
            install_hint: Optional[str] = None
        
        checks = [
            DependencyCheck(
                name="Calibre CLI",
                available=True,  # TODO: Implement actual check
                status="Available",
                install_hint="Install Calibre from https://calibre-ebook.com/"
            ),
            DependencyCheck(
                name="librarian CLI",
                available=False,  # TODO: Implement actual check
                status="Not found",
                install_hint="Install librarian CLI tool"
            ),
            DependencyCheck(
                name="Chrome browser",
                available=True,  # TODO: Implement actual check
                status="Available"
            ),
        ]
        
        return checks
    
    def check_paths(self) -> List[Any]:
        """Check configured paths."""
        from dataclasses import dataclass
        
        @dataclass
        class PathCheck:
            name: str
            path: Path
            exists: bool
        
        config = self.get_config()
        checks = []
        
        # Check various configured paths
        if 'download' in config and 'download_path' in config['download']:
            path = Path(config['download']['download_path']).expanduser()
            checks.append(PathCheck("Download directory", path, path.exists()))
        
        if 'calibre' in config and 'library_path' in config['calibre']:
            path = Path(config['calibre']['library_path']).expanduser()
            checks.append(PathCheck("Calibre library", path, path.exists()))
        
        return checks
    
    def create_profile(self, name: str, from_current: bool = False) -> None:
        """Create a new configuration profile."""
        profiles_dir = self.config_dir / 'profiles'
        profiles_dir.mkdir(exist_ok=True)
        
        profile_path = profiles_dir / f'{name}.yml'
        
        if from_current:
            config_data = self.get_config()
        else:
            config_data = ConfigurationSchema.get_default_config()
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        self.logger.info(f"Created profile '{name}' at {profile_path}")
    
    def use_profile(self, name: str) -> None:
        """Switch to a different configuration profile."""
        profiles_dir = self.config_dir / 'profiles'
        profile_path = profiles_dir / f'{name}.yml'
        
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")
        
        # Copy profile to main config
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_config = yaml.safe_load(f)
        
        self.save_config(profile_config)
        
        self.logger.info(f"Switched to profile '{name}'")
    
    def list_profiles(self) -> List[Any]:
        """List all available configuration profiles."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class Profile:
            name: str
            created: datetime
        
        profiles_dir = self.config_dir / 'profiles'
        if not profiles_dir.exists():
            return []
        
        profiles = []
        for profile_file in profiles_dir.glob('*.yml'):
            stat = profile_file.stat()
            profiles.append(Profile(
                name=profile_file.stem,
                created=datetime.fromtimestamp(stat.st_ctime)
            ))
        
        return sorted(profiles, key=lambda p: p.name)
    
    def get_current_profile(self) -> str:
        """Get the name of the currently active profile."""
        # TODO: Implement profile tracking
        return "default"