import json
import math
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pdfixsdk import PdfDevRect, PdfPageView, PdfRect, __version__, kPdeImage


class TemplateJsonCreator:
    """
    Class that prepares each page and in the end creates whole template json file for PDFix-SDK
    """

    # Constants
    CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        """
        Initializes pdfix sdk template json creation by preparing list for each page.
        """
        self.template_json_pages: list = []
        self.formulas: list = []

    def get_formulas(self) -> list:
        """
        Return list of all formula ids with latex text that were gathered during processing pages.

        Returns:
            List of all formulas
        """
        return self.formulas

    def create_json_dict_for_document(self, model: str, zoom: float) -> dict:
        """
        Prepare PDFix SDK json template for whole document.

        Args:
            model (list): Paddle layout model name.
            zoom (float): Zoom level that page was rendered with.

        Returns:
            Template json for whole document
        """
        created_date = date.today().strftime("%Y-%m-%d")
        metadata: dict = {
            "author": f"AutoTag / Create Layout Template (Paddle) {self._get_current_version()}",
            "created": created_date,
            "modified": created_date,
            "notes": f"Created using PaddleX layout model: {model} and PDFix zoom: {zoom}",
            "sdk_version": __version__,
            # we are creating first one always so it is always "1"
            "version": "1",
        }
        page_map: list = [{"graphic_table_detect": "0", "statement": "$if", "text_table_detect": "0"}]

        return {
            "metadata": metadata,
            "template": {
                "element_create": self.template_json_pages,
                "pagemap": page_map,
            },
        }

    def process_page(self, results: dict, page_number: int, page_view: PdfPageView, zoom: float) -> None:
        """
        Prepare json template for PDFix SDK for one page and save it internally to use later in
        create_json_dict_for_document.

        Args:
            results (dict): Dictionary of results from Paddle, where are
                list of detected elements, ...
            page_number (int): PDF file page number.
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.
            zoom (float): Zoom level that page was rendered with.
        """
        elements: list = self._create_json_for_elements(results, page_view, page_number)

        json_for_page = {
            "comment": f"Page {page_number}",
            "elements": elements,
            "query": {
                "$and": [{"$page_num": page_number}],
            },
            "statement": "$if",
        }
        self.template_json_pages.append(json_for_page)

    def _get_current_version(self) -> str:
        """
        Read the current version from config.json.

        Returns:
            The current version of the Docker image.
        """
        config_path = os.path.join(Path(__file__).parent.absolute(), f"../{self.CONFIG_FILE}")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("version", "unknown")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading {self.CONFIG_FILE}: {e}", file=sys.stderr)
            return "unknown"

    def _generate_unique_id(self, page_number: int, type: int, coordinate: list) -> int:
        """
        Helper function inspired by PDFix SDK functions to generate unique id.

        Args:
            page_number (int): PDF file page number.
            type (int): Type of bounding box.
            coordinate (list): The bounding box coordinates.

        Returns:
            32-bit integer number.
        """
        # Create string that we will hash
        string_to_hash = f"{page_number}{type}"
        for index in range(4):
            string_to_hash += str(int(coordinate[index]))

        # Hash that string
        # Ensure we never return 0
        hash_value = 0x811C9DC5
        prime_number = 0x1000193
        for character in string_to_hash:
            # Gets the ASCII value of character
            power_giver = ord(character)
            hash_value ^= power_giver
            hash_value *= prime_number
            # Make sure it never overflows 32bit integer
            hash_value &= 0xFFFFFFFF
        return hash_value

    def _create_json_for_elements(self, results: dict, page_view: PdfPageView, page_number: int) -> list:
        """
        Prepare initial structural elements for the template based on
        detected regions.

        Args:
            results (dict): Dictionary of results from Paddle, where are list of detected elements, ...
            page_view (PdfPageView): The view of the PDF page used for coordinate conversion.
            page_number (int): PDF file page number.

        Returns:
            List of elements with parameters.
        """
        elements: list = []

        # do not process if nothing is for processing
        if "boxes" not in results:
            return elements

        for result in results["boxes"]:
            element: dict[str, Any] = {}

            rect = PdfDevRect()
            rect.left = math.floor(result["coordinate"][0])  # min_x
            rect.top = math.floor(result["coordinate"][1])  # min_y
            rect.right = math.ceil(result["coordinate"][2])  # max_x
            rect.bottom = math.ceil(result["coordinate"][3])  # max_y
            bbox = page_view.RectToPage(rect)
            element["bbox"] = [str(bbox.left), str(bbox.bottom), str(bbox.right), str(bbox.top)]
            label = result["label"].lower()
            element["comment"] = f"{label} {round(result['score'] * 100)}%"

            # Determine element type
            match label:
                case "abstract":
                    element["type"] = "pde_text"

                case "algorithm":
                    element["type"] = "pde_text"

                case "aside_text":
                    element["flag"] = "artifact"
                    element["type"] = "pde_text"

                case "chart":
                    element["type"] = "pde_image"

                case "chart_title":
                    element["tag"] = "Caption"
                    element["type"] = "pde_text"

                case "content":
                    element["type"] = "pde_text"

                case "doc_title":
                    element["tag"] = "Title"
                    element["type"] = "pde_text"

                case "figure_title":
                    element["tag"] = "Caption"
                    element["type"] = "pde_text"

                case "footer":
                    element["flag"] = "footer|artifact"
                    element["type"] = "pde_text"

                case "footer_image":
                    element["flag"] = "footer|artifact"
                    element["type"] = "pde_image"

                case "footnote":
                    element["type"] = "pde_text"

                case "formula":
                    if "custom" in result:
                        formula_id = self._generate_unique_id(page_number, kPdeImage, result["coordinate"])
                        self.formulas.append((formula_id, result["custom"]))
                        element["id"] = str(formula_id)
                    element["tag"] = "Formula"
                    element["type"] = "pde_image"

                case "formula_number":
                    element["type"] = "pde_text"

                case "header":
                    element["flag"] = "header|artifact"
                    element["type"] = "pde_text"

                case "header_image":
                    element["flag"] = "header|artifact"
                    element["type"] = "pde_image"

                case "image":
                    element["type"] = "pde_image"

                case "number":
                    number_flag = self._is_footer_or_header(page_view, bbox)
                    element["flag"] = f"{number_flag}|artifact"
                    element["type"] = "pde_text"

                case "paragraph_title":
                    element["heading"] = "h1"
                    element["type"] = "pde_text"

                case "reference":
                    element["tag"] = "Reference"
                    element["type"] = "pde_text"

                case "seal":
                    element["flag"] = "artifact"
                    element["type"] = "pde_image"

                case "table":
                    if "custom" in result:
                        cell_elements: list = self._create_table_cells(result["custom"], page_view)
                        element["element_template"] = {
                            "template": {
                                "element_create": [{"elements": cell_elements, "query": {}, "statement": "$if"}],
                                "table_update": [{"cell_header": "true", "statement": "$if"}],
                            },
                        }
                        element["row_num"] = result["custom"]["rows"]
                        element["col_num"] = result["custom"]["columns"]
                    element["type"] = "pde_table"

                case "table_title":
                    element["tag"] = "Caption"
                    element["type"] = "pde_text"

                case "text":
                    element["type"] = "pde_text"

                case _:
                    element["type"] = "pde_text"

            elements.append(element)

        elements = sorted(elements, key=lambda x: (float(x["bbox"][3]), 1000.0 - float(x["bbox"][0])), reverse=True)

        return elements

    def _create_table_cells(self, result: dict, page_view: PdfPageView) -> list:
        """
        Prepare table cell elements.

        Args:
            result (dict): Custom result created for one specific table
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.

        Returns:
            List of cell elements with parameters.
        """
        cells: list = []

        for cell in result["cells"]:
            cell_position: str = f"[{cell['row']}, {cell['column']}]"
            cell_span: str = f"[{cell['row_span']}, {cell['column_span']}]"

            create_cell: dict = {
                "cell_column": str(cell["column"]),
                "cell_column_span": str(cell["column_span"]),
                "cell_row": str(cell["row"]),
                "cell_row_span": str(cell["row_span"]),
                "comment": f"Cell Pos: {cell_position} Span: {cell_span}",
                "type": "pde_cell",
            }

            # # we are not using "structure model" so we do not have this information
            # create_cell["cell_header"] = self._convert_bool_to_str(False),
            # create_cell["cell_scope"] = "0"

            if "bbox" in cell:
                rect = PdfDevRect()
                rect.left = math.ceil(cell["bbox"][0])  # min_x
                rect.top = math.ceil(cell["bbox"][1])  # min_y
                rect.right = math.floor(cell["bbox"][2])  # max_x
                rect.bottom = math.floor(cell["bbox"][3])  # max_y
                bbox = page_view.RectToPage(rect)
                create_cell["bbox"] = [str(bbox.left), str(bbox.bottom), str(bbox.right), str(bbox.top)]

            cells.append(create_cell)

        return cells

    def _convert_bool_to_str(self, value: bool) -> str:
        """
        Create value for json as pdfix template expects

        Args:
            value (bool): calue to convert

        Returns:
            Converted bool to string for json purposes
        """
        return "true" if value else "false"

    def _is_footer_or_header(self, page_view: PdfPageView, bbox: PdfRect) -> str:
        """
        According to Y coordinate of bbox return if it is "header" or "footer"

        Args:
            page_view (PdfPageView): Page view to get page heigh
            bbox (PdfRect): Bounding box in PDF coordinates (Y=0 is bottom)

        Returns:
            "header" or "footer"
        """
        page_height = page_view.GetDeviceHeight()
        half_height = page_height / 2
        return "footer" if bbox.top < half_height else "header"
