import cv2
from paddlex import create_model
from tqdm import tqdm

from page_renderer import create_image_from_part_of_page


def process_pdf_page_image_with_ai(
    image: cv2.typing.MatLike, id: str, page_number: int, progress_bar: tqdm, max_formulas_and_tables_per_page: int
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
    # Model taken from PPStructureV3 pipeline
    model = create_model(
        model_name="PP-DocLayout-L",
        model_dir="models/PP-DocLayout-L",
        device="cpu",
        threshold={
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

    # # Model taken from layout pipeline
    # model = create_model(
    #     model_name="RT-DETR-H_layout_17cls",
    #     model_dir="models/RT-DETR-H_layout_17cls",
    #     device="cpu",
    #     threshold={
    #         0: 0.3,  # paragraph_title
    #         1: 0.3,  # image (default 0.5)
    #         2: 0.5,  # text
    #         3: 0.5,  # number
    #         4: 0.5,  # abstract
    #         5: 0.5,  # content
    #         6: 0.5,  # figure_title
    #         7: 0.3,  # formula
    #         8: 0.5,  # table
    #         9: 0.5,  # table_title
    #         10: 0.5,  # reference
    #         11: 0.3,  # doc_title (default 0.5)
    #         12: 0.5,  # footnote
    #         13: 0.3,  # header (default 0.5)
    #         14: 0.5,  # algorithm
    #         15: 0.5,  # footer
    #         16: 0.3,  # seal
    #     },
    # )

    output = model.predict(input=image, batch_size=1, layout_nms=True)

    for res in output:
        # res.print()
        res.save_to_img(save_path=f"./output/{id}-page{page_number}.png")
        # res.save_to_json("./output/")

        table_index = 0
        formula_index = 0

        boxes_to_process = len([box for box in res["boxes"] if box["label"] == "table" or box["label"] == "formula"])

        # Add one box as layout recognition
        boxes_to_process += 1

        # Calculate steps - there will never be division by 0
        # not all processings are equal in time but at least keep some progress for customer
        one_step: int = max_formulas_and_tables_per_page // boxes_to_process
        last_step: int = max_formulas_and_tables_per_page - (boxes_to_process * one_step)

        # Layout recognition is already one
        progress_bar.update(one_step)

        if "boxes" in res:
            for box in res["boxes"]:
                if box["label"] == "table":
                    coordinate = box["coordinate"]
                    table_image = create_image_from_part_of_page(image, coordinate, 1)
                    output_file_path = f"./output/{id}_{page_number}-table{table_index}.png"
                    table_dict = process_table_image_with_ai_v2(table_image, coordinate, output_file_path)
                    box["custom"] = table_dict
                    table_index += 1
                    progress_bar.update(one_step)
                if box["label"] == "formula":
                    coordinate = box["coordinate"]
                    formula_image = create_image_from_part_of_page(image, coordinate, 1)
                    output_file_path = f"./output/{id}_{page_number}-formula{formula_index}.png"
                    formula_rec = process_formula_image_with_ai(formula_image, output_file_path)
                    box["custom"] = formula_rec
                    formula_index += 1
                    progress_bar.update(one_step)

            progress_bar.update(last_step)

            return res

    # no output
    progress_bar.update(max_formulas_and_tables_per_page)
    return {}


def process_table_image_with_ai_v2(image: cv2.typing.MatLike, coordinate: list, output_file_path: str) -> dict:
    """
    Let AI do its magic for table image.

    Args:
        image (cv2.typing.MatLike): Rendered image of table.
        coordinate (list): Bounding box of table in rendered PDF page
        output_file_path (string): Unique file path.

    Returns:
        List of recognized cell elements with additional data
    """
    # table classification
    model = create_model(
        model_name="PP-LCNet_x1_0_table_cls",
        model_dir="models/PP-LCNet_x1_0_table_cls",
        device="cpu",
    )

    output = model.predict(input=image, batch_size=1)

    for res in output:
        # res.print()
        is_wired = use_wired_model(res)

        # table cells
        table_cell_model_name = "RT-DETR-L_wired_table_cell_det" if is_wired else "RT-DETR-L_wireless_table_cell_det"
        table_cell_model_dir = f"models/{table_cell_model_name}"

        table_cell_model = create_model(
            model_name=table_cell_model_name,
            model_dir=table_cell_model_dir,
            device="cpu",
        )

        cell_output = table_cell_model.predict(input=image, batch_size=1)

        for cell_results in cell_output:
            # cell_results.print()
            cell_results.save_to_img(save_path=output_file_path)

            # processing table results into usable structure
            size_rows, size_columns, cells = create_table_structure(cell_results)

            # calculating page bounding box
            x: float = coordinate[0]
            y: float = coordinate[1]
            for cell in cells:
                cell["bbox"] = [
                    cell["box"][0] + x,
                    cell["box"][1] + y,
                    cell["box"][2] + x,
                    cell["box"][3] + y,
                ]

            # it should never return more than 1 result:
            return {
                "rows": size_rows,
                "columns": size_columns,
                "cells": cells,
            }

    return {}


def use_wired_model(result: dict) -> bool:
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


def create_table_structure(result: dict) -> tuple[int, int, list]:
    """
    From results of table cell recognition create data for each cell:
        - row number
        - row span
        - column number
        - column span

    Args:
        result (dict): Result from table cell recognition

    Returns:
        Number of rows in table.
        Number of columns in table.
        List of all cell with all additional data
    """
    row_lines: list = []
    column_lines: list = []

    for box in result["boxes"]:
        # vertical lines
        left_line: float = int(box["coordinate"][0])
        right_line: float = int(box["coordinate"][2])
        if left_line not in column_lines:
            column_lines.append(left_line)
        if right_line not in column_lines:
            column_lines.append(right_line)

        # horizontal lines
        top_line: int = int(box["coordinate"][1])
        bottom_line: int = int(box["coordinate"][3])
        if top_line not in row_lines:
            row_lines.append(top_line)
        if bottom_line not in row_lines:
            row_lines.append(bottom_line)

    def clean_lines(lines: list) -> list:
        # sort lines in ascending order
        lines.sort()

        # choose number smaller than any possible, All lines are 0 or greater
        previous: int = -10

        # add only lines that are not close to each other (difference of at least 2)
        result_lines: list = []

        for line in lines:
            if line - previous > 1:
                result_lines.append(line)
            previous = line

        return result_lines

    row_lines = clean_lines(row_lines)
    column_lines = clean_lines(column_lines)
    number_rows: int = len(row_lines) - 1
    number_columns: int = len(column_lines) - 1

    def calculate_cell_data(min: int, max: int, lines: list) -> tuple[int, int]:
        def find_index(target: int, sorted_list: list) -> int:
            lower_bound = target - 2
            upper_bound = target + 2
            for index, value in enumerate(sorted_list):
                if lower_bound <= value <= upper_bound:
                    return index
            # not found
            return -1

        min_index = find_index(min, lines)
        max_index = find_index(max, lines)

        span = max_index - min_index
        n = min_index + 1
        return n, span

    cells_with_data: list = []
    for box in result["boxes"]:
        left: float = box["coordinate"][0]
        top: float = box["coordinate"][1]
        right: float = box["coordinate"][2]
        bottom: float = box["coordinate"][3]

        row_number, row_span = calculate_cell_data(int(top), int(bottom), row_lines)
        column_number, column_span = calculate_cell_data(int(left), int(right), column_lines)

        cell_result: dict = {
            "row": row_number,
            "column": column_number,
            "row_span": row_span,
            "column_span": column_span,
            "box": [left, top, right, bottom],
        }
        cells_with_data.append(cell_result)

    # sort cells by ascending coordinates: Y (row) and X (column)
    cells_with_data = sorted(cells_with_data, key=lambda x: (x["row"], x["column"]))

    return number_rows, number_columns, cells_with_data


def process_formula_image_with_ai(image: cv2.typing.MatLike, output_file_path: str) -> str:
    """
    Let AI do its magic for formula image.

    Args:
        image (cv2.typing.MatLike): Rendered image of formula.
        output_file_path (string): Unique file path.

    Returns:
        TBE, currently empty dictionary
    """
    # cv2.imwrite(output_file_path, image)

    formula_model = create_model(
        model_name="PP-FormulaNet-L",
        model_dir="models/PP-FormulaNet-L",
        device="cpu",
    )

    output = formula_model.predict(input=image, batch_size=1)  # threshold=0.3

    for res in output:
        # res.print()
        return res["rec_formula"]

    print("No results for formula")
    cv2.imwrite(output_file_path, image)
    return ""
