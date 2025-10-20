import base64
import tempfile

import cv2
import numpy as np
from pdfixsdk import (
    PdfDevRect,
    PdfDoc,
    PdfImageParams,
    Pdfix,
    PdfPage,
    PdfPageRenderParams,
    PdfPageView,
    PdfRect,
    PsFileStream,
    PsImage,
    kImageDIBFormatArgb,
    kImageFormatJpg,
    kPsTruncate,
    kRotate0,
)

from exceptions import PdfixFailedToRenderException


def create_image_from_pdf_page(pdfix: Pdfix, pdf_page: PdfPage, page_view: PdfPageView) -> cv2.typing.MatLike:
    """
    Renders the PDF page into an opencv image of size 792x612.

    Args:
        pdfix (Pdfix): Pdfix SDK.
        pdf_page (PdfPage): The page to render.
        page_view (PdfPageView): The view of the PDF page used
            for coordinate conversion.

    Returns:
        Rendered page as MatLike object.
    """
    # Get the dimensions of the page view (device width and height)
    page_width: int = page_view.GetDeviceWidth()
    page_height: int = page_view.GetDeviceHeight()

    # Create an image with the specified dimensions and ARGB format
    page_image: PsImage = pdfix.CreateImage(page_width, page_height, kImageDIBFormatArgb)
    if page_image is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to create the image")

    try:
        # Set up rendering parameters
        render_params: PdfPageRenderParams = PdfPageRenderParams()
        render_params.image = page_image
        render_params.matrix = page_view.GetDeviceMatrix()

        # Render the page content onto the image
        if not pdf_page.DrawContent(render_params):
            raise PdfixFailedToRenderException(pdfix, "Unable to draw the content")

        # Save the renderred image to a temporary file in JPG format
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            file_stream: PsFileStream = pdfix.CreateFileStream(temp_file.name, kPsTruncate)
            if file_stream is None:
                raise PdfixFailedToRenderException(pdfix, "Unable to create file stream")

            try:
                # Set image parameters (format and quality)
                image_params: PdfImageParams = PdfImageParams()
                image_params.format = kImageFormatJpg
                image_params.quality = 100

                # Save the image to the file stream
                if not page_image.SaveToStream(file_stream, image_params):
                    raise PdfixFailedToRenderException(pdfix, "Unable to save the image to the stream")

            except Exception:
                raise
            finally:
                # Clean up resources
                file_stream.Destroy()

            # Return the saved image as a NumPy array using OpenCV
            return cv2.imread(temp_file.name)
    except Exception:
        raise
    finally:
        page_image.Destroy()

    black_pixel: cv2.typing.MatLike = np.zeros((1, 1, 3), dtype=np.uint8)
    return black_pixel


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
    min_x: int = int(box[0]) - offset
    min_y: int = int(box[1]) - offset
    max_x: int = int(box[2]) + offset
    max_y: int = int(box[3]) + offset
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
    image_data: bytes = base64.b64decode(encoded)
    numpy_array: cv2.typing.MatLike = np.frombuffer(image_data, np.uint8)
    return cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)


def render_element_to_image(pdfix: Pdfix, doc: PdfDoc, page_num: int, bbox: PdfRect, zoom: float) -> cv2.typing.MatLike:
    """
    Render element from document into opencv image.

    Args:
        pdfix (Pdfix): PDFix SDK.
        doc (PdfDoc): The PDF document to render.
        page_num (int): The page number where element is located.
        bbox (PdfRect): The bounding box of element to render.
        zoom (float): The zoom level for rendering.

    Returns:
        The rendered element as MatLike object.
    """
    page: PdfPage = doc.AcquirePage(page_num)
    if page is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to acquire the page")

    try:
        page_view: PdfPageView = page.AcquirePageView(zoom, kRotate0)
        if page_view is None:
            raise PdfixFailedToRenderException(pdfix, "Unable to acquire page view")

        try:
            # Convert PDF Rect to Image Rect
            rect: PdfDevRect = page_view.RectToDevice(bbox)

            # Set up rendering parameters
            render_parameters: PdfPageRenderParams = PdfPageRenderParams()
            render_parameters.matrix = page_view.GetDeviceMatrix()
            render_parameters.clip_box = bbox
            render_parameters.image = pdfix.CreateImage(
                rect.right - rect.left,
                rect.bottom - rect.top,
                kImageDIBFormatArgb,
            )
            if render_parameters.image is None:
                raise PdfixFailedToRenderException(pdfix, "Unable to create the image")

            try:
                # Render the page element content onto the image
                if not page.DrawContent(render_parameters):
                    raise PdfixFailedToRenderException(pdfix, "Unable to draw the content")

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                    file_stream: PsFileStream = pdfix.CreateFileStream(temp_file.name, kPsTruncate)
                    if file_stream is None:
                        raise PdfixFailedToRenderException(pdfix, "Unable to create file stream")

                    try:
                        # Set image parameters (format and quality)
                        image_params: PdfImageParams = PdfImageParams()
                        image_params.format = kImageFormatJpg
                        image_params.quality = 100

                        # Save the image to the file stream
                        if not render_parameters.image.SaveToStream(file_stream, image_params):
                            raise PdfixFailedToRenderException(pdfix, "Unable to save the image to the stream")

                    except Exception:
                        raise
                    finally:
                        file_stream.Destroy()

                    # Return the saved image as a NumPy array using OpenCV
                    return cv2.imread(temp_file.name)
            except Exception:
                raise
            finally:
                render_parameters.image.Destroy()
        except Exception:
            raise
        finally:
            page_view.Release()
    except Exception:
        raise
    finally:
        page.Release()

    black_pixel: cv2.typing.MatLike = np.zeros((1, 1, 3), dtype=np.uint8)
    return black_pixel
