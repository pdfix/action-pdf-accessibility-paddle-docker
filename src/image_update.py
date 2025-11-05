import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

from constants import CONFIG_FILE, DOCKER_IMAGE


class DockerImageContainerUpdateChecker:
    """
    A class to check if there is a new Docker image version available.
    """

    # Constants
    LAST_CHECK_FILE = ".local_data.json"

    def check_for_image_updates(self) -> None:
        """
        Checks once a day if a new Docker image version is available.
        If a new version is found, it prints a message with the update command.
        """
        try:
            if not self._last_check_today():
                current_version: str = self._get_current_version()
                latest_version: Optional[str] = self._get_latest_docker_version()

                if latest_version and latest_version != current_version:
                    print(
                        f"🚀 A new Docker image version ({latest_version}) is available! "
                        f"Update with: `docker pull {DOCKER_IMAGE}:{latest_version}`"
                    )

                self._update_last_check()
        except Exception:
            # do not propagate any exceptions up
            pass

    def _get_current_version(self) -> str:
        """
        Read the current version from config.json.

        Returns:
            The current version of the Docker image.
        """
        config_path: Path = Path(__file__).parent.parent.joinpath(CONFIG_FILE).resolve()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config: Any = json.load(f)
                return config.get("version", "unknown")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading {CONFIG_FILE}: {e}", file=sys.stderr)
            return "unknown"

    def _get_latest_docker_version(self) -> Optional[str]:
        """
        Fetch the latest available version from Docker Hub.

        Returns:
            The latest version of the Docker image, or None if an error occurs.
        """
        url: str = f"https://hub.docker.com/v2/repositories/{DOCKER_IMAGE}/tags?page_size=1"
        try:
            response: requests.Response = requests.get(url)
            response.raise_for_status()
            tags: list = response.json().get("results", [])
            if tags:
                # Latest tag
                return tags[0]["name"]
        except requests.RequestException as e:
            print(f"Error checking for updates: {e}", file=sys.stderr)
        return None

    def _last_check_today(self) -> bool:
        """
        Check if the last update check was today by reading last_check.json.

        Returns:
            True if the last check was today, False otherwise.
        """
        if os.path.exists(self.LAST_CHECK_FILE):
            try:
                with open(self.LAST_CHECK_FILE, "r", encoding="utf-8") as f:
                    data: Any = json.load(f)
                    last_date: str = data.get("last_check", "")
                    return last_date == datetime.now().strftime("%Y-%m-%d")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading {self.LAST_CHECK_FILE}: {e}", file=sys.stderr)
        return False

    def _update_last_check(self) -> None:
        """
        Store today's date in last_check.json.
        """
        try:
            with open(self.LAST_CHECK_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_check": datetime.now().strftime("%Y-%m-%d")}, f)
        except Exception as e:
            print(f"Error writing {self.LAST_CHECK_FILE}: {e}", file=sys.stderr)
