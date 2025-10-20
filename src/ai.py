from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

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
        self.model_name: str = model
        model_path: str = Path(__file__).parent.joinpath(f"../models/{model}").resolve().as_posix()
        self.model_dir: str = model_path
        self.process_formula: bool = process_formula
        self.process_table: bool = process_table
        self.threshold: dict = thresholds

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
            output_name: str = f"{id}-page{page_number}.png"
            output_path: str = Path(__file__).parent.joinpath(f"../output/{output_name}").resolve().as_posix()
            res.save_to_img(save_path=output_path)

            table_index: int = 0

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
                            coordinate: list = box["coordinate"]
                            table_image: cv2.typing.MatLike = create_image_from_part_of_page(image, coordinate, 1)

                            # Process table
                            output_file_name: str = f"{id}_{page_number}-table{table_index}.png"
                            output_file_path: str = (
                                Path(__file__).parent.joinpath(f"../output/{output_file_name}").resolve().as_posix()
                            )
                            table_index += 1
                            table_dict: dict = self._process_table_image_with_ai_v2(
                                table_image, coordinate, output_file_path
                            )

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
        model_name: str = "PP-FormulaNet-L"
        model_path: str = Path(__file__).parent.joinpath(f"../models/{model_name}").resolve().as_posix()

        # Formula model prediction
        formula_model = create_model(
            model_name=model_name,
            model_dir=model_path,
            device="cpu",
        )

        output = formula_model.predict(input=image, batch_size=1)

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
            return latex2mathml.converter.convert(latex_formula)
        except Exception:
            pass
        return ""

    def add_mathml_metadata(self, mathml_str: str) -> str:
        """
        Adds metadata annotations to a MathML string using <semantics> and <annotation>.

        Parameters:
            mathml_str (str): The MathML content as a string.

        Returns:
            str: The updated MathML string with metadata annotations.
        """
        # Parse the MathML string into an XML element
        try:
            root: ET.Element[str] = ET.fromstring(mathml_str)
        except ET.ParseError:
            # Failed to parse the string into xml
            return mathml_str

        # Ensure the root is <math>
        if root.tag != "{http://www.w3.org/1998/Math/MathML}math" and root.tag != "math":
            # Failed to find <math> tag as root
            return mathml_str

        # Define the MathML namespace
        NS = {"m": "http://www.w3.org/1998/Math/MathML"}
        ET.register_namespace("", NS["m"])

        # Create <semantics> if it's not already there
        existing_semantics: Optional[ET.Element[str]] = root.find("m:semantics", NS)

        if existing_semantics is not None:
            semantics: ET.Element[str] = existing_semantics
        else:
            # Move all children of <math> into <semantics>
            semantics = ET.Element("{http://www.w3.org/1998/Math/MathML}semantics")
            for child in list(root):
                semantics.append(child)
                root.remove(child)
            root.append(semantics)

        # Create metadata annotations
        metadata_1: ET.Element[str] = ET.Element("{http://www.w3.org/1998/Math/MathML}annotation")
        metadata_1.text = "Generated by PaddleX AI"
        metadata_1.set("encoding", "text/plain")

        metadata_2: ET.Element[str] = ET.Element("{http://www.w3.org/1998/Math/MathML}annotation")
        metadata_2.text = "Converted from LaTeX to MathML using latex2mathml"
        metadata_2.set("encoding", "text/plain")

        # Add annotations only if they don't already exist
        existing_texts: set[str] = {ann.text for ann in semantics.findall("m:annotation", NS) if ann.text}
        if metadata_1.text not in existing_texts:
            semantics.append(metadata_1)
        if metadata_2.text not in existing_texts:
            semantics.append(metadata_2)

        # Return the modified XML as string
        return ET.tostring(root, encoding="unicode")

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
        model_name: str = "PP-LCNet_x1_0_table_cls"
        model_path: str = Path(__file__).parent.joinpath(f"../models/{model_name}").resolve().as_posix()

        # Table classification model prediction
        model = create_model(
            model_name=model_name,
            model_dir=model_path,
            device="cpu",
        )

        output = model.predict(input=image, batch_size=1)

        for classification_result in output:
            is_wired: bool = self._use_wired_model(classification_result)

            # Table cells model prediction
            table_cell_model_name: str = (
                "RT-DETR-L_wired_table_cell_det" if is_wired else "RT-DETR-L_wireless_table_cell_det"
            )
            table_cell_model_dir: str = (
                Path(__file__).parent.joinpath(f"../models/{table_cell_model_name}").resolve().as_posix()
            )

            table_cell_model = create_model(
                model_name=table_cell_model_name,
                model_dir=table_cell_model_dir,
                device="cpu",
            )

            cell_output = table_cell_model.predict(input=image, batch_size=1)

            for cell_results in cell_output:
                cell_results.save_to_img(save_path=output_file_path)

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
