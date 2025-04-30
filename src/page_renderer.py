import cv2
from pdfixsdk import (
    PdfImageParams,
    PdfPage,
    PdfPageRenderParams,
    PdfPageView,
    GetPdfix,
    kImageDIBFormatArgb,
    kImageFormatJpg,
    kPsTruncate
)
import tempfile

from exceptions import PdfixException


def create_image_from_pdf_page(pdf_page: PdfPage,
                               page_view: PdfPageView) -> cv2.typing.MatLike:
    """
    Renders the PDF page into an opencv image of size 792x612.

    Args:
        pdf_page (PdfPage): The page to render.
        page_view (PdfPageView): The view of the PDF page used
            for coordinate conversion.

    Returns:
        Rendered page as MatLike object.
    """
    # Initialize PDFix instance
    pdfix = GetPdfix()

    # Get the dimensions of the page view (device width and height)
    page_width = page_view.GetDeviceWidth()
    page_height = page_view.GetDeviceHeight()

    # Create an image with the specified dimensions and ARGB format
    page_image = pdfix.CreateImage(page_width, page_height, kImageDIBFormatArgb)
    if page_image is None:
        raise PdfixException("Unable to create the image")

    # Set up rendering parameters
    render_params = PdfPageRenderParams()
    render_params.image = page_image
    render_params.matrix = page_view.GetDeviceMatrix()

    # Render the page content onto the image
    if not pdf_page.DrawContent(render_params):
        raise PdfixException("Unable to draw the content")

    # Save the rendered image to a temporary file in JPG format
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        file_stream = pdfix.CreateFileStream(temp_file.name, kPsTruncate)

        # Set image parameters (format and quality)
        image_params = PdfImageParams()
        image_params.format = kImageFormatJpg
        image_params.quality = 100

        # Save the image to the file stream
        if not page_image.SaveToStream(file_stream, image_params):
            raise PdfixException("Unable to save the image to the stream")

        # Clean up resources
        file_stream.Destroy()
        page_image.Destroy()

        # Return the saved image as a NumPy array using OpenCV
        return cv2.imread(temp_file.name)
