import os
from pathlib import Path

import cv2
import latex2mathml.converter
from paddlex import create_model
from tqdm import tqdm

from page_renderer import create_image_from_part_of_page
from process_bboxes import PaddleXPostProcessingBBoxes
from process_table import PaddleXPostProcessingTable


class PaddleXEngine:
    """
    Class that encapsulates all model predictions done to rendered PDF page.
    """

    def __init__(
        self,
        model: str = "PP-DocLayout-L",
        process_formula: bool = False,
        process_table: bool = False,
        thresholds: dict = {},
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
        self.model_name = model
        model_path = os.path.join(Path(__file__).parent.absolute(), f"../models/{model}")
        self.model_dir = model_path
        self.process_formula = process_formula
        self.process_table = process_table
        self.threshold = thresholds

        # Remove thresholds for classes that are not in model
        if model == "RT-DETR-H_layout_17cls":
            for key in range(17, 23):
                self.threshold.pop(key, None)

    def process_pdf_page_image_with_ai(
        self,
        image: cv2.typing.MatLike,
        id: str,
        page_number: int,
        progress_bar: tqdm,
        max_formulas_and_tables_per_page: int,
    ) -> dict:
        """
        Let AI do its magic for PDF page image.

        Args:
            image (cv2.typing.MatLike): Rendered image of PDF page.
            id (string): PDF document name.
            page_number (int): Page number.
            progress_bar (tqdm): Progress bar that we update for each model
                call.
            max_formulas_and_tables_per_page (int): Our estimation how many
                tables and formulas can be in one page.

        Returns:
            List of recognized elements with data about possition and type.
        """
        model = create_model(
            model_name=self.model_name,
            model_dir=self.model_dir,
            device="cpu",
            threshold=self.threshold,
        )

        output = model.predict(input=image, batch_size=1, layout_nms=True)

        for res in output:
            output_name = f"{id}-page{page_number}.png"
            output_path = os.path.join(Path(__file__).parent.absolute(), f"../output/{output_name}")
            res.save_to_img(save_path=output_path)

            table_index = 0

            # How many tables and formulas we will process
            number_of_tables = len([box for box in res["boxes"] if box["label"] == "table"])
            number_of_formulas = len([box for box in res["boxes"] if box["label"] == "formula"])
            boxes_to_process = 0
            if self.process_table:
                boxes_to_process += number_of_tables
            if self.process_formula:
                boxes_to_process += number_of_formulas

            # Add one box as layout recognition that already passed
            boxes_to_process += 1

            # Calculate steps - there will never be division by 0
            # not all processings are equal in time but at least keep updating the progress bar
            one_step: int = max_formulas_and_tables_per_page // boxes_to_process
            last_step: int = max_formulas_and_tables_per_page - (boxes_to_process * one_step)

            # Layout recognition is already done
            progress_bar.update(one_step)

            if "boxes" in res:
                for box in res["boxes"]:
                    match box["label"]:
                        case "table":
                            if not self.process_table:
                                continue

                            # Get table image
                            coordinate = box["coordinate"]
                            table_image = create_image_from_part_of_page(image, coordinate, 1)

                            # Process table
                            output_file_name = f"{id}_{page_number}-table{table_index}.png"
                            output_file_path = os.path.join(
                                Path(__file__).parent.absolute(), f"../output/{output_file_name}"
                            )
                            table_index += 1
                            table_dict = self._process_table_image_with_ai_v2(table_image, coordinate, output_file_path)

                            # Save as additional data to PaddleX result
                            box["custom"] = table_dict

                            # Update progress after 1 processed table
                            progress_bar.update(one_step)

                        case "formula":
                            if not self.process_formula:
                                continue

                            # Get formula image
                            coordinate = box["coordinate"]
                            formula_image = create_image_from_part_of_page(image, coordinate, 1)

                            # Process formula
                            formula_representation = self.process_formula_image_with_ai(formula_image)

                            # Save as additional data to PaddleX result
                            if formula_representation != "":
                                box["custom"] = formula_representation

                            # Update progress after 1 processed formula
                            progress_bar.update(one_step)

                bbox_post_processing = PaddleXPostProcessingBBoxes(res)
                res["boxes"] = bbox_post_processing.process_bboxes()
                if last_step > 0:
                    progress_bar.update(last_step)

                return res

        # No layout output
        progress_bar.update(max_formulas_and_tables_per_page)
        return {}

    def process_formula_image_with_ai(self, image: cv2.typing.MatLike) -> str:
        """
        Let AI do its magic for formula image.

        Args:
            image (cv2.typing.MatLike): Rendered image of formula.

        Returns:
            TBE, currently empty dictionary
        """
        model_name = "PP-FormulaNet-L"
        model_path = os.path.join(Path(__file__).parent.absolute(), f"../models/{model_name}")

        # Formula model prediction
        formula_model = create_model(
            model_name=model_name,
            model_dir=model_path,
            device="cpu",
        )

        output = formula_model.predict(input=image, batch_size=1)

        for res in output:
            latex_formula = res["rec_formula"]
            mathml_formula = self._convert_to_mathml(latex_formula)
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
            return latex2mathml.converter.convert(latex_formula)
        except Exception:
            pass
        return ""

    def _process_table_image_with_ai_v2(
        self, image: cv2.typing.MatLike, coordinate: list, output_file_path: str
    ) -> dict:
        """
        Let AI do its magic for table image.

        Args:
            image (cv2.typing.MatLike): Rendered image of table.
            coordinate (list): Bounding box of table in rendered PDF page
            output_file_path (string): Unique absolute file path.

        Returns:
            List of recognized cell elements with additional data
        """
        model_name = "PP-LCNet_x1_0_table_cls"
        model_path = os.path.join(Path(__file__).parent.absolute(), f"../models/{model_name}")

        # Table classification model prediction
        model = create_model(
            model_name=model_name,
            model_dir=model_path,
            device="cpu",
        )

        output = model.predict(input=image, batch_size=1)

        for classification_result in output:
            is_wired = self._use_wired_model(classification_result)

            # Table cells model prediction
            table_cell_model_name = (
                "RT-DETR-L_wired_table_cell_det" if is_wired else "RT-DETR-L_wireless_table_cell_det"
            )
            table_cell_model_dir = os.path.join(Path(__file__).parent.absolute(), f"../models/{table_cell_model_name}")

            table_cell_model = create_model(
                model_name=table_cell_model_name,
                model_dir=table_cell_model_dir,
                device="cpu",
            )

            cell_output = table_cell_model.predict(input=image, batch_size=1)

            for cell_results in cell_output:
                cell_results.save_to_img(save_path=output_file_path)

                # We are processing 1 table so we are expecting just 1 result:
                post_processing = PaddleXPostProcessingTable()
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
