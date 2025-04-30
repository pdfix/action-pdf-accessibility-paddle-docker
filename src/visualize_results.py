import cv2
from pathlib import Path
from pdfixsdk import PdfDevRect, PdfPage


def draw_rect(image: cv2.typing.MatLike,
              rect: PdfDevRect, color:
              cv2.typing.Scalar,
              thickness: int) -> None:
    """
    Draw rectangle with in image with desired size, color and width

    Args:
        image (cv2.typing.MatLike): Rendered image of PDF page.
        rect (PdfDevRect): Area where green rectangle will be drawn.
        color (cv2.typing.Scalar): Color in RGB form 0 to 255
        thickness (int): Width of lines in pixels
    """
    cv2.rectangle(image,
                  (rect.left, rect.top),
                  (rect.right, rect.bottom),
                  color,
                  thickness)


def fill_image_with_recognized_places(zoom: float,
                                      id: str,
                                      page: PdfPage,
                                      results: list,
                                      image: cv2.typing.MatLike) -> None:
    """
    Visualize recognized elements in PDF page

    Args:
        zoom (float): Zoom level for rendering the page.
        id (string): PDF document name
        page (PdfPage): The PDF page that was processed.
        regions (list): List of recognized elements by AI model.
        image (cv2.typing.MatLike): Rendered image of PDF page.
    """
    for result in results:
        rect = PdfDevRect()
        rect.left = int(result["bbox"][0])
        rect.top = int(result["bbox"][1])
        rect.right = int(result["bbox"][2])
        rect.bottom = int(result["bbox"][3])
        draw_rect(image, rect, (0, 255, 0), 2) # green

        if result["type"].lower() == "table":
            # table recognition is turned off
            if not result["res"]:
                continue

            for cell in result["custom"]:
                cell_rect = PdfDevRect()
                cell_rect.left = int(cell["page_bbox"][0])
                cell_rect.top = int(cell["page_bbox"][1])
                cell_rect.right = int(cell["page_bbox"][2])
                cell_rect.bottom = int(cell["page_bbox"][3])
                border_color = (255, 255, 0) if cell["text"] else (255, 0, 0)
                draw_rect(image, cell_rect, border_color, 1)

        if result["type"].lower() == "list":
            for li_bbox in result["custom"]:
                li_rect = PdfDevRect()
                li_rect.left = int(li_bbox[0])
                li_rect.top = int(li_bbox[1])
                li_rect.right = int(li_bbox[2])
                li_rect.bottom = int(li_bbox[3])
                draw_rect(image, li_rect, (0, 0, 255), 1) # red

    # Debugging: Save the rendered image for inspection
    images = Path(f"images-{zoom}")
    images.mkdir(exist_ok=True)
    cv2.imwrite(f"{str(images)}/{id}_{page.GetNumber()+1}.jpg", image)
