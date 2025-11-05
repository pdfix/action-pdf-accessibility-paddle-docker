from typing import Optional

import cv2
from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfRect,
    PdsObject,
    PdsStructElement,
    PdsStructTree,
    kSaveFull,
)
from tqdm import tqdm

from ai import PaddleXEngine
from constants import MATH_ML_VERSION
from exceptions import (
    PdfixFailedToOpenException,
    PdfixFailedToSaveException,
    PdfixInitializeException,
    PdfixNoTagsException,
)
from page_renderer import render_element_to_image
from utils_sdk import authorize_sdk, browse_tags_recursive, set_associated_file_math_ml


class GenerateMathmlFromImage:
    """
    Class that takes care of receiving base64 encoded image in JSON file and processing it through Paddle Engine
    and writing result into output JSON file.
    """

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize class for formula description.

        Args:
            input_path (str): Path to the image (JPG) file.
            output_path (str): Path to the mathml (XML) file.
        """
        self.input_path_str: str = input_path
        self.output_path_str: str = output_path

    def process_image(self) -> None:
        """
        Uses formula image file to generate LaTeX representation using Paddle, and converts it to MathML ver. 3 which
        is saved to XML  output file.

        The function performs the following steps:
        1. Reads the input image file.
        2. Passes the image to paddle engine (that uses formula model)
        3. Converts response to MathML ver. 3
        4. Saves the MathMl in the output XML file.
        """
        image: cv2.typing.MatLike = cv2.imread(self.input_path_str)

        ai: PaddleXEngine = PaddleXEngine()
        mathml_formula: str = ai.process_formula_image_with_ai(image)

        with open(self.output_path_str, "w", encoding="utf-8") as output_file:
            output_file.write(mathml_formula)


class GenerateMathmlInPdf:
    """
    Class that takes care of adding associate file with MathML representation of formula to all formulas inside
    tagged PDF document using Paddle Model.
    """

    def __init__(
        self,
        license_name: Optional[str],
        license_key: Optional[str],
        input_path: str,
        output_path: str,
    ) -> None:
        """
        Initialize class for generating mathmls for formulas in pdf.

        Args:
            license_name (Optional[str]): Pdfix sdk license name (e-mail)
            license_key (striOptional[str]ng): Pdfix sdk license key
            input_path (str): Path to PDF document
            output_path (str): Path where tagged PDF should be saved
        """
        self.license_name: Optional[str] = license_name
        self.license_key: Optional[str] = license_key
        self.input_path_str: str = input_path
        self.output_path_str: str = output_path

    def process_file(self) -> None:
        """
        Goes through PDF document and for each formula tries to set associate file with MathML.
        """
        pdfix: Optional[Pdfix] = GetPdfix()
        if pdfix is None:
            raise PdfixInitializeException()

        # Try to authorize PDFix SDK
        authorize_sdk(pdfix, self.license_name, self.license_key)

        # Open the document
        doc: Optional[PdfDoc] = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise PdfixFailedToOpenException(pdfix, self.input_path_str)

        ai: PaddleXEngine = PaddleXEngine()

        # Get Root Tag element
        struct_tree: Optional[PdsStructTree] = doc.GetStructTree()
        if struct_tree is None:
            raise PdfixNoTagsException(pdfix, "PDF has no structure tree")

        child_object: Optional[PdsObject] = struct_tree.GetChildObject(0)
        if child_object is None:
            raise PdfixNoTagsException(pdfix, "PDF has no child objects in structure tree")
        child_element: Optional[PdsStructElement] = struct_tree.GetStructElementFromObject(child_object)
        if child_element is None:
            raise PdfixNoTagsException(pdfix, "PDF has no elements in structure tree")

        # Find all formulas:
        items: list[PdsStructElement] = browse_tags_recursive(child_element, "Formula")
        count: int = len(items)

        for index in tqdm(range(count)):
            element: PdsStructElement = items[index]
            self._process_element(pdfix, doc, element, ai)

        # Save document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise PdfixFailedToSaveException(pdfix, self.output_path_str)

    def _process_element(self, pdfix: Pdfix, doc: PdfDoc, element: PdsStructElement, ai: PaddleXEngine) -> None:
        """
        For given element, tries to get page number and bounding box. If successfull creates image of element and
        sents it to Paddle Formula Model and transforms answer to MathMl ver.3. Then sets it to element as associate
        file (AF).

        Args:
            pdfix (Pdfix): Pdfix SDK.
            doc (PdfDoc): PDF document.
            element (PdsStructElement): Formula element.
            ai (PaddleXEngine): Contains ai models and how to run them.
        """
        # For logging purposes
        element_object_id: int = element.GetObject().GetId()
        element_id: str = element.GetId()
        element_type: str = element.GetType(False)
        log_id: str = f"{element_type} [obj: {element_object_id}, id: {element_id}]"

        # Get page number
        page_number: int = element.GetPageNumber(0)
        if page_number == -1:
            for i in range(0, element.GetNumChildren()):
                page_number = element.GetChildPageNumber(i)
                if page_number != -1:
                    break

        if page_number == -1:
            print(f"Skipping [{log_id}] Formula tag as we can't determine the page number")
            return

        # Get bounding box
        bbox: PdfRect = PdfRect()
        for i in range(element.GetNumPages()):
            page_num: int = element.GetPageNumber(i)
            bbox = element.GetBBox(page_num)
            break

        if bbox.left == bbox.right or bbox.top == bbox.bottom:
            print(f"Skipping [{log_id}] Formula tag as we can't determine the bounding box")
            return

        # Create image
        image: cv2.typing.MatLike = render_element_to_image(pdfix, doc, page_num, bbox, 1)

        # Recognize formula
        mathml_formula: str = ai.process_formula_image_with_ai(image)

        # Set AF
        set_associated_file_math_ml(pdfix, element, mathml_formula, MATH_ML_VERSION)
