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


def drawRect(image, rect):
    # Rect coordinates (top-left and bottom-right corner)
    start_point = (rect.left, rect.top)  # X, Y
    end_point = (rect.right, rect.bottom)  # X, Y
    # Color (B, G, R) and width
    color = (0, 255, 0)
    thickness = 2
    cv2.rectangle(image, start_point, end_point, color, thickness)


def updateTableCells(elem: PdeElement, region: dict, page_view: PdfPageView, img):
    if not region["res"]:
        return

    page_map = elem.GetPageMap()
    table = PdeTable(elem.obj)
    col = 0
    row = 0
    left = -1  # initial x-coordinate
    rect = PdfDevRect()
    rect.left = int(region["bbox"][0])
    rect.top = int(region["bbox"][1])
    rect.right = int(region["bbox"][2])
    rect.bottom = int(region["bbox"][3])
    bbox = page_view.RectToPage(rect)
    # print(f"Table: {bbox.left}, {bbox.bottom}, {bbox.right}, {bbox.top}")

    for cell_bbox in region["res"]["cell_bbox"]:
        rect = PdfDevRect()
        rect.left = int(cell_bbox[0] + region["bbox"][0]) - 2
        rect.top = int(cell_bbox[1] + region["bbox"][1]) - 2
        rect.right = int(cell_bbox[2] + region["bbox"][0]) + 2
        rect.bottom = int(cell_bbox[3] + region["bbox"][1]) + 2
        drawRect(img, rect)

        bbox = page_view.RectToPage(rect)
        # print(f"Cell {bbox.left}, {bbox.bottom}, {bbox.right}, {bbox.top}")

        cell = PdeCell(page_map.CreateElement(kPdeCell, table).obj)
        cell.SetColNum(col)
        cell.SetRowNum(row)
        cell.SetBBox(bbox)
        cell.SetColSpan(1)
        cell.SetRowSpan(1)

        col += 1  # count cols
        if left > rect.left:
            row += 1  # count rows
            col = 0
        left = rect.left

    table.SetNumCols(col + 1)
    table.SetNumRows(row + 1)


