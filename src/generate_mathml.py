import json

from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfRect,
    PdsStructElement,
    kSaveFull,
)
from tqdm import tqdm

from ai import PaddleXEngine
from exceptions import PdfixException
from page_renderer import convert_base64_image_to_matlike_image, render_element_to_image
from utils_sdk import authorize_sdk, browse_tags_recursive, set_associated_file_math_ml


class GenerateMathmlFromImage:
    """
    Class that takes care of receiving base64 encoded image in JSON file and processing it through Paddle Engine
    and writing result into output JSON file.
    """

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize class for formula description.

        The input JSON file should have the following structure:
        {
            "image": "<header>,<base64_encoded_image>"
        }

        The output JSON file will look like:
        {
            "content": "MathML ver. 3 description of formula"
        }

        Args:
            input_path (str): Path to the input JSON file.
            output_path (str): Path to the output JSON file.
        """
        self.input_path_str = input_path
        self.output_path_str = output_path

    def process_image(self) -> None:
        """
        Processes a JSON file by extracting a base64-encoded image,
        generating a response using Paddle, and saving the result to an output file.

        The function performs the following steps:
        1. Reads the input JSON file.
        2. Extracts the base64-encoded image.
        3. Converts the image data
        4. Passes the image to paddle engine (that uses formula model)
        5. Converts response to MathML ver. 3
        6. Saves the MathMl representation as a dictionary {"content": representation} in the output JSON file.
        """
        with open(self.input_path_str, "r", encoding="utf-8") as input_file:
            data = json.load(input_file)

        image = convert_base64_image_to_matlike_image(data["image"])

        ai = PaddleXEngine()
        mathml_formula = ai.process_formula_image_with_ai(image)
        content: dict = {"content": mathml_formula}

        with open(self.output_path_str, "w", encoding="utf-8") as output_file:
            json.dump(content, output_file)


class GenerateMathmlsInPdf:
    """
    Class that takes care of adding associate file with MathML representation of formula to all formulas inside
    tagged PDF document using Paddle Model.
    """

    def __init__(
        self,
        license_name: str,
        license_key: str,
        input_path: str,
        output_path: str,
    ) -> None:
        """
        Initialize class for generating mathmls for formulas in pdf.

        Args:
            license_name (string): Pdfix sdk license name (e-mail)
            license_key (string): Pdfix sdk license key
            input_path (string): Path to PDF document
            output_path (string): Path where tagged PDF should be saved
        """
        self.license_name = license_name
        self.license_key = license_key
        self.input_path_str = input_path
        self.output_path_str = output_path

    def process_file(self) -> None:
        """
        Goes through PDF document and for each formula tries to set associate file with MathML.
        """
        pdfix = GetPdfix()
        if pdfix is None:
            raise Exception("Pdfix Initialization failed")

        # Try to authorize PDFix SDK
        authorize_sdk(pdfix, self.license_name, self.license_key)

        # Open the document
        doc = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise PdfixException(pdfix, "Unable to open PDF")

        ai = PaddleXEngine()

        # Get Root Tag element
        struct_tree = doc.GetStructTree()
        if struct_tree is None:
            raise PdfixException(pdfix, "PDF has no structure tree")

        child_element = struct_tree.GetStructElementFromObject(struct_tree.GetChildObject(0))

        # Find all formulas:
        items = browse_tags_recursive(child_element, "Formula")
        count = len(items)
        ai = PaddleXEngine()

        for index in tqdm(range(count)):
            element = items[index]
            self._process_element(pdfix, doc, element, ai)

        # Save document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise PdfixException(pdfix)

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
        element_object_id = element.GetObject().GetId()
        element_id = element.GetId()
        element_type = element.GetType(False)
        log_id = f"{element_type} [obj: {element_object_id}, id: {element_id}]"

        # Get page number
        page_number = element.GetPageNumber(0)
        if page_number == -1:
            for i in range(0, element.GetNumChildren()):
                page_number = element.GetChildPageNumber(i)
                if page_number != -1:
                    break

        if page_number == -1:
            print(f"Skipping [{log_id}] Formula tag as we can't determine the page number")
            return

        # Get bounding box
        bbox = PdfRect()
        for i in range(element.GetNumPages()):
            page_num = element.GetPageNumber(i)
            bbox = element.GetBBox(page_num)
            break

        if bbox.left == bbox.right or bbox.top == bbox.bottom:
            print(f"Skipping [{log_id}] Formula tag as we can't determine the bounding box")
            return

        # Create image
        image = render_element_to_image(pdfix, doc, page_num, bbox, 1)

        # Recognize formula
        mathml_formula = ai.process_formula_image_with_ai(image)

        print(f"Formula in [{log_id}]:\n    {mathml_formula}")

        # Set AF
        set_associated_file_math_ml(pdfix, element, mathml_formula, ai.MATH_ML_VERSION)
