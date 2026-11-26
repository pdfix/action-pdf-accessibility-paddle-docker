from pathlib import Path
from typing import Any, Generator, Optional

import cv2
import latex2mathml.converter
from paddlex import create_model
from tqdm import tqdm

from page_renderer import create_image_from_part_of_page
from process_bboxes import PaddleXPostProcessingBBoxes
from process_table import PaddleXPostProcessingTable
from utils import add_mathml_metadata


class PaddleXEngine:
    """
    Class that encapsulates all model predictions done to rendered PDF page.
    """

    def __init__(
        self,
        model: str = "PP-DocLayout-L",
        process_formula: bool = False,
        process_table: bool = False,
        thresholds: Optional[dict] = None,
    ) -> None:
        """
        Initializes Paddle Engine

        Args:
            model (str): One of supported Paddle Layout Models:
                - "PP-DocLayout-L"
                - "RT-DETR-H_layout_17cls"
            process_formula (bool): Whether to process formulas
            process_table (bool): Whether to process tables
            thresholds (dict): Thresholds for layout detection, if not provided
                default thresholds will be used.
        """
        self.model_name: str = model
        self.process_formula: bool = process_formula
        self.process_table: bool = process_table
        # Copy, classes not in the model are removed below
        self.threshold: dict = dict(thresholds or {})

        # Remove thresholds for classes that are not in model
        if model == "RT-DETR-H_layout_17cls":
            for key in range(17, 23):
                self.threshold.pop(key, None)

        # Models are loaded with their first use and used for all pages, tables and formulas
        self._models: dict[str, Any] = {}

    def _model(self, model_name: str, **options: Any) -> Any:
        """
        Load a model from the models folder once and return it on every next call.

        Args:
            model_name (str): Name of the Paddle model (folder in models).
            options (Any): Additional options for create_model (only used when loading).

        Returns:
            Loaded Paddle model.
        """
        if model_name not in self._models:
            model_dir: str = Path(__file__).parent.joinpath(f"../models/{model_name}").resolve().as_posix()
            self._models[model_name] = create_model(model_name=model_name, model_dir=model_dir, device="cpu", **options)
        return self._models[model_name]

    def process_pdf_page_image_with_ai(
        self,
        image: cv2.typing.MatLike,
        id: str,
        page_number: int,
        progress_bar: tqdm,
        total_units_for_page_processing: float,
    ) -> dict:
        """
        Let AI do its magic for PDF page image.

        Args:
            image (cv2.typing.MatLike): Rendered image of PDF page.
            id (string): PDF document name.
            page_number (int): Page number.
            progress_bar (tqdm): Progress bar.
            total_units_for_page_processing (float): How many units progress bar needs to update.

        Returns:
            List of recognized elements with data about possition and type.
        """
        model = self._model(self.model_name, threshold=self.threshold)

        output: Generator[Any, Any, None] = model.predict(input=image, batch_size=1, layout_nms=True)

        for res in output:
            # How many tables and formulas we will process
            number_of_tables: int = len([box for box in res["boxes"] if box["label"] == "table"])
            number_of_formulas: int = len([box for box in res["boxes"] if box["label"] == "formula"])
            boxes_to_process: int = 0
            if self.process_table:
                boxes_to_process += number_of_tables
            if self.process_formula:
                boxes_to_process += number_of_formulas
            # Add one box as layout recognition that already passed
            boxes_to_process += 1

            # Calculate step amount - there will never be division by 0
            step: float = total_units_for_page_processing / boxes_to_process

            # Layout recognition step
            progress_bar.update(step)

            if "boxes" in res:
                for box in res["boxes"]:
                    match box["label"]:
                        case "table":
                            if not self.process_table:
                                continue

                            # Get table image
                            coordinate: list = box["coordinate"]
                            table_image: cv2.typing.MatLike = create_image_from_part_of_page(image, coordinate, 1)

                            # Process table
                            table_dict: dict = self._process_table_image_with_ai_v2(table_image, coordinate)

                            # Save as additional data to PaddleX result
                            box["custom"] = table_dict

                            # Update progress after 1 processed table
                            progress_bar.update(step)

                        case "formula":
                            if not self.process_formula:
                                continue

                            # Get formula image
                            coordinate = box["coordinate"]
                            formula_image: cv2.typing.MatLike = create_image_from_part_of_page(image, coordinate, 1)

                            # Process formula
                            formula_representation: str = self.process_formula_image_with_ai(formula_image)

                            # Save as additional data to PaddleX result
                            if formula_representation != "":
                                box["custom"] = formula_representation

                            # Update progress after 1 processed formula
                            progress_bar.update(step)

                bbox_post_processing: PaddleXPostProcessingBBoxes = PaddleXPostProcessingBBoxes(res)
                res["boxes"] = bbox_post_processing.process_bboxes()

                return res

        # No layout output
        progress_bar.update(total_units_for_page_processing)
        return {}

    def process_formula_image_with_ai(self, image: cv2.typing.MatLike) -> str:
        """
        Let AI do its magic for formula image.

        Args:
            image (cv2.typing.MatLike): Rendered image of formula.

        Returns:
            TBE, currently empty dictionary
        """
        # Formula model prediction
        formula_model = self._model("PP-FormulaNet-L")

        output: Generator[Any, Any, None] = formula_model.predict(input=image, batch_size=1)

        for res in output:
            latex_formula: str = res["rec_formula"]
            mathml_formula: str = self._convert_to_mathml(latex_formula)
            return mathml_formula

        # No formula output
        return ""

    def _convert_to_mathml(self, latex_formula: str) -> str:
        """
        From LaTeX representation of formula create MathML representation of formula.

        Args:
            latex_formula (str): LaTeX representation of formula.

        Returns:
            MathML representation of formula.
        """
        try:
            # For most latex inputs creates mathml-3 representation
            # If it cannot convert it throws exception
            return add_mathml_metadata(latex2mathml.converter.convert(latex_formula), "Paddle")
        except Exception:
            pass
        return ""

    def _process_table_image_with_ai_v2(self, image: cv2.typing.MatLike, coordinate: list) -> dict:
        """
        Let AI do its magic for table image.

        Args:
            image (cv2.typing.MatLike): Rendered image of table.
            coordinate (list): Bounding box of table in rendered PDF page

        Returns:
            List of recognized cell elements with additional data
        """
        # Table classification model prediction
        model = self._model("PP-LCNet_x1_0_table_cls")

        output: Generator[Any, Any, None] = model.predict(input=image, batch_size=1)

        for classification_result in output:
            is_wired: bool = self._use_wired_model(classification_result)

            # Table cells model prediction
            table_cell_model_name: str = (
                "RT-DETR-L_wired_table_cell_det" if is_wired else "RT-DETR-L_wireless_table_cell_det"
            )
            table_cell_model = self._model(table_cell_model_name)

            cell_output = table_cell_model.predict(input=image, batch_size=1)

            for cell_results in cell_output:
                # We are processing 1 table so we are expecting just 1 result:
                post_processing: PaddleXPostProcessingTable = PaddleXPostProcessingTable()
                return post_processing.create_custom_result_from_paddlex_cell_result(cell_results, coordinate)

        # No classification or cell recognition
        return {}

    def _use_wired_model(self, result: dict) -> bool:
        """
        Checks result of table clasification and returns if table is wired or wireless.

        Args:
            result (dict): Result from table classification

        Returns:
            True if table is wired. False if table is wireless.
        """
        if result["scores"][0] > result["scores"][1]:
            return result["label_names"][0] == "wired_table"
        else:
            return result["label_names"][0] == "wireless_table"
