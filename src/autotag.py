import json
import os
from pathlib import Path

from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfPage,
    PdfTagsParams,
    kDataFormatJson,
    kRotate0,
    kSaveFull,
)
from tqdm import tqdm

from ai import PaddleXEngine
from exceptions import PdfixException
from page_renderer import create_image_from_pdf_page
from template_json import TemplateJsonCreator
from utils_sdk import authorize_sdk, browse_tags_recursive, json_to_raw_data, set_associated_file_math_ml


class AutotagUsingPaddleXRecognition:
    """
    Class that takes care of Autotagging provided PDF document using Paddle Engine.
    """

    def __init__(
        self,
        license_name: str,
        license_key: str,
        input_path: str,
        output_path: str,
        model: str,
        zoom: float,
        process_formula: bool,
        process_table: bool,
        thresholds: dict,
    ) -> None:
        """
        Initialize class for tagging pdf.

        Args:
            license_name (string): Pdfix sdk license name (e-mail).
            license_key (string): Pdfix sdk license key.
            input_path (string): Path to PDF document.
            output_path (string): Path where tagged PDF should be saved.
            model (string): Paddle model for layout recognition.
            zoom (float): Zoom level for rendering the page.
            process_formula (bool): Whether to process formulas.
            process_table (bool): Whether to process tables.
            thresholds (dict): Thresholds for layout detection.
        """
        self.license_name = license_name
        self.license_key = license_key
        self.input_path_str = input_path
        self.output_path_str = output_path
        self.model = model
        self.zoom = zoom
        self.process_formula = process_formula
        self.process_table = process_table
        self.thresholds = thresholds

    def process_file(self) -> None:
        """
        Automatically tags a PDF document.
        """
        id: str = Path(self.input_path_str).stem

        pdfix = GetPdfix()
        if pdfix is None:
            raise Exception("Pdfix Initialization failed")

        # Try to authorize PDFix SDK
        authorize_sdk(pdfix, self.license_name, self.license_key)

        # Open the document
        doc = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise PdfixException(pdfix, "Unable to open PDF")

        # Process images of each page
        num_pages = doc.GetNumPages()
        paddlex = PaddleXEngine(self.model, self.process_formula, self.process_table, self.thresholds)
        template_json_creator = TemplateJsonCreator()
        max_formulas_and_tables_per_page = 1000
        progress_bar = tqdm(total=num_pages * max_formulas_and_tables_per_page, desc="Processing pages")

        for page_index in range(0, num_pages):
            # Acquire the page
            page = doc.AcquirePage(page_index)
            if page is None:
                raise PdfixException(pdfix, "Unable to acquire the page")

            try:
                # Process the page
                self._process_pdf_file_page(
                    pdfix,
                    id,
                    page,
                    page_index,
                    paddlex,
                    template_json_creator,
                    progress_bar,
                    max_formulas_and_tables_per_page,
                )
            except Exception:
                raise
            finally:
                # Clean-up
                page.Release()

        # Create template for whole document
        template_json_dict: dict = template_json_creator.create_json_dict_for_document(self.model, self.zoom)

        # Save template to file
        template_path = os.path.join(Path(__file__).parent.absolute(), f"../output/{id}-template_json.json")
        with open(template_path, "w") as file:
            file.write(json.dumps(template_json_dict, indent=2))

        # Autotag document
        self._autotag_using_template(doc, template_json_dict, pdfix)

        # Add Associate File (AF) for formulas to document
        if self.process_formula:
            formulas: list = template_json_creator.get_formulas()
            self._add_afs_for_formulas(pdfix, doc, paddlex, formulas)

        # Save document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise PdfixException(pdfix)

    def _process_pdf_file_page(
        self,
        pdfix: Pdfix,
        id: str,
        page: PdfPage,
        page_index: int,
        paddlex: PaddleXEngine,
        templateJsonCreator: TemplateJsonCreator,
        progress_bar: tqdm,
        max_formulas_and_tables_per_page: int,
    ) -> None:
        """
        Create template json for current PDF document page.

        Args:
            pdfix (Pdfix): Pdfix SDK.
            id (string): PDF document name.
            page (PdfPage): The PDF document page to process.
            page_index (int): PDF file page index.
            paddlex (PaddleXEngine): PaddleX engine instance for processing.
            templateJsonCreator (TemplateJsonCreator): Template JSON creator.
            progress_bar (tqdm): Progress bar that we update for each model
                call.
            max_formulas_and_tables_per_page (int): Our estimation how many
                tables and formulas can be in one page.
        """
        page_number = page_index + 1

        # Define rotation for rendering the page
        page_view = page.AcquirePageView(self.zoom, kRotate0)

        try:
            # Render the page as an image
            image = create_image_from_pdf_page(pdfix, page, page_view)

            # Run layout model analysis and formula and table model analysis using the PaddleX engine
            results = paddlex.process_pdf_page_image_with_ai(
                image, id, page_number, progress_bar, max_formulas_and_tables_per_page
            )

            # Create template json from PaddleX results for this page
            templateJsonCreator.process_page(results, page_number, page_view, self.zoom)
        except Exception:
            raise
        finally:
            # Release resources
            page_view.Release()

    def _autotag_using_template(self, doc: PdfDoc, template_json_dict: dict, pdfix: Pdfix) -> None:
        """
        Autotag opened document using template and remove previous tags and structures.

        Args:
            doc (PdfDoc): Opened document to tag.
            template_json_dict (dict): Template for tagging.
            pdfix (Pdfix): Pdfix SDK.
        """
        # Remove old structure and prepare an empty structure tree
        doc.RemoveTags()
        doc.RemoveStructTree()

        # Convert template json to memory stream
        memory_stream = pdfix.CreateMemStream()
        try:
            raw_data, raw_data_size = json_to_raw_data(template_json_dict)
            if not memory_stream.Write(0, raw_data, raw_data_size):
                raise PdfixException(pdfix)

            doc_template = doc.GetTemplate()
            if not doc_template.LoadFromStream(memory_stream, kDataFormatJson):
                raise PdfixException("Unable save template into document")
        except Exception:
            raise
        finally:
            memory_stream.Destroy()

        # Autotag document
        tagsParams = PdfTagsParams()
        if not doc.AddTags(tagsParams):
            raise PdfixException(pdfix)

    def _add_afs_for_formulas(self, pdfix: Pdfix, doc: PdfDoc, paddlex: PaddleXEngine, formulas: list) -> None:
        """
        For each formula add associate file to document.

        Args:
            pdfix (Pdfix): PDFix SDK.
            doc (PdfDoc): Tagged PDF document.
            paddlex (PaddleXEngine): PaddleX engine instance for processing.
            formulas (list): List of formulas to process.
        """
        struct_tree = doc.GetStructTree()
        if struct_tree is None:
            raise PdfixException(pdfix, "PDF has no structure tree")

        child_element = struct_tree.GetStructElementFromObject(struct_tree.GetChildObject(0))
        items = browse_tags_recursive(child_element, "Formula")
        for formula_element in items:
            element_id: str = formula_element.GetId()
            if element_id == "":
                # This formula element does not have "id"
                continue

            index = next((i for i, data in enumerate(formulas) if str(data[0]) == element_id), -1)
            if index < 0:
                # We don't have data for this formula "id"
                continue
            formula = formulas.pop(index)
            set_associated_file_math_ml(pdfix, formula_element, formula[1], paddlex.MATH_ML_VERSION)
