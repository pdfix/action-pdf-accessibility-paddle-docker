from typing import Optional

import cv2
from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfRect,
    PdfStructElemEnumProcType,
    PdsObject,
    PdsStructElement,
    PdsStructTree,
    kEnumNone,
    kEnumResultContinue,
    kPdsStructChildElement,
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
from utils_sdk import authorize_sdk, set_associated_file_math_ml


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
        with tqdm(total=100) as progress_bar:
            progress_bar.set_description("Processing")

            image: cv2.typing.MatLike = cv2.imread(self.input_path_str)

            ai: PaddleXEngine = PaddleXEngine()
            mathml_formula: str = ai.process_formula_image_with_ai(image)

            with open(self.output_path_str, "w", encoding="utf-8") as output_file:
                output_file.write(mathml_formula)

            progress_bar.n = 100
            progress_bar.set_description("Done")
            progress_bar.refresh()


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
            license_key (Optional[str]): Pdfix sdk license key
            input_path (str): Path to PDF document
            output_path (str): Path where tagged PDF should be saved
        """
        self.license_name: Optional[str] = license_name
        self.license_key: Optional[str] = license_key
        self.input_path_str: str = input_path
        self.output_path_str: str = output_path

        self.pdfix: Optional[Pdfix] = None
        self.doc: Optional[PdfDoc] = None
        self.struct_tree: Optional[PdsStructTree] = None
        self.ai: Optional[PaddleXEngine] = None

    def process_file(self) -> None:
        """
        Goes through PDF document and for each formula tries to set associate file with MathML.
        """
        with tqdm(total=100) as progress_bar:
            progress_bar.set_description("Initializing")

            self.pdfix = GetPdfix()
            if self.pdfix is None:
                raise PdfixInitializeException()

            # Try to authorize PDFix SDK
            authorize_sdk(self.pdfix, self.license_name, self.license_key)

            # Open the document
            self.doc = self.pdfix.OpenDoc(self.input_path_str, "")
            if self.doc is None:
                raise PdfixFailedToOpenException(self.pdfix, self.input_path_str)

            self.ai = PaddleXEngine()

            # Enumerate struct tree
            self.struct_tree = self.doc.GetStructTree()
            if self.struct_tree is None:
                raise PdfixNoTagsException(self.pdfix, "PDF has no structure tree")

            progress_bar.update(10)
            progress_bar.set_description("Processing elements")

            # Keep a local reference so the ctypes callback is not GC'd during enumeration.
            enum_proc = PdfStructElemEnumProcType(self.enumerate_struct_tree)
            try:
                self.doc.EnumStructTree(None, kEnumNone, enum_proc, None)
            except Exception:
                raise
            finally:
                self.struct_tree = None

            progress_bar.n = 95
            progress_bar.set_description("Saving document")
            progress_bar.refresh()

            # Save document
            if not self.doc.Save(self.output_path_str, kSaveFull):
                raise PdfixFailedToSaveException(self.pdfix, self.output_path_str)

            progress_bar.n = 100
            progress_bar.set_description("Done")
            progress_bar.refresh()

    def enumerate_struct_tree(self, document_pointer: int, parent_pointer: int, index: int, client_data: int) -> int:
        """
        Callback invoked for each struct element during struct tree enumeration.

        Args:
            document_pointer (int): Document pointer passed by PDFix SDK (unused).
            parent_pointer (int): Parent struct element pointer, or 0 for the root.
            index (int): Child index under the parent.
            client_data (int): Client data pointer passed by PDFix SDK (unused).

        Returns:
            Enumeration result code; always continues to the next element.
        """
        struct_element: Optional[PdsStructElement] = self.resolve_struct_element(
            self.struct_tree, parent_pointer, index
        )
        if struct_element is None:
            return kEnumResultContinue

        if struct_element.GetType(False) == "Formula":
            self._process_element(struct_element)

        return kEnumResultContinue

    def resolve_struct_element(
        self, struct_tree: Optional[PdsStructTree], parent_pointer: int, index: int
    ) -> Optional[PdsStructElement]:
        """
        Resolve a struct element from enumeration parent pointer and child index.

        Args:
            struct_tree (Optional[PdsStructTree]): Document struct tree.
            parent_pointer (int): Parent struct element pointer, or 0 for the root.
            index (int): Child index under the parent.

        Returns:
            Resolved struct element, or None if the child is not a struct element.
        """
        if struct_tree is None:
            return None

        parent: PdsStructElement
        if parent_pointer:
            parent = PdsStructElement(parent_pointer)
        else:
            root_object: Optional[PdsObject] = struct_tree.GetObject()
            if root_object is None:
                return None
            root_element: Optional[PdsStructElement] = struct_tree.GetStructElementFromObject(root_object)
            if root_element is None:
                return None
            parent = root_element

        if parent.GetChildType(index) != kPdsStructChildElement:
            return None

        child_object: Optional[PdsObject] = parent.GetChildObject(index)
        if child_object is None:
            return None

        return struct_tree.GetStructElementFromObject(child_object)

    def _process_element(self, element: PdsStructElement) -> None:
        """
        For given element, tries to get page number and bounding box. If successfull creates image of element and
        sents it to Paddle Formula Model and transforms answer to MathMl ver.3. Then sets it to element as associate
        file (AF).

        Args:
            element (PdsStructElement): Formula element.
        """
        if self.pdfix is None or self.doc is None or self.ai is None:
            return

        # For logging purposes
        element_object: Optional[PdsObject] = element.GetObject()
        if element_object is None:
            return
        element_object_id: int = element_object.GetId()
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
        page_num: int = page_number
        for i in range(element.GetNumPages()):
            page_num = element.GetPageNumber(i)
            bbox = element.GetBBox(page_num)
            break

        if bbox.left == bbox.right or bbox.top == bbox.bottom:
            print(f"Skipping [{log_id}] Formula tag as we can't determine the bounding box")
            return

        # Create image
        image: cv2.typing.MatLike = render_element_to_image(self.pdfix, self.doc, page_num, bbox, 1)

        # Recognize formula
        mathml_formula: str = self.ai.process_formula_image_with_ai(image)

        # Set AF
        set_associated_file_math_ml(self.pdfix, element, mathml_formula, MATH_ML_VERSION)
