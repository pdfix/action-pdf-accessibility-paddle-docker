import json
from pathlib import Path
from typing import Optional

import cv2
from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfPage,
    PdfPageView,
    kRotate0,
)
from tqdm import tqdm

from ai import PaddleXEngine
from constants import (
    PERCENT_AI,
    PERCENT_RENDER,
    PERCENT_TEMPLATE,
    PROGRESS_FIRST_STEP,
    PROGRESS_FOURTH_STEP,
    PROGRESS_SECOND_STEP,
    PROGRESS_THIRD_STEP,
)
from exceptions import PdfixFailedToCreateTemplateException, PdfixFailedToOpenException, PdfixInitializeException
from page_renderer import create_image_from_pdf_page
from template_json import TemplateJsonCreator
from utils_sdk import authorize_sdk


class CreateTemplateJsonUsingPaddleXRecognition:
    def __init__(
        self,
        license_name: Optional[str],
        license_key: Optional[str],
        input_path: str,
        output_path: str,
        model: str,
        zoom: float,
        process_table: bool,
        thresholds: dict,
    ) -> None:
        """
        Initialize class for tagging pdf(s).

        Args:
            license_name (Optional[str]): Pdfix sdk license name (e-mail).
            license_key (Optional[str]): Pdfix sdk license key.
            input_path (str): Path to PDF document.
            output_path (str): Path where template JSON should be saved.
            model (str): Paddle model for layout recognition.
            zoom (float): Zoom level for rendering the page.
            process_table (bool): Whether to process tables.
            thresholds (dict): Thresholds for layout detection.
        """
        self.license_name: Optional[str] = license_name
        self.license_key: Optional[str] = license_key
        self.input_path_str: str = input_path
        self.output_path_str: str = output_path
        self.model: str = model
        self.zoom: float = zoom
        self.process_table: bool = process_table
        self.thresholds: dict = thresholds

    def process_file(self) -> None:
        """
        Automatically creates template json.
        """
        total_progress_count: int = (
            PROGRESS_FIRST_STEP + PROGRESS_SECOND_STEP + PROGRESS_THIRD_STEP + PROGRESS_FOURTH_STEP
        )
        with tqdm(total=total_progress_count) as progress_bar:
            progress_bar.set_description("Initializing")

            id: str = Path(self.input_path_str).stem

            pdfix: Optional[Pdfix] = GetPdfix()
            if pdfix is None:
                raise PdfixInitializeException()

            # Try to authorize PDFix SDK
            authorize_sdk(pdfix, self.license_name, self.license_key)

            # Open the document
            doc: Optional[PdfDoc] = pdfix.OpenDoc(self.input_path_str, "")
            if doc is None:
                raise PdfixFailedToOpenException(pdfix, self.input_path_str)

            # Process images of each page
            number_of_pages: int = doc.GetNumPages()
            paddlex: PaddleXEngine = PaddleXEngine(self.model, False, self.process_table, self.thresholds)
            template_json_creator: TemplateJsonCreator = TemplateJsonCreator()

            progress_bar.update(PROGRESS_FIRST_STEP)
            progress_bar.set_description("Processing pages")
            step_count: float = float(PROGRESS_SECOND_STEP) / number_of_pages

            for page_index in range(0, number_of_pages):
                # Acquire the page
                page: Optional[PdfPage] = doc.AcquirePage(page_index)
                if page is None:
                    raise PdfixFailedToCreateTemplateException(pdfix, "Unable to acquire the page")

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
                        step_count,
                    )
                except Exception:
                    raise
                finally:
                    # Clean-up
                    page.Release()

            progress_bar.n = PROGRESS_FIRST_STEP + PROGRESS_SECOND_STEP
            progress_bar.set_description("Saving template")
            progress_bar.refresh()

            # Create template json for whole document
            template_json_dict: dict = template_json_creator.create_json_dict_for_document(self.model, self.zoom)
            output_data: dict = template_json_dict

            # Save template json
            with open(self.output_path_str, "w") as file:
                file.write(json.dumps(output_data, indent=2))

            progress_bar.n = total_progress_count
            progress_bar.set_description("Done")
            progress_bar.refresh()

    def _process_pdf_file_page(
        self,
        pdfix: Pdfix,
        id: str,
        page: PdfPage,
        page_index: int,
        paddlex: PaddleXEngine,
        templateJsonCreator: TemplateJsonCreator,
        progress_bar: tqdm,
        total_units_for_page_processing: float,
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
            progress_bar (tqdm): Progress bar.
            total_units_for_page_processing (float): How many units progress bar needs to update.
        """
        page_number: int = page_index + 1

        render_step_units: float = total_units_for_page_processing * PERCENT_RENDER
        ai_step_units: float = total_units_for_page_processing * PERCENT_AI
        template_step_units: float = total_units_for_page_processing * PERCENT_TEMPLATE

        # Define rotation for rendering the page
        page_view: Optional[PdfPageView] = page.AcquirePageView(self.zoom, kRotate0)
        if page_view is None:
            raise PdfixFailedToCreateTemplateException(pdfix, "Unable to acquire page view")

        try:
            # Render the page as an image
            image: cv2.typing.MatLike = create_image_from_pdf_page(pdfix, page, page_view)
            progress_bar.update(render_step_units)

            # Run layout model analysis and formula and table model analysis using the PaddleX engine
            results: dict = paddlex.process_pdf_page_image_with_ai(image, id, page_number, progress_bar, ai_step_units)

            # Create template json from PaddleX results for this page
            templateJsonCreator.process_page(results, page_number, page_view, self.zoom)
            progress_bar.update(template_step_units)
        except Exception:
            raise
        finally:
            # Release resources
            page_view.Release()
