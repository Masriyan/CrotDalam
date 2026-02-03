#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Configuration Management
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Config:
    """Application configuration."""
    
    # General
    app_name: str = "CROT DALAM"
    version: str = "2.0.0"
    debug: bool = False
    
    # Browser defaults
    headless: bool = True
    locale: str = "en-US"
    default_limit: int = 60
    default_mode: str = "quick"
    
    # Anti-detection
    antidetect_enabled: bool = True
    antidetect_aggressive: bool = False
    min_delay: float = 0.5
    max_delay: float = 3.0
    
    # Proxy
    proxy_list: List[str] = field(default_factory=list)
    proxy_rotation: bool = False
    
    # Output
    output_directory: str = "out"
    screenshot_enabled: bool = False
    download_enabled: bool = False
    archive_enabled: bool = False
    
    # GUI
    gui_host: str = "127.0.0.1"
    gui_port: int = 5000
    gui_secret_key: str = "crot-dalam-secret-key-change-in-production"
    
    # Alerts
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    
    # Paths
    session_directory: str = "sessions"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def save(self, path: Path) -> None:
        """Save configuration to file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load configuration from file."""
        if not path.exists():
            return cls()
        
        with open(path, "r") as f:
            data = json.load(f)
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()
        
        # Map env vars to config fields
        env_mapping = {
            "CROT_DEBUG": ("debug", lambda x: x.lower() == "true"),
            "CROT_HEADLESS": ("headless", lambda x: x.lower() == "true"),
            "CROT_LOCALE": ("locale", str),
            "CROT_LIMIT": ("default_limit", int),
            "CROT_MODE": ("default_mode", str),
            "CROT_ANTIDETECT": ("antidetect_enabled", lambda x: x.lower() == "true"),
            "CROT_PROXY_LIST": ("proxy_list", lambda x: x.split(",")),
            "CROT_OUTPUT_DIR": ("output_directory", str),
            "CROT_GUI_HOST": ("gui_host", str),
            "CROT_GUI_PORT": ("gui_port", int),
            "CROT_SECRET_KEY": ("gui_secret_key", str),
            "CROT_TELEGRAM_TOKEN": ("telegram_bot_token", str),
            "CROT_TELEGRAM_CHAT": ("telegram_chat_id", str),
            "CROT_DISCORD_WEBHOOK": ("discord_webhook_url", str),
        }
        
        for env_var, (field_name, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value:
                try:
                    setattr(config, field_name, converter(value))
                except Exception:
                    pass
        
        return config


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file or environment."""
    # Default config path
    if config_path is None:
        config_path = Path.home() / ".config" / "crot_dalam" / "config.json"
    
    # Try loading from file first
    if config_path.exists():
        config = Config.load(config_path)
    else:
        config = Config()
    
    # Override with environment variables
    env_config = Config.from_env()
    for field_name in Config.__dataclass_fields__:
        env_value = getattr(env_config, field_name)
        default_value = getattr(Config(), field_name)
        
        # Only override if env value differs from default
        if env_value != default_value:
            setattr(config, field_name, env_value)
    
    return config


def get_default_config() -> Config:
    """Get default configuration."""
    return Config()
