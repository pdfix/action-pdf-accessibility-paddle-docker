import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

import constants
from constants import DOCKER_IMAGE, DOCKER_NAMESPACE, DOCKER_REPOSITORY
from logger import get_logger

logger: logging.Logger = get_logger("app_logger")


class DockerImageContainerUpdateChecker:
    """
    A class to check if there is a new Docker image version available.
    """

    # Constants
    LAST_CHECK_FILE: str = ".local_data.json"

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
                    logger.info(
                        f"🚀 A new Docker image version ({latest_version}) is available! "
                        f"Update with: `docker pull {DOCKER_IMAGE}:{latest_version}`"
                    )

                self._update_last_check()
        except Exception:
            # do not propagate any exceptions up
            pass

    def _get_current_version(self) -> str:
        """
        Read the current version from config.json, or from constants.py in images without config.json (veraPDF).
        Both are set by update_version.sh at release.

        Returns:
            The current version of the Docker image.
        """
        version: Optional[str] = getattr(constants, "VERSION", None)
        if version:
            return version
        config_file: str = getattr(constants, "CONFIG_FILE", "config.json")
        config_path: Path = Path(__file__).parent.parent.joinpath(config_file).resolve()
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config: Any = json.load(file)
                return config.get("version", "unknown")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading {config_file}: {e}")
            return "unknown"

    def _get_latest_docker_version(self) -> Optional[str]:
        """
        Fetch the latest available version from Docker Hub.

        Returns:
            The latest version of the Docker image, or None if an error occurs.
        """
        # Most-recently-updated tags first; skip floating "latest" in favor of a concrete version tag.
        url: str = (
            f"https://hub.docker.com/v2/"
            f"namespaces/{DOCKER_NAMESPACE}/"
            f"repositories/{DOCKER_REPOSITORY}/"
            f"tags?page_size=50&ordering=last_updated"
        )
        try:
            response: requests.Response = requests.get(url)
            response.raise_for_status()
            data: Any = response.json()
            if isinstance(data, dict) and "results" in data:
                results: Any = data["results"]
                if isinstance(results, list):
                    for item in results:
                        if isinstance(item, dict) and "name" in item:
                            name: str = str(item["name"])
                            if name != "latest":
                                return name
        except requests.RequestException as e:
            logger.error(f"Error checking for updates: {e}")
        return None

    def _last_check_today(self) -> bool:
        """
        Check if the last update check was today by reading last_check.json.

        Returns:
            True if the last check was today, False otherwise.
        """
        if os.path.exists(self.LAST_CHECK_FILE):
            try:
                with open(self.LAST_CHECK_FILE, "r", encoding="utf-8") as file:
                    data: Any = json.load(file)
                    last_date: str = data.get("last_check", "")
                    return last_date == datetime.now().strftime("%Y-%m-%d")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Error reading {self.LAST_CHECK_FILE}: {e}")
        return False

    def _update_last_check(self) -> None:
        """
        Store today's date in last_check.json.
        """
        try:
            with open(self.LAST_CHECK_FILE, "w", encoding="utf-8") as file:
                json.dump({"last_check": datetime.now().strftime("%Y-%m-%d")}, file)
        except Exception as e:
            logger.error(f"Error writing {self.LAST_CHECK_FILE}: {e}")
