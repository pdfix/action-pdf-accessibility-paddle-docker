import cv2
from paddlex import create_model
from tqdm import tqdm

from page_renderer import create_image_from_part_of_page
from process_table import PaddleXPostProcessingTable


class PaddleXEngine:
    """
    Class that encapsulates all model predictions done to rendered PDF page.
    """

    def __init__(self, model: str = "PP-DocLayout-L") -> None:
        self.model_name = model
        self.model_dir = f"models/{model}"
        match model:
            case "PP-DocLayout-L":
                self.threshold = (
                    {
                        0: 0.3,  # paragraph_title
                        1: 0.5,  # image
                        2: 0.5,  # text
                        3: 0.5,  # number
                        4: 0.5,  # abstract
                        5: 0.5,  # content
                        6: 0.5,  # figure_title
                        7: 0.3,  # formula
                        8: 0.5,  # table
                        9: 0.5,  # table_title
                        10: 0.5,  # reference
                        11: 0.5,  # doc_title
                        12: 0.5,  # footnote
                        13: 0.3,  # header (default 0.5)
                        14: 0.5,  # algorithm
                        15: 0.5,  # footer
                        16: 0.3,  # seal
                        17: 0.5,  # chart_title
                        18: 0.5,  # chart
                        19: 0.5,  # formula_number
                        20: 0.3,  # header_image (default 0.5)
                        21: 0.5,  # footer_image
                        22: 0.5,  # aside_text
                    },
                )
            case "RT-DETR-H_layout_17cls":
                self.threshold = (
                    {
                        0: 0.3,  # paragraph_title
                        1: 0.3,  # image (default 0.5)
                        2: 0.5,  # text
                        3: 0.5,  # number
                        4: 0.5,  # abstract
                        5: 0.5,  # content
                        6: 0.5,  # figure_title
                        7: 0.3,  # formula
                        8: 0.5,  # table
                        9: 0.5,  # table_title
                        10: 0.5,  # reference
                        11: 0.3,  # doc_title (default 0.5)
                        12: 0.5,  # footnote
                        13: 0.3,  # header (default 0.5)
                        14: 0.5,  # algorithm
                        15: 0.5,  # footer
                        16: 0.3,  # seal
                    },
                )

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
            res.save_to_img(save_path=f"./output/{id}-page{page_number}.png")

            table_index = 0

            # How many tables and formulas we will process
            boxes_to_process = len(
                [box for box in res["boxes"] if box["label"] == "table" or box["label"] == "formula"]
            )

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
                            # Get table image
                            coordinate = box["coordinate"]
                            table_image = create_image_from_part_of_page(image, coordinate, 1)

                            # Process table
                            output_file_path = f"./output/{id}_{page_number}-table{table_index}.png"
                            table_index += 1
                            table_dict = self._process_table_image_with_ai_v2(table_image, coordinate, output_file_path)

                            # Save as additional data to PaddleX result
                            box["custom"] = table_dict

                            # Update progress after 1 processed table
                            progress_bar.update(one_step)

                        case "formula":
                            # Get formula image
                            coordinate = box["coordinate"]
                            formula_image = create_image_from_part_of_page(image, coordinate, 1)

                            # Process formula
                            formula_rec = self._process_formula_image_with_ai(formula_image)

                            # Save as additional data to PaddleX result
                            box["custom"] = formula_rec

                            # Update progress after 1 processed formula
                            progress_bar.update(one_step)

                progress_bar.update(last_step)

                return res

        # No layout output
        progress_bar.update(max_formulas_and_tables_per_page)
        return {}

    def _process_table_image_with_ai_v2(
        self, image: cv2.typing.MatLike, coordinate: list, output_file_path: str
    ) -> dict:
        """
        Let AI do its magic for table image.

        Args:
            image (cv2.typing.MatLike): Rendered image of table.
            coordinate (list): Bounding box of table in rendered PDF page
            output_file_path (string): Unique file path.

        Returns:
            List of recognized cell elements with additional data
        """
        # Table classification model prediction
        model = create_model(
            model_name="PP-LCNet_x1_0_table_cls",
            model_dir="models/PP-LCNet_x1_0_table_cls",
            device="cpu",
        )

        output = model.predict(input=image, batch_size=1)

        for classification_result in output:
            is_wired = self._use_wired_model(classification_result)

            # Table cells model prediction
            table_cell_model_name = (
                "RT-DETR-L_wired_table_cell_det" if is_wired else "RT-DETR-L_wireless_table_cell_det"
            )
            table_cell_model_dir = f"models/{table_cell_model_name}"

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

    def _process_formula_image_with_ai(self, image: cv2.typing.MatLike) -> str:
        """
        Let AI do its magic for formula image.

        Args:
            image (cv2.typing.MatLike): Rendered image of formula.

        Returns:
            TBE, currently empty dictionary
        """

        # Formula model prediction
        formula_model = create_model(
            model_name="PP-FormulaNet-L",
            model_dir="models/PP-FormulaNet-L",
            device="cpu",
        )

        output = formula_model.predict(input=image, batch_size=1)

        for res in output:
            return res["rec_formula"]

        # No formula output
        return ""
