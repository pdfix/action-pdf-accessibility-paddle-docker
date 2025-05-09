def create_custom_result_from_paddlex_cell_result(cell_results: dict, coordinate: list) -> dict:
    """
    From results of table cell recognition create data for each cell:
        - row number
        - row span
        - column number
        - column span
        - box - bbox in table coordinates
        - bbox - bbox in page coordinates

    Args:
        cell_results (dict): Result from table cell recognition
        coordinate (list): Bbox of table we are processing

    Returns:
        Number of rows in table.
        Number of columns in table.
        List of all cell with all additional data
    """
    if "boxes" not in cell_results or len(cell_results["boxes"]) == 0:
        return {
            "rows": 0,
            "columns": 0,
            "cells": [],
        }

    row_lines, column_lines = create_table_row_and_column_lines(cell_results)

    number_rows: int = len(row_lines) - 1
    number_columns: int = len(column_lines) - 1

    table_min_x: float = coordinate[0]
    table_min_y: float = coordinate[1]

    cells_with_data: list = []
    for box in cell_results["boxes"]:
        min_x: float = box["coordinate"][0]
        min_y: float = box["coordinate"][1]
        max_x: float = box["coordinate"][2]
        max_y: float = box["coordinate"][3]

        # row_number, row_span = calculate_position_and_span(int(min_y), int(max_y), row_lines)
        # column_number, column_span = calculate_position_and_span(int(min_x), int(max_x), column_lines)

        row_min_index, row_max_index, row_number, row_span = calculate_indexes_position_span(
            int(min_y), int(max_y), row_lines
        )
        column_min_index, column_max_index, column_number, column_span = calculate_indexes_position_span(
            int(min_x), int(max_x), column_lines
        )

        # bbox = [min_x, min_y, max_x, max_y]
        bbox = [
            column_lines[column_min_index],
            row_lines[row_min_index],
            column_lines[column_max_index],
            row_lines[row_max_index],
        ]

        cell_result: dict = {
            "row": row_number,
            "column": column_number,
            "row_span": row_span,
            "column_span": column_span,
            "box": bbox,
            "bbox": [table_min_x + bbox[0], table_min_y + bbox[1], table_min_x + bbox[2], table_min_y + bbox[3]],
        }
        cells_with_data.append(cell_result)

    # sort cells by ascending coordinates: Y (row) and X (column)
    cells_with_data = sorted(cells_with_data, key=lambda x: (x["row"], x["column"]))

    return {
        "rows": number_rows,
        "columns": number_columns,
        "cells": cells_with_data,
    }


def create_table_row_and_column_lines(result: dict) -> tuple[list, list]:
    """
    From results of table cell recognition create all table lines

    Args:
        result (dict): Result from table cell recognition

    Returns:
        Table row lines
        Table column lines
    """
    row_lines: list = create_lines(result, 1, 3)
    column_lines: list = create_lines(result, 0, 2)
    row_lines = clean_lines(row_lines)
    column_lines = clean_lines(column_lines)

    return row_lines, column_lines


def create_lines(result: dict, min_index: int, max_index: int) -> list:
    """
    Create unsorted list of all lines in that direction with duplicates

    Args:
        result (dict): Result from table cell recognition
        min_index (int): Index into bbox coordinates
        max_index (list): Index into bbox coordinates

    Returns:
        List of all lines
    """
    lines: list = []

    for box in result["boxes"]:
        min_line: int = round(box["coordinate"][min_index])
        max_line: int = round(box["coordinate"][max_index])
        if min_line not in lines:
            lines.append(min_line)
        if max_line not in lines:
            lines.append(max_line)

    return lines


def clean_lines(lines: list) -> list:
    """
    Sort and remove duplicates

    Args:
        lines (list): List of lines

    Returns:
        List of all lines sorted and without duplicates
    """
    lines.sort()
    previous_line: int = -10
    result_lines: list = []

    for line in lines:
        # all lines close to each other (2 pixels) are ignored
        if line - previous_line > 2:
            result_lines.append(line)
        previous_line = line

    return result_lines


def calculate_indexes_position_span(min: int, max: int, lines: list) -> tuple[int, int, int, int]:
    """
    Calculate cell position and cell span in one direction

    Args:
        min (int): cell's min coordinate in one direction
        max (int): cell's max coordinate in one direction
        lines (list): List of all table lines in one direction

    Returns:
        Cell min line index
        Cell max line index
        Cell position in one direction
        Cell span in one direction
    """
    min_index = find_line_index(min, lines)
    max_index = find_line_index(max, lines)

    span = max_index - min_index
    position = min_index + 1
    return min_index, max_index, position, span


def calculate_position_and_span(min: int, max: int, lines: list) -> tuple[int, int]:
    """
    Calculate cell position and cell span in one direction

    Args:
        min (int): cell's min coordinate in one direction
        max (int): cell's max coordinate in one direction
        lines (list): List of all table lines in one direction

    Returns:
        Cell position in one direction
        Cell span in one direction
    """
    min_index = find_line_index(min, lines)
    max_index = find_line_index(max, lines)

    span = max_index - min_index
    position = min_index + 1
    return position, span


def find_line_index(target_line: int, lines: list) -> int:
    """
    Find index of closest line to target_line

    Args:
        target_line (int): Line that we want closest index
        lines (list): List of all lines

    Returns:
        Index of line in lines
    """
    return min(range(len(lines)), key=lambda i: abs(lines[i] - target_line))
