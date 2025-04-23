import tempfile
import json
import cv2
from paddleocr import PPStructure
from pdfixsdk import *
from pathlib import Path
from tqdm import tqdm

# https://paddlepaddle.github.io/PaddleOCR/main/en/ppstructure/models_list.html
PP_ENGINE = PPStructure(
    show_log=True,
    lang="en",
    enable_mkldnn=False,  # results may be unstable
    layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
    table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
    det_model_dir="models/det/en_PP-OCRv3_det_infer/",
    rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
    formula_model_dir="models/formula/rec_latex_ocr_infer/"
)


class PdfixException(Exception):
    def __init__(self, message: str = ""):
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


def draw_rect(id: str, image, rect):
    cv2.rectangle(image, (rect.left, rect.top), (rect.right, rect.bottom), (0, 255, 0), 2)


def update_table_cells(id: str, pdf_element: PdeElement, region_data: dict, page_view: PdfPageView, image):
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
        draw_rect(id, image, cell_rect)

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


def render_page(id: str, pdf_page: PdfPage, page_view: PdfPageView):
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

def prepare_initial_elements(id: str, page_view: PdfPageView, regions: list):
    """
    Prepare initial structural elements for the template based on detected regions.

    Args:
        page_view (PdfPageView): The view of the PDF page used for coordinate conversion.
        regions (list): A list of detected regions, each containing bounding box and type.
        image (any): The image representation of the page for visualization.
    """
    elements = []

    for region in regions:
        rect = PdfDevRect()
        rect.left = int(region["bbox"][0])
        rect.top = int(region["bbox"][1])
        rect.right = int(region["bbox"][2])
        rect.bottom = int(region["bbox"][3])
        bbox = page_view.RectToPage(rect)

        # Determine element type
        element_type = "pde_text"  # Default to text
        region_type = region["type"].lower()
        if region_type == "pde_table":
            element_type = kPdeTable
        elif region_type == "pde_image":
            element_type = kPdeImage
        elif region_type == "list":
            element_type = "pde_list"

        elem = {}
        elem["bbox"] = [rect.left, rect.bottom, rect.right, rect.top]
        elem["type"] = element_type

        if region_type == "title":
            elem["tag"] = "H1"
        # elif region_type == "table":
        #     update_table_cells(element, region, page_view, image)   

        elements.append(elem)

    return elements
    
def add_initial_elements(id: str, page_map: PdePageMap, page_view: PdfPageView, regions: list, image: any):
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
        draw_rect(id, image, rect)

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
        
        # if region_type == "title":
        #     element.SetTextStyle(kTextH1)
        # elif region_type == "table":
        #     update_table_cells(element, region, page_view, image)


def autotag_page(id: str, page: PdfPage, doc_struct_elem: PdsStructElement):
    """
    Automatically tags a PDF page by analyzing its layout and mapping the detected elements
    to the document structure.

    Args:
        page (PdfPage): The PDF page to process.
        doc_struct_elem (PdsStructElement): The root structure element where tags will be added.
    """
    pdfix = GetPdfix()

    # Define zoom level and rotation for rendering the page
    zoom = 1.0
    rotate = kRotate0
    page_view = page.AcquirePageView(zoom, rotate)

    # Render the page as an image
    img = render_page(id, page, page_view)

    # Run layout analysis using the Paddle engine
    result = PP_ENGINE(img)

    elems = prepare_initial_elements(id, page_view, result)
    print(json.dumps(elems, indent=2))

    # Acquire the page map to store recognized elements
    page_map = page.AcquirePageMap()

    # Add detected elements to the page map based on the analysis result
    add_initial_elements(id, page_map, page_view, result, img)

    # Debugging: Save the rendered image for inspection
    images = Path(f"images-{zoom}")
    images.mkdir(exist_ok=True)
    cv2.imwrite(f"{str(images)}/{id}_{page.GetNumber()+1}.jpg", img)

    # Generate structured elements from the page map
    if not page_map.CreateElements():
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    # Create a new structural element for the page
    page_element = doc_struct_elem.AddNewChild("NonStruct", doc_struct_elem.GetNumChildren())
    
    # Assign recognized elements as tags to the structure element
    if not page_map.AddTags(page_element, False, PdfTagsParams()):
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    # Release resources
    page_map.Release()
    page_view.Release()


def autotag_pdf(input_pdf: str, output_pdf: str):
    """
    Automatically tags a PDF document by analyzing its structure and applying tags to each page.

    Args:
        input_pdf (str): Path to the input PDF file.
        output_pdf (str): Path to save the output tagged PDF file.
    """
    id = Path(input_pdf).stem

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
    struct_tree = doc.CreateStructTree()
    doc_struct_elem = struct_tree.GetStructElementFromObject(struct_tree.GetObject())
    if doc_struct_elem is None:
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    num_pages = doc.GetNumPages()

    # Process each page
    for i in tqdm(range(0, num_pages), desc="Processing pages"):
        # Acquire the page
        page = doc.AcquirePage(i)
        if page is None:
            raise PdfixException("Unable to acquire the page")
        try:
            autotag_page(id, page, doc_struct_elem)  # Removed unnecessary pdfix argument
        except Exception as e:
            raise e

        page.Release()

    # Save the processed document
    if not doc.Save(output_pdf, kSaveFull):
        raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")


def autotag_folder(directory: str, output_directory: str):
    input_path = Path(directory)
    output_path = Path(output_directory)

    if not input_path.is_dir():
        print(f"Error: '{directory}' is not a valid directory.")
        return
    
    output_path.mkdir(parents=True, exist_ok=True)

    for pdf_file in input_path.glob("*.pdf"):
        output_file = output_path / pdf_file.name  # Zachová názov súboru, ale v novom priečinku
        autotag_pdf(str(pdf_file), str(output_file))