import tempfile

import cv2
from paddleocr import PPStructure
from pdfixsdk import *

# from pdfixsdk import *
from tqdm import tqdm

PP_ENGINE = PPStructure(
    show_log=True,
    lang="en",
    enable_mkldnn=False,  # results may be unstable
    layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
    table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
    det_model_dir="models/det/en_PP-OCRv3_det_infer/",
    rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
)


class PdfixException(Exception):
    def __init__(self, message: str = ""):
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


def draw_rect(image, rect):
    # Rect coordinates (top-left and bottom-right corner)
    start_point = (rect.left, rect.top)  # X, Y
    end_point = (rect.right, rect.bottom)  # X, Y
    # Color (B, G, R) and width
    color = (0, 255, 0)
    thickness = 2
    cv2.rectangle(image, start_point, end_point, color, thickness)


def update_table_cells(pdf_element: PdeElement, region_data: dict, page_view: PdfPageView, image):
    """
    Updates the table element with detected cells

    Args:
        pdf_element (PdeElement): The table element to edit.
        region_data (dict): The data containing the cell bounding boxes.
        page_view (PdfPageView): The view of the PDF page used for coordinate conversion.
        image (any): The image representation of the page for visualization.
    """    
    # Return early if no cells exist in the region
    if not region_data["res"]:
        return

    # Get the page map and create the table object
    page_map = pdf_element.GetPageMap()
    table = PdeTable(pdf_element.obj)

    # Initialize variables for row, column, and previous x-coordinate
    column = 0
    row = 0
    previous_left = -1  # Initialize the previous left x-coordinate

    # Loop through each cell's bounding box in the region
    for cell_bbox in region_data["res"]["cell_bbox"]:
        # Define the cell bounding box with some padding
        cell_rect = PdfDevRect()
        cell_rect.left = int(cell_bbox[0] + region_data["bbox"][0]) - 2
        cell_rect.top = int(cell_bbox[1] + region_data["bbox"][1]) - 2
        cell_rect.right = int(cell_bbox[2] + region_data["bbox"][0]) + 2
        cell_rect.bottom = int(cell_bbox[3] + region_data["bbox"][1]) + 2
        
        # Draw the cell rectangle on the image for visualization (optional step)
        draw_rect(image, cell_rect)

        # Convert cell rectangle to page coordinates
        cell_bbox = page_view.RectToPage(cell_rect)

        # Create a new cell element and set its properties
        cell = PdeCell(page_map.CreateElement(kPdeCell, table).obj)
        cell.SetColNum(column)
        cell.SetRowNum(row)
        cell.SetBBox(cell_bbox)
        cell.SetColSpan(1)
        cell.SetRowSpan(1)

        # Update the column count
        column += 1

        # Check if we need to move to the next row (if the current cell's left is less than the previous left)
        if previous_left > cell_rect.left:
            row += 1  # Move to the next row
            column = 0  # Reset column to 0 for the new row
        
        # Update the previous left value
        previous_left = cell_rect.left

    # Set the number of columns and rows in the table based on the last values of column and row
    table.SetNumCols(column + 1)
    table.SetNumRows(row + 1)


def render_page(pdf_page: PdfPage, page_view: PdfPageView):
    """
    Renders the PDF page into an opencv image

    Args:
        pdf_page (PdfPage): The page to render.
        page_view (PdfPageView): The view of the PDF page used for coordinate conversion.
        image (any): The image representation of the page for visualization.
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

    
def add_initial_elements(page_map: PdePageMap, page_view: PdfPageView, regions: list, image: any):
    """
    Adds initial structural elements to the page map based on detected regions.

    Args:
        page_map (PdePageMap): The page map where elements will be added.
        page_view (PdfPageView): The view of the PDF page used for coordinate conversion.
        regions (list): A list of detected regions, each containing bounding box and type.
        image (any): The image representation of the page for visualization.
    """
    for region in regions:
        rect = PdfDevRect()
        rect.left = int(region["bbox"][0])
        rect.top = int(region["bbox"][1])
        rect.right = int(region["bbox"][2])
        rect.bottom = int(region["bbox"][3])
        bbox = page_view.RectToPage(rect)

        # Draw the cell rectangle on the image for visualization (optional step)
        draw_rect(image, rect)

        # Determine element type
        element_type = kPdeText  # Default to text
        region_type = region["type"].lower()
        if region_type == "table":
            element_type = kPdeTable
        elif region_type == "figure":
            element_type = kPdeImage
        elif region_type == "list":
            element_type = kPdeList
        
        element = page_map.CreateElement(element_type, None)
        element.SetBBox(bbox)
        
        if region_type == "title":
            element.SetTextStyle(kTextH1)
        # elif region_type == "table":
        #     update_table_cells(element, region, page_view, image)    


def autotag_page(page: PdfPage, doc_struct_elem: PdsStructElement):
    """
    Automatically tags a PDF page by analyzing its layout and mapping the detected elements
    to the document structure.

    Args:
        page (PdfPage): The PDF page to process.
        doc_struct_elem (PdsStructElement): The root structure element where tags will be added.
    """
    pdfix = GetPdfix()

    # Define zoom level and rotation for rendering the page
    zoom = 4.0
    rotate = kRotate0
    page_view = page.AcquirePageView(zoom, rotate)

    # Render the page as an image
    img = render_page(page, page_view)

    # Run layout analysis using the Paddle engine
    result = PP_ENGINE(img)

    # Acquire the page map to store recognized elements
    pageMap = page.AcquirePageMap()

    # Add detected elements to the page map based on the analysis result
    add_initial_elements(pageMap, page_view, result, img)

    # Debugging: Save the rendered image for inspection
    # cv2.imwrite("output.jpg", img)

    # Generate structured elements from the page map
    if not pageMap.CreateElements():
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    # Create a new structural element for the page
    pageElem = doc_struct_elem.AddNewChild("NonStruct", doc_struct_elem.GetNumChildren())
    
    # Assign recognized elements as tags to the structure element
    if not pageMap.AddTags(pageElem, False, PdfTagsParams()):
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    # Release resources
    pageMap.Release()
    page_view.Release()


def autotag_pdf(input_pdf: str, output_pdf: str):
    """
    Automatically tags a PDF document by analyzing its structure and applying tags to each page.

    Args:
        input_pdf (str): Path to the input PDF file.
        output_pdf (str): Path to save the output tagged PDF file.
    """
    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception("Pdfix Initialization failed")

    # TODO: Add authorization here

    # Open the document
    doc = pdfix.OpenDoc(input_pdf, "")
    if doc is None:
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    # Remove old structure and prepare an empty structure tree
    doc.RemoveTags()
    doc.RemoveStructTree()
    structTree = doc.CreateStructTree()
    docStructElem = structTree.GetStructElementFromObject(structTree.GetObject())
    if docStructElem is None:
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    numPages = doc.GetNumPages()

    # Process each page
    for i in tqdm(range(0, numPages), desc="Processing pages"):
        # Acquire the page
        page = doc.AcquirePage(i)
        if page is None:
            raise PdfixException("Unable to acquire the page")

        try:
            autotag_page(page, docStructElem)  # Removed unnecessary pdfix argument
        except Exception as e:
            raise e

        page.Release()

    # Save the processed document
    if not doc.Save(output_pdf, kSaveFull):
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")