def autotag_page(
    page: PdfPage,
    pdfix: Pdfix,
    doc_struct_elem: PdsStructElement,
) -> None:
    """Render a PDF page into a temporary file, which is then used for Paddle layout recognition.

    Parameters
    ----------
    page : PdfPage
        The PDF page to be processed
    pdfix : Pdfix
        The Pdfix SDK object
    doc_struct_elem : PdsStructElement
        PDF Tag for the page

    """  # noqa: E501
    zoom = 4.0
    page_view = page.AcquirePageView(zoom, kRotate0)
    if page_view is None:
        raise PdfixException("Unable to acquire the page view")

    # Create an image
    width = page_view.GetDeviceWidth()
    height = page_view.GetDeviceHeight()
    image = pdfix.CreateImage(width, height, kImageDIBFormatArgb)
    if image is None:
        raise PdfixException("Unable to create the image")

    # Render page
    render_params = PdfPageRenderParams()
    render_params.image = image
    render_params.matrix = page_view.GetDeviceMatrix()
    if not page.DrawContent(render_params):
        raise PdfixException("Unable to draw the content")

    # Create temp file for rendering
    with tempfile.NamedTemporaryFile() as tmp:
        # Save image to file
        img_name = tmp.name + ".jpg"
        img_name = "image.jpg"
        stm = pdfix.CreateFileStream(img_name, kPsTruncate)
        if stm is None:
            raise PdfixException("Unable to create the file stream")

        img_params = PdfImageParams()
        img_params.format = kImageFormatJpg
        img_params.quality = 100
        if not image.SaveToStream(stm, img_params):
            raise PdfixException("Unable to save the image to the stream")

        img = cv2.imread(img_name)
        # result = layout_analysis(img)

        # ocr_engine = PPStructure(
        # show_log=True,
        # lang="en")
        result = PP_ENGINE(img)

        # Prepare page view for coordinate transformation
        page_crop = page.GetCropBox()
        rotate = page.GetRotate()
        page_width = page_crop.right - page_crop.left
        if rotate in (kRotate90, kRotate270):
            page_width = page_crop.top - page_crop.bottom
        zoom = width / page_width
        page_view = page.AcquirePageView(zoom, 0)

        # Pre-create objects from Paddle engine to the pagemap
        page_map = page.AcquirePageMap()

        # Iterate blocks. It's only one level in this model
        # res_cp = deepcopy(result)
        # save res
        for region in result:
            # roi_img = region.pop("img")
            # f.write("{}\n".format(json.dumps(region)))
            layout_type = region["type"]
            layout_bbox = region["bbox"]
            layout_table_html = (
                region["res"]["html"] if region["type"] == "table" else None
            )

            layout_table_bboxes = (
                region["res"]["cell_bbox"] if region["type"] == "table" else None
            )
            print("Type: {} {}".format(layout_type, layout_bbox))
            if layout_table_html is not None:
                print("{}\n{}".format(layout_table_html, layout_table_bboxes))

            rect = PdfDevRect()
            rect.left = int(region["bbox"][0])
            rect.top = int(region["bbox"][1])
            rect.right = int(region["bbox"][2])
            rect.bottom = int(region["bbox"][3])
            bbox = page_view.RectToPage(rect)

            drawRect(img, rect)

            # Create initial element
            # parent = PdeElement(None)
            pde_elem_type = kPdeText  # text (default)
            if region["type"].lower() == "table":
                pde_elem_type = kPdeTable
            elif region["type"].lower() == "figure":
                pde_elem_type = kPdeImage
            elif region["type"].lower() == "list":
                pde_elem_type = kPdeList
            # elif region["type"].lower() == "equation":
            #     pde_elem_type = kPdeEquation

            elem = page_map.CreateElement(pde_elem_type, None)
            elem.SetBBox(bbox)
            if region["type"].lower() == "title":  # title
                elem.SetTextStyle(kTextH1)
            # elif region["type"].lower() == "table":
            #     updateTableCells(elem, region, page_view, img)

        cv2.imwrite("output.jpg", img)

        # Recognize page
        if not page_map.CreateElements():
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

        # Prepare the struct element for page
        page_elem = doc_struct_elem.AddNewChild(
            "NonStruct",
            doc_struct_elem.GetNumChildren(),
        )
        page_map.AddTags(page_elem, False, PdfTagsParams())

        # Cleanup
        page_view.Release()
        page_map.Release()


def autotag(
    input_path: str,
    output_path: str,
    license_name: str,
    license_key: str,
    lang: str = "en",
) -> None:
    """Run layput recognition using Paddle.

    Parameters
    ----------
    input_path : str
        Input path to the PDF file
    output_path : str
        Output path for saving the PDF file
    license_name : str
        Pdfix SDK license name
    license_key : str
        Pdfix SDK license key
    lang : str, optional
        Language identifier for OCR Paddle. Default value "en"

    """
    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception("Pdfix Initialization fail")

    if license_name and license_key:
        if not pdfix.GetAccountAuthorization().Authorize(license_name, license_key):
            raise Exception("Pdfix Authorization fail")
    else:
        print("No license name or key provided. Using Pdfix trial")

    # Open doc
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception("Unable to open the PDF " + pdfix.GetError())

    # Remove old structure and prepare an empty structure tree
    doc.RemoveTags()
    doc.RemoveStructTree()
    struct_tree = doc.CreateStructTree()
    doc_struct_elem = struct_tree.GetStructElementFromObject(struct_tree.GetObject())

    doc_num_pages = doc.GetNumPages()

    # Process each page
    for i in tqdm(range(0, doc_num_pages), desc="Processing pages"):
        # Acquire page
        page = doc.AcquirePage(i)
        if page is None:
            raise PdfixException("Unable to acquire the page")

        try:
            autotag_page(page, pdfix, doc_struct_elem)
        except Exception as e:
            raise e

        page.Release()

    if not doc.Save(output_path, kSaveFull):
        raise Exception("Unable to save PDF " + pdfix.GetError())
