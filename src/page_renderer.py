import base64
import os
from typing import Optional

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


def save_and_read_image(pdfix: Pdfix, image: PsImage, image_name: str) -> cv2.typing.MatLike:
    """
    Save the rendered image as JPG into the working folder, read it with OpenCV and delete the file.

    Args:
        pdfix (Pdfix): Pdfix SDK.
        image (PsImage): Rendered image.
        image_name (str): File name in the working folder, for example "paddle_page_1.jpg".

    Returns:
        Image as MatLike object.
    """
    file_stream: Optional[PsFileStream] = pdfix.CreateFileStream(image_name, kPsTruncate)
    if file_stream is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to create file stream")
    try:
        try:
            image_params: PdfImageParams = PdfImageParams()
            image_params.format = kImageFormatJpg
            image_params.quality = 100
            if not image.SaveToStream(file_stream, image_params):
                raise PdfixFailedToRenderException(pdfix, "Unable to save the image to the stream")
        finally:
            file_stream.Destroy()
        return cv2.imread(image_name)
    finally:
        if os.path.exists(image_name):
            os.remove(image_name)


def create_image_from_pdf_page(
    pdfix: Pdfix, pdf_page: PdfPage, page_view: PdfPageView, image_name: str
) -> cv2.typing.MatLike:
    """
    Renders the PDF page into an opencv image.

    Args:
        pdfix (Pdfix): Pdfix SDK.
        pdf_page (PdfPage): The page to render.
        page_view (PdfPageView): The view of the PDF page used
            for coordinate conversion.
        image_name (str): File name of the image in the working folder while it is read.

    Returns:
        Rendered page as MatLike object.
    """
    # Get the dimensions of the page view (device width and height)
    page_width: int = page_view.GetDeviceWidth()
    page_height: int = page_view.GetDeviceHeight()

    # Create an image with the specified dimensions and ARGB format
    page_image: Optional[PsImage] = pdfix.CreateImage(page_width, page_height, kImageDIBFormatArgb)
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

        # Image goes to the working folder while it is read, then it is deleted (like in other actions)
        return save_and_read_image(pdfix, page_image, image_name)
    except Exception:
        raise
    finally:
        page_image.Destroy()


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
    # Keep the area inside the image: a negative index would cut from the other side (empty image)
    height: int = image.shape[0]
    width: int = image.shape[1]
    min_x: int = max(0, int(box[0]) - offset)
    min_y: int = max(0, int(box[1]) - offset)
    max_x: int = min(width, int(box[2]) + offset)
    max_y: int = min(height, int(box[3]) + offset)
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


def render_element_to_image(
    pdfix: Pdfix, doc: PdfDoc, page_num: int, bbox: PdfRect, zoom: float, image_name: str
) -> cv2.typing.MatLike:
    """
    Render element from document into opencv image.

    Args:
        pdfix (Pdfix): PDFix SDK.
        doc (PdfDoc): The PDF document to render.
        page_num (int): The page number where element is located.
        bbox (PdfRect): The bounding box of element to render.
        zoom (float): The zoom level for rendering.
        image_name (str): File name of the image in the working folder while it is read.

    Returns:
        The rendered element as MatLike object.
    """
    page: Optional[PdfPage] = doc.AcquirePage(page_num)
    if page is None:
        raise PdfixFailedToRenderException(pdfix, "Unable to acquire the page")

    try:
        page_view: Optional[PdfPageView] = page.AcquirePageView(zoom, kRotate0)
        if page_view is None:
            raise PdfixFailedToRenderException(pdfix, "Unable to acquire page view")

        try:
            # Convert PDF Rect to Image Rect
            rect: PdfDevRect = page_view.RectToDevice(bbox)

            # Set up rendering parameters
            render_parameters: PdfPageRenderParams = PdfPageRenderParams()
            render_parameters.matrix = page_view.GetDeviceMatrix()
            render_parameters.clip_box = bbox
            ps_image: Optional[PsImage] = pdfix.CreateImage(
                rect.right - rect.left,
                rect.bottom - rect.top,
                kImageDIBFormatArgb,
            )
            if ps_image is None:
                raise PdfixFailedToRenderException(pdfix, "Unable to create the image")

            render_parameters.image = ps_image

            try:
                # Render the page element content onto the image
                if not page.DrawContent(render_parameters):
                    raise PdfixFailedToRenderException(pdfix, "Unable to draw the content")

                # Image goes to the working folder while it is read, then it is deleted (like in other actions)
                return save_and_read_image(pdfix, render_parameters.image, image_name)
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
