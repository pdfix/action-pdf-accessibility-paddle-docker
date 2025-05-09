import cv2
from paddlex import create_model
from tqdm import tqdm

from page_renderer import create_image_from_part_of_page
from process_table import create_custom_result_from_paddlex_cell_result


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

            # we are processing 1 table so we are expecting just 1 result:
            return create_custom_result_from_paddlex_cell_result(cell_results, coordinate)

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

    return ""
