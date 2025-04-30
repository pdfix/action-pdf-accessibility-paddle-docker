import cv2
import json
from pathlib import Path
from pdfixsdk import (
    PdeCell,
    PdeElement,
    PdePageMap,
    PdeTable,
    PdfDevRect,
    Pdfix,
    PdfPage,
    PdfTagsParams,
    PdfPageView,
    PdsStructElement,
    GetPdfix,
    kPdeCell,
    kPdeImage,
    kPdeList,
    kPdeTable,
    kPdeText,
    kRotate0,
    kSaveFull,
)
from tqdm import tqdm

from ai import process_image_with_ai
from exceptions import (
    PdfixAuthorizationException,
    PdfixAuthorizationFailedException,
    PdfixException,
    SameDirectoryException,
    UnvalidDirectoryException,
)
from page_renderer import create_image_from_pdf_page
from template_json import create_json_from_results
from visualize_results import fill_image_with_recognized_places


class AutotagByPaddle:
    def __init__(self,
                 license_name: str,
                 license_key: str,
                 input_path: str,
                 output_path: str) -> None:
        """
        Initialize class for tagging pdf(s).

        Args:
            license_name (string): Pdfix sdk license name (e-mail)
            license_key (string): Pdfix sdk license key
            input_path (string): Path to one pdf or folder.
            output_path (string): Path where proccessed pdf(s) should be
                written, if input is 1 pdf output should be also 1 pdf ...
        """
        self.license_name = license_name
        self.license_key = license_key
        self.input_path_str = input_path
        self.output_path_str = output_path

    def process_folder(self) -> None:
        """
        Automatically goes through PDF documents in folder and tags them.
        """
        input_path = Path(self.input_path_str)
        output_path = Path(self.output_path_str)

        if self.input_path_str == self.output_path_str:
            raise SameDirectoryException()

        if not input_path.is_dir():
            raise UnvalidDirectoryException(self.input_path_str)

        output_path.mkdir(parents=True, exist_ok=True)

        for pdf_file in input_path.glob("*.pdf"):
            output_file = Path.joinpath(output_path, pdf_file.name)
            self.input_path_str = str(pdf_file)
            self.output_path_str = str(output_file)
            self.process_file()

    def process_file(self) -> None:
        """
        Automatically tags a PDF document.
        """
        id: str = Path(self.input_path_str).stem

        pdfix = GetPdfix()
        if pdfix is None:
            raise Exception("Pdfix Initialization failed")

        self._authorize(pdfix)

        # Open the document
        doc = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        # Remove old structure and prepare an empty structure tree
        doc.RemoveTags()
        doc.RemoveStructTree()
        struct_tree = doc.CreateStructTree()
        doc_struct_elem = \
            struct_tree.GetStructElementFromObject(struct_tree.GetObject())
        if doc_struct_elem is None:
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        num_pages = doc.GetNumPages()

        # Process each page
        for page_number in tqdm(range(0, num_pages), desc="Processing pages"):
            # Acquire the page
            page = doc.AcquirePage(page_number)
            if page is None:
                raise PdfixException("Unable to acquire the page")
            self._process_pdf_file_page(pdfix, id, page, doc_struct_elem)
            page.Release()

        # Save the processed document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    def _authorize(self, pdfix: Pdfix) -> None:
        """
        Tries to authorize license information in pdfix sdk.

        Args:
            pdfix (Pdfix): Pdfix sdk instance.
        """
        if self.license_name is None and self.license_key:
            raise PdfixAuthorizationException("License key was not provided")

        if self.license_name and self.license_key is None:
            raise PdfixAuthorizationException("License name was not provided")

        if self.license_name and self.license_key:
            authorization = pdfix.GetAccountAuthorization()
            if not authorization.Authorize(self.license_name, self.license_key):
                raise PdfixAuthorizationFailedException()

    def _process_pdf_file_page(self,
                               pdfix: Pdfix,
                               id: str,
                               page: PdfPage,
                               doc_struct_elem: PdsStructElement) -> None:
        """
        Automatically tag one PDF document page.

        Args:
            pdfix (Pdfix): Pdfix sdk instance.
            id (string): PDF document name.
            page (PdfPage): The PDF document page to process.
            doc_struct_elem (PdsStructElement): The root structure element where
                tags will be added.
        """
        # Define zoom level and rotation for rendering the page
        zoom = 1.0
        rotate = kRotate0
        page_view = page.AcquirePageView(zoom, rotate)

        # Render the page as an image
        image = create_image_from_pdf_page(page, page_view)

        # Run layout analysis using the Paddle engine
        results = process_image_with_ai(image)

        # Process some data from paddle into more usable structures
        results = self._process_paddle_data(results)

        # For debugging purposes uncomment next line
        # self._debug_paddle_output(zoom, id, page, results, image)

        # Write recognised tags with as much information as possible
        # into PDF structure data.
        self._write_found_elements_directy_into_structure(page, page_view,
            results, pdfix, doc_struct_elem)

        # Release resources
        page_view.Release()

    def _process_paddle_data(self, results: list) -> list:
        """
        Parse paddle data for lists and tables into more usable structures and
        return them in new structure alongside with original data.

        Args:
            results (list): Paddle results.

        Returns:
            The same list as paddle with "custom" key for tables and lists.
        """
        enhanced_results: list = []
        for result in results:
            enhanced_result = result
            match result["type"].lower():
                case "list":
                    # Process list data into more usable structure
                    enhanced_result["custom"] = \
                        self._process_list_result_into_usable_structure(result)
                case "table":
                    # Process table data into more usable structure
                    enhanced_result["custom"] = \
                        self._process_table_result_into_usable_structure(result)
            enhanced_results.append(enhanced_result)
        return enhanced_results

    def _process_list_result_into_usable_structure(self,
                                                   list_result: dict) -> list:
        """
        Calculating bboxes for texts inside list.

        Args:
            list_result (dict): Result returned by paddle for list recognition.
                It contains list of texts where each text contains "text"
                recognised text, "confidence" score for recognition and
                "text_region" list of 4 points

        Returns:
            List of bboxes created from those 4 points.
        """
        def calculate_bbox(points: list) -> list:
            min_x: float = points[0][0]
            max_x: float = points[0][0]
            min_y: float = points[0][1]
            max_y: float = points[0][1]
            for point in points:
                x: float = point[0]
                y: float = point[1]
                min_x = min_x if min_x <= x else x
                max_x = max_x if max_x >= x else x
                min_y = min_y if min_y <= y else y
                max_y = max_y if max_y >= y else y
            return [min_x, min_y, max_x, max_y]

        bboxes: list = []
        for text in list_result["res"]:
            bbox = calculate_bbox(text["text_region"])
            bboxes.append(bbox)
        return bboxes

    def _process_table_result_into_usable_structure(self,
                                                    table_result: dict) -> list:
        """
        Parsing paddle output specific html. There are no <th> and there are
        multiple assumptions. This is not generic way to parse html page
        with table.

        Args:
            table_result (dict): Result returned by paddle for table
                recognition. It contains "cell_bbox" (list of bboxes) and "html"
                (html representation of what paddle recognised)

        Returns:
            List of cells where each cell contains data about row, column,
            is_header, text and bboxes inside table and page.
        """
        html_content: str = table_result["res"]["html"]
        bboxes: list = table_result["res"]["cell_bbox"]
        table_bbox: list = table_result["bbox"]
        content: str = html_content.replace("<html><body><table>",
            "").replace("</table></body></html>", "")
        sections: list = content.split("</thead>")
        thead: str = sections[0].replace("<thead>", "")
        bodies: str = sections[1]

        def parse_section(data: str,
                          is_header: bool,
                          row_number: int,
                          table_bbox: list,
                          bboxes: list,
                          index: int) -> tuple[list, int, int]:
            output: list = []
            for row in data.split("</tr>"):
                if row == "":
                    continue
                row_number += 1
                row_data: str = row.replace("<tr>", "").replace("</tr>", "")
                column_number: int = 0
                for column in row_data.split("</td>"):
                    if column == "":
                        continue
                    column_number += 1
                    text: str = column.replace("<td>", "").replace("</td>", "")
                    bbox_inside_table: list = bboxes[index]
                    bbox_inside_page: list = [
                        table_bbox[0] + bbox_inside_table[0],
                        table_bbox[1] + bbox_inside_table[1],
                        table_bbox[0] + bbox_inside_table[2],
                        table_bbox[1] + bbox_inside_table[3]
                    ]
                    cell = {
                        "row": row_number,
                        "column": column_number,
                        "is_header": is_header,
                        "text": text,
                        "bbox": bbox_inside_table,
                        "page_bbox": bbox_inside_page
                    }
                    index += 1
                    output.append(cell)
            return output, row_number, index

        bboxes_index: int = 0
        row_number: int = 0
        cell_results: list = []
        header_results, row_number, bboxes_index = parse_section(thead, True,
            row_number, table_bbox, bboxes, bboxes_index)
        cell_results += header_results

        for body in bodies.split("</tbody>"):
            if body == "":
                continue
            body_data: str = body.replace("<tbody>", "").replace("</tbody>", "")
            body_results, row_number, bboxes_index = parse_section(body_data,
                False, row_number, table_bbox, bboxes, bboxes_index)
            cell_results += body_results

        return cell_results

    def _debug_paddle_output(self,
                             zoom: float,
                             id: str,
                             page: PdfPage,
                             results: list,
                             image: cv2.typing.MatLike) -> None:
        """
        Function just for easier debuggingof PaddleOCR results.

        Prints raw results with processed enhancements into console.

        Creates images of each PDF page with recognised regions (green), list
        texts (red), empty table cells (dark blue), table cells with text
        (cyan). This is saved into
        "images-{zoom}/{id}_{page.GetNumber()+1}.jpg". For easier access to this
        folder mount it during docker run:
        "docker run -v path_to_images:/usr/paddle-ocr/images-1.0 ..." as zoom
        current is "1.0".

        WIP creates PDFix template-like json structure with found regions.

        Args:
            zoom (float): Zoom level of rendering PDF page.
            id (string): PDF document name.
            page (PdfPage): The PDF document page to process.
            results (list): Enhanced Paddle results.
            image (cv2.typing.MatLike): Rendered image of PDF page.
        """
        # Console debug of results
        print("************** START ***************")
        for result in results:
            expected_results = 5
            # result['img'] is too big in output so not using:
            # print(result)
            # instead printing rest of values per each line:
            print(f"type: {result['type']}")
            print(f"bbox: {result['bbox']}")
            # as table recognition can be turned off make sure not to try
            # print not existing dictionary value
            if "res" in result:
                expected_results += 1
                print(f"res: {result['res']}")
                if len(result['res']) == 0:
                    # sometimes Paddle returns text region without any text:
                    print("!!!!!!!!!!! WARNING NOTHING IN RESULT !!!!!!!!!!!!")
            print(f"img_idx: {result['img_idx']}")
            print(f"score: {result['score']}")
            if "custom" in result:
                expected_results += 1
                print(f"custom: {result['custom']}")
            if len(result) > expected_results:
                output_message = "!!!!!!!!!!!!!!! WARNING MORE INFO IN RESULT"
                output_message += f" (FOUND: {len(result)},"
                output_message += f" EXPECTED: {expected_results})"
                output_message += " !!!!!!!!!!!!!!!"
                print(output_message)
            print("---------- NEXT SOMETIMES ----------------")
        print("************** END ***************")

        # Visual debug of results
        fill_image_with_recognized_places(zoom, id, page, results, image)

        # Json from results
        elems = create_json_from_results(results)
        print(json.dumps(elems))
        #print(json.dumps(elems, indent=2))

    def _write_found_elements_directy_into_structure(self,
            page: PdfPage,
            page_view: PdfPageView,
            results: list,
            pdfix: Pdfix,
            doc_struct_elem: PdsStructElement) -> None:
        """
        Tries to tag elements into PDF structure for given page.

        Args:
            page (PdfPage): The PDF document page to process.
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.
            results (list): Paddle results enhanced with some custom processed
                data.
            pdfix (Pdfix): PDFix sdk instance.
            doc_struct_elem (PdsStructElement): The root structure element where
                tags will be added.
        """
        # Acquire the page map to store recognized elements
        page_map = page.AcquirePageMap()

        # Add detected elements to the page map based on the analysis results
        self._add_found_elements(page_map, page_view, results)

        # Generate structured elements from the page map
        if not page_map.CreateElements():
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        # Create a new structural element for the page
        page_element = doc_struct_elem.AddNewChild("NonStruct",
            doc_struct_elem.GetNumChildren())

        # Assign recognized elements as tags to the structure element
        if not page_map.AddTags(page_element, False, PdfTagsParams()):
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        # Release resources
        page_map.Release()

    def _add_found_elements(self,
                            page_map: PdePageMap,
                            page_view: PdfPageView,
                            results: list) -> None:
        """
        Adds initial structural elements to the page map based
        on detected results.

        Args:
            page_map (PdePageMap): The page map where elements will be added.
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.
            results (list): A list of all detected regions (Paddle results),
                each containing bounding box, type, ...
        """
        for result in results:
            rect = PdfDevRect()
            rect.left = int(result["bbox"][0])
            rect.top = int(result["bbox"][1])
            rect.right = int(result["bbox"][2])
            rect.bottom = int(result["bbox"][3])
            bbox = page_view.RectToPage(rect)

            # Determine element type
            region_type = result["type"].lower()
            element_type = kPdeText  # Default to text
            match region_type:
                case "table":
                    element_type = kPdeTable
                case "figure":
                    element_type = kPdeImage
                case "list":
                    element_type = kPdeList
                case "text":
                    element_type = kPdeText
                case "title":
                    element_type = kPdeText
                case _:
                    element_type = kPdeText

            element = page_map.CreateElement(element_type, None)
            element.SetBBox(bbox)

            match region_type:
                case "list":
                    self._add_list_data(element, result["custom"], page_view)
                    pass
                case "title":
                    # TODO SDK API missing
                    # element.SetTextStyle(kTextH1)
                    pass
                case "table":
                    self._add_table_data(element, result["custom"], page_view)

    def _add_list_data(self,
                        pdf_element: PdeElement,
                        list_result: list,
                        page_view: PdfPageView) -> None:
        """
        Updates the list element with detected bullet sections. For this
        PaddleOCR it is just all lines.

        Args:
            pdf_element (PdeElement): The table element to edit.
            list_result (list): List of texts with all available data.
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.
        """
        """TODO"""
        pass

    def _add_table_data(self,
                        pdf_element: PdeElement,
                        table_result: list,
                        page_view: PdfPageView) -> None:
        """
        Updates the table element with detected cells

        Args:
            pdf_element (PdeElement): The table element to edit.
            table_result (list): List of cells with all available data.
            page_view (PdfPageView): The view of the PDF page used
                for coordinate conversion.
        """
        # Get the page map and create the table object
        page_map = pdf_element.GetPageMap()
        table = PdeTable(pdf_element.obj)

        max_row = 0
        max_column = 0

        for cell in table_result:
            cell_rect = PdfDevRect()
            cell_rect.left = int(cell["page_bbox"][0]) - 2
            cell_rect.top = int(cell["page_bbox"][1]) - 2
            cell_rect.right = int(cell["page_bbox"][2]) + 2
            cell_rect.bottom = int(cell["page_bbox"][3]) + 2

            # Convert cell rectangle to page coordinates
            cell_bbox = page_view.RectToPage(cell_rect)

            # Create a new cell element and set its properties
            cell = PdeCell(page_map.CreateElement(kPdeCell, table).obj)
            row = cell["row"]
            column = cell["column"]
            cell.SetColNum(column)
            cell.SetRowNum(row)
            cell.SetBBox(cell_bbox)
            cell.SetHeader(cell["is_header"])
            cell.SetColSpan(1)
            cell.SetRowSpan(1)

            # update max values
            max_row = max_row if max_row >= row else row
            max_column = max_column if max_column >= column else column

        # Set the number of columns and rows in the table based
        # on the last values of column and row
        table.SetNumCols(max_column) # TODO check if +1 needed?
        table.SetNumRows(max_row) # TODO check if +1 needed?
