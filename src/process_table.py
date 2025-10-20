class PaddleXPostProcessingTable:
    """
    Class that take PaddleX results for cell recognition and creates each cell with information:
    - row number
    - row span
    - column number
    - column span
    - bounding box that has same border lines as rest of cells in the same row and column
    """

    def create_custom_result_from_paddlex_cell_result(self, cell_results: dict, coordinate: list) -> dict:
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

        row_lines, column_lines = self._create_table_row_and_column_lines(cell_results)

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

            row_min_index, row_max_index, row_number, row_span = self._calculate_indexes_position_span(
                int(min_y), int(max_y), row_lines
            )
            column_min_index, column_max_index, column_number, column_span = self._calculate_indexes_position_span(
                int(min_x), int(max_x), column_lines
            )

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

        # fill empty cells and sort cells by ascending coordinates: Y (row) and X (column)
        cells_with_data = self._fill_missing_cells_and_sort(cells_with_data, number_rows, number_columns)

        return {
            "rows": number_rows,
            "columns": number_columns,
            "cells": cells_with_data,
        }

    def _fill_missing_cells_and_sort(self, cells: list, number_rows: int, number_columns: int) -> list:
        """
        Fill missing cells in table and sort them by row and column

        Args:
            cells (list): List of cells with data
            number_rows (int): Rows count in table
            number_columns (int): Columns count in table

        Returns:
            List of cells with data sorted by row and column
        """
        if not cells:
            return []

        # Create grid with empty spans
        output_cells: list = []

        for row in range(1, number_rows + 1):
            row_cells: list = []
            for column in range(1, number_columns + 1):
                row_cell: dict = {
                    "row": row,
                    "column": column,
                    "row_span": 0,
                    "column_span": 0,
                }
                row_cells.append(row_cell)
            output_cells.append(row_cells)

        # Fill the grid with existing cells
        for cell in cells:
            row_index = cell["row"] - 1
            column_index = cell["column"] - 1
            output_cells[row_index][column_index] = cell

        # Convert grid to flat list (with bonus already being sorted)
        return [cell for row in output_cells for cell in row]

    def _create_table_row_and_column_lines(self, result: dict) -> tuple[list, list]:
        """
        From results of table cell recognition create all table lines

        Args:
            result (dict): Result from table cell recognition

        Returns:
            Table row lines
            Table column lines
        """
        row_lines: list = self._create_lines(result, 1, 3)
        column_lines: list = self._create_lines(result, 0, 2)
        row_lines = self._clean_lines(row_lines)
        column_lines = self._clean_lines(column_lines)

        return row_lines, column_lines

    def _create_lines(self, result: dict, min_index: int, max_index: int) -> list:
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

    def _clean_lines(self, lines: list) -> list:
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

    def _calculate_indexes_position_span(self, min: int, max: int, lines: list) -> tuple[int, int, int, int]:
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
        min_index: int = self._find_line_index(min, lines)
        max_index: int = self._find_line_index(max, lines)

        span: int = max_index - min_index
        position: int = min_index + 1
        return min_index, max_index, position, span

    def _find_line_index(self, target_line: int, lines: list) -> int:
        """
        Find index of closest line to target_line

        Args:
            target_line (int): Line that we want closest index
            lines (list): List of all lines

        Returns:
            Index of line in lines
        """
        return min(range(len(lines)), key=lambda i: abs(lines[i] - target_line))
