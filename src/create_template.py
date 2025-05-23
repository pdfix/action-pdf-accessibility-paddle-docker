import json
from pathlib import Path

from pdfixsdk import (
    GetPdfix,
    PdfPage,
    kRotate0,
)
from tqdm import tqdm

from ai import PaddleXEngine
from exceptions import PdfixException
from page_renderer import create_image_from_pdf_page
from template_json import TemplateJsonCreator


class CreateTemplateJsonUsingPaddleXRecognition:
    def __init__(self, input_path: str, output_path: str, model: str, zoom: float) -> None:
        """
        Initialize class for tagging pdf(s).

        Args:
            input_path (string): Path to one pdf or folder
            output_path (string): Path where proccessed pdf(s) should be
                written, if input is 1 pdf output should be also 1 pdf,
                if input is folder output should also be folder
            model (string): Paddle model for layout recognition
            zoom (float): Zoom level for rendering the page
        """
        self.input_path_str = input_path
        self.output_path_str = output_path
        self.model = model
        self.zoom = zoom

    def process_file(self) -> None:
        """
        Automatically creates template json.
        """
        id: str = Path(self.input_path_str).stem

        pdfix = GetPdfix()
        if pdfix is None:
            raise Exception("Pdfix Initialization failed")

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

            try:
                # Process the page
                self._process_pdf_file_page(
                    id, page, page_index, template_json_creator, progress_bar, max_formulas_and_tables_per_page
                )
            except Exception:
                raise
            finally:
                # Clean-up
                page.Release()

        # Create template json for whole document
        template_json_dict: dict = template_json_creator.create_json_dict_for_document(self.model, self.zoom)

        # Save template json
        with open(self.output_path_str, "w") as file:
            file.write(json.dumps(template_json_dict, indent=2))

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

        # Define rotation for rendering the page
        page_view = page.AcquirePageView(self.zoom, kRotate0)

        try:
            # Render the page as an image
            image = create_image_from_pdf_page(page, page_view)

            # Run layout model analysis and formula and table model analysis using the PaddleX engine
            paddlex = PaddleXEngine(self.model)
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
