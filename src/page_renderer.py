import base64
import tempfile

import cv2
import numpy as np
from pdfixsdk import (
    GetPdfix,
    PdfImageParams,
    PdfPage,
    PdfPageRenderParams,
    PdfPageView,
    kImageDIBFormatArgb,
    kImageFormatJpg,
    kPsTruncate,
)

from exceptions import PdfixException


def create_image_from_pdf_page(pdf_page: PdfPage, page_view: PdfPageView) -> cv2.typing.MatLike:
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


def create_image_from_part_of_page(image: cv2.typing.MatLike, box: list, offset: int) -> cv2.typing.MatLike:
    """
    Takes rendered PDF page and cuts box from it with specified offset

    Args:
        image (cv2.typing.MatLike): Rendered PDF page.
        box (list): Bounding box of wanted area
        offset (int): How many pixel around bounding box should be also taken.

    Returns:
        Cut image as MatLike object.
    """
    min_x = int(box[0]) - offset
    min_y = int(box[1]) - offset
    max_x = int(box[2]) + offset
    max_y = int(box[3]) + offset
    return image[min_y:max_y, min_x:max_x]


def convert_base64_image_to_matlike_image(base64_data: str) -> cv2.typing.MatLike:
    """
    Converts image data from base64 encoded format to cv2 MatLike (numpy array) format

    Args:
        base64_data (str): Data containing header and encoded image

    Returns:
        MatLike image
    """
    header, encoded = base64_data.split(",", 1)
    image_data = base64.b64decode(encoded)
    numpy_array = np.frombuffer(image_data, np.uint8)
    return cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)
