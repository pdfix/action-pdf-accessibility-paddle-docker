import json
from pathlib import Path
from typing import Any, Optional


class ParamsParser:
    def __init__(self, params_json_path: str) -> None:
        """
        Initialize the ParamsParser.

        Args:
            params_json_path (str): Path to the params JSON file.
        """
        self.params_json_path: Path = Path(params_json_path)
        self.params: dict[str, Any] = {}

    def parse(self) -> None:
        """
        Parse the params JSON file.
        """
        with open(self.params_json_path, "r") as file:
            json_data: Any = json.load(file)

            if isinstance(json_data, list):
                for item in json_data:
                    if isinstance(item, dict):
                        self._parse_dictionary_item(item)
                    else:
                        print(f"Not expecting '{type(item)}' under list for params.")
            else:
                print(f"Invalid json data: {type(json_data)}")

    def _parse_dictionary_item(self, dict_item: dict[Any, Any]) -> None:
        """
        Parse a dictionary item.

        Args:
            dict_item (dict[Any, Any]): Dictionary item to parse.
        """
        item_name: Optional[str] = None
        item_value: Optional[Any] = None
        for key, value in dict_item.items():
            if key == "name":
                item_name = value
            elif key == "value":
                item_value = value
        if item_name is not None and item_value is not None:
            self.params[item_name] = item_value
        else:
            print(f"Invalid param: {dict_item}")
