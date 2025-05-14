import ctypes
import json
import os
from pathlib import Path

from pdfixsdk import (
    GetPdfix,
    Pdfix,
    PdfPage,
    PdfTagsParams,
    kDataFormatJson,
    kRotate0,
    kSaveFull,
)
from tqdm import tqdm

from ai import PaddleXEngine
from exceptions import (
    InvalidDirectoryException,
    PdfixAuthorizationException,
    PdfixAuthorizationFailedException,
    PdfixException,
    SameDirectoryException,
)
from page_renderer import create_image_from_pdf_page
from template_json import TemplateJsonCreator


class AutotagUsingPaddleXRecognition:
    def __init__(self, license_name: str, license_key: str, input_path: str, output_path: str, model: str) -> None:
        """
        Initialize class for tagging pdf(s).

        Args:
            license_name (string): Pdfix sdk license name (e-mail)
            license_key (string): Pdfix sdk license key
            input_path (string): Path to one pdf or folder
            output_path (string): Path where proccessed pdf(s) should be
                written, if input is 1 pdf output should be also 1 pdf,
                if input is folder output should also be folder
            model (string): Paddle model for layout recognition
        """
        self.license_name = license_name
        self.license_key = license_key
        self.input_path_str = input_path
        self.output_path_str = output_path
        self.model = model

    def process_folder(self) -> None:
        """
        Automatically goes through PDF documents in folder and tags them.
        """
        input_path = Path(self.input_path_str)
        output_path = Path(self.output_path_str)

        if self.input_path_str == self.output_path_str:
            raise SameDirectoryException()

        if not input_path.is_dir():
            raise InvalidDirectoryException(self.input_path_str)

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

        # Try to authorize so results don't contain watermarks
        self._authorize(pdfix)

        # Open the document
        doc = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        # Process images of each page
        num_pages = doc.GetNumPages()
        template_json_creator = TemplateJsonCreator()
        max_formulas_and_tables_per_page = 1000
        progress_bar = tqdm(total=num_pages * max_formulas_and_tables_per_page, desc="Processing pages")

        for page_index in range(0, num_pages):
            # Acquire the page
            page = doc.AcquirePage(page_index)
            if page is None:
                raise PdfixException("Unable to acquire the page")

            # Process the page
            self._process_pdf_file_page(
                id, page, page_index, template_json_creator, progress_bar, max_formulas_and_tables_per_page
            )

            # Clean-up
            page.Release()

        # Create template json for whole document
        template_json_dict: dict = template_json_creator.create_json_dict_for_document(self.model)

        # Save template json to fileoutput_name = f"{id}-page{page_number}.png"
        template_path = os.path.join(Path(__file__).parent.absolute(), f"../output/{id}-template_json.json")
        with open(template_path, "w") as file:
            file.write(json.dumps(template_json_dict, indent=2))

        # Remove old structure and prepare an empty structure tree
        doc.RemoveTags()
        doc.RemoveStructTree()

        # Convert template json to memory stream
        memory_stream = GetPdfix().CreateMemStream()
        raw_data, raw_data_size = self._json_to_raw_data(template_json_dict)
        if not memory_stream.Write(0, raw_data, raw_data_size):
            raise Exception(GetPdfix().GetError())

        doc_template = doc.GetTemplate()
        if not doc_template.LoadFromStream(memory_stream, kDataFormatJson):
            raise Exception(f"Unable to open pdf : {pdfix.GetError()}")

        memory_stream.Destroy()

        # Autotag document
        tagsParams = PdfTagsParams()
        if not doc.AddTags(tagsParams):
            raise Exception(pdfix.GetError())

        # Save the processed document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    def _json_to_raw_data(self, json_dict: dict) -> tuple[ctypes.Array[ctypes.c_ubyte], int]:
        """
        Converts a JSON dictionary into a raw byte array (c_ubyte array) that can be used for low-level data operations.

        Parameters:
            json_dict (dict): A Python dictionary to be converted into JSON format and then into raw bytes.

        Returns:
            tuple: A tuple containing:
                - json_data_raw (ctypes.c_ubyte array): The raw byte array representation of the JSON data.
                - json_data_size (int): The size of the JSON data in bytes.
        """
        json_str: str = json.dumps(json_dict)
        json_data: bytearray = bytearray(json_str.encode("utf-8"))
        json_data_size: int = len(json_str)
        json_data_raw: ctypes.Array[ctypes.c_ubyte] = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
        return json_data_raw, json_data_size

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

    def _process_pdf_file_page(
        self,
        id: str,
        page: PdfPage,
        page_index: int,
        templateJsonCreator: TemplateJsonCreator,
        progress_bar: tqdm,
        max_formulas_and_tables_per_page: int,
    ) -> None:
        """
        Create template json for current PDF document page.

        Args:
            id (string): PDF document name.
            page (PdfPage): The PDF document page to process.
            page_index (int): PDF file page index.
            progress_bar (tqdm): Progress bar that we update for each model
                call.
            max_formulas_and_tables_per_page (int): Our estimation how many
                tables and formulas can be in one page.
        """
        page_number = page_index + 1

        # Define zoom level and rotation for rendering the page
        zoom = 1.0
        rotate = kRotate0
        page_view = page.AcquirePageView(zoom, rotate)

        # Render the page as an image
        image = create_image_from_pdf_page(page, page_view)

        # Run layout model analysis and formula and table model analysis using the PaddleX engine
        paddlex = PaddleXEngine(self.model)
        results = paddlex.process_pdf_page_image_with_ai(
            image, id, page_number, progress_bar, max_formulas_and_tables_per_page
        )

        # Create template json from PaddleX results for this page
        templateJsonCreator.process_page(results, page_number, page_view)

        # Release resources
        page_view.Release()
