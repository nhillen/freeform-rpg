"""
Configuration management for Freeform RPG.

Handles API key storage and retrieval with interactive login flow.
"""

import json
import os
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    # Use XDG_CONFIG_HOME if set, otherwise ~/.config
    config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    config_dir = Path(config_home) / "freeform-rpg"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "config.json"


def load_config() -> dict:
    """Load configuration from disk."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save configuration to disk."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    # Secure the file (owner read/write only)
    os.chmod(config_path, 0o600)


def get_api_key() -> Optional[str]:
    """
    Get the Anthropic API key from config or environment.

    Priority:
    1. ANTHROPIC_API_KEY environment variable
    2. Stored config file
    """
    # Check environment first
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key

    # Check config file
    config = load_config()
    return config.get("anthropic_api_key")


def set_api_key(api_key: str) -> None:
    """Store the API key in config."""
    config = load_config()
    config["anthropic_api_key"] = api_key
    save_config(config)


def clear_api_key() -> None:
    """Remove the stored API key."""
    config = load_config()
    config.pop("anthropic_api_key", None)
    save_config(config)


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validate an API key by making a test call.

    Returns:
        (is_valid, message)
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Make a minimal API call to validate
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True, "API key validated successfully"
    except anthropic.AuthenticationError:
        return False, "Invalid API key"
    except anthropic.RateLimitError:
        # Key is valid but rate limited - still counts as valid
        return True, "API key valid (rate limited)"
    except Exception as e:
        return False, f"Validation failed: {str(e)}"


def interactive_login() -> bool:
    """
    Interactive login flow for setting up API key.

    Returns:
        True if login successful, False otherwise
    """
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " Freeform RPG - Authentication Setup ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    print()

    # Check if already logged in
    existing_key = get_api_key()
    if existing_key:
        print(f"  You're already logged in.")
        print(f"  API key: {existing_key[:8]}...{existing_key[-4:]}")
        print()
        response = input("  Replace existing key? [y/N] ").strip().lower()
        if response != 'y':
            print("  Keeping existing key.")
            return True
        print()

    print("  To play, you need an Anthropic API key.")
    print("  Get one at: https://console.anthropic.com/settings/keys")
    print()

    # Get the key
    try:
        api_key = input("  Enter your API key: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.")
        return False

    if not api_key:
        print("  No key entered.")
        return False

    # Basic format check
    if not api_key.startswith("sk-ant-"):
        print()
        print("  Warning: Key doesn't look like an Anthropic key (should start with 'sk-ant-')")
        response = input("  Continue anyway? [y/N] ").strip().lower()
        if response != 'y':
            return False

    # Validate the key
    print()
    print("  Validating key...", end=" ", flush=True)

    is_valid, message = validate_api_key(api_key)

    if is_valid:
        print("✓")
        print(f"  {message}")
        print()

        # Save it
        set_api_key(api_key)
        config_path = get_config_path()
        print(f"  Key saved to: {config_path}")
        print()
        print("  You're all set! Run 'new-game' to start playing.")
        return True
    else:
        print("✗")
        print(f"  {message}")
        return False


def check_auth_or_prompt() -> Optional[str]:
    """
    Check for API key, prompting for login if not found.

    Returns:
        API key if available, None if user declined to login
    """
    api_key = get_api_key()

    if api_key:
        return api_key

    print()
    print("  No API key found.")
    print()
    response = input("  Would you like to set one up now? [Y/n] ").strip().lower()

    if response in ('', 'y', 'yes'):
        if interactive_login():
            return get_api_key()

    return None
