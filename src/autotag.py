import tempfile

import cv2
from paddleocr import PPStructure
from pdfixsdk import (
    GetPdfix,
    PdeElement,
    PdfDevRect,
    PdfImageParams,
    Pdfix,
    PdfPage,
    PdfPageRenderParams,
    PdfTagsParams,
    PdsStructElement,
    kImageDIBFormatArgb,
    kImageFormatJpg,
    kPdeImage,
    kPdeTable,
    kPdeText,
    kPdeEquation,
    kPsTruncate,
    kRotate0,
    kRotate90,
    kRotate270,
    kSaveFull,
    kTextH1,
)

# from pdfixsdk import *
from tqdm import tqdm

PP_ENGINE = PPStructure(
    show_log=True,
    lang="en",
    enable_mkldnn=True,  # results may be unstable
    layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
    table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
    det_model_dir="models/det/en_PP-OCRv3_det_infer/",
    rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
)


class PdfixException(Exception):
    def __init__(self, message: str = ""):
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


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
    zoom = 2.0
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
        stm = pdfix.CreateFileStream(tmp.name + ".jpg", kPsTruncate)
        if stm is None:
            raise PdfixException("Unable to create the file stream")

        img_params = PdfImageParams()
        img_params.format = kImageFormatJpg
        img_params.quality = 100
        if not image.SaveToStream(stm, img_params):
            raise PdfixException("Unable to save the image to the stream")

        img = cv2.imread(tmp.name + ".jpg")
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

            print(region["type"])
            print(region["bbox"])

            # if (
            #    region["type"].lower() == "table"
            #    and len(region["res"]) > 0
            #    and "html" in region["res"]
            # ):
            #    to_excel(region["res"]["html"], excel_path)
            # elif region["type"].lower() == "figure":
            #    cv2.imwrite(img_path, roi_img)

            # Get image height
            # img_h = img.shape[0]
            # struct_elem['BBox'] = region["bbox"]
            # struct_elem['BBox'] = [b.block.x_1 * scale, (img_h - b.block.y_2) * scale,
            #                       b.block.x_2 * scale, (img_h - b.block.y_1) * scale]

            rect = PdfDevRect()
            rect.left = int(region["bbox"][0])
            rect.top = int(region["bbox"][1])
            rect.right = int(region["bbox"][2])
            rect.bottom = int(region["bbox"][3])
            bbox = page_view.RectToPage(rect)

            # Create initial element
            parent = PdeElement(None)
            pde_elem_type = kPdeText  # text (default)
            if region["type"].lower() == "table":
                pde_elem_type = kPdeTable
            elif region["type"].lower() == "figure":
                pde_elem_type = kPdeImage
            elif region["type"].lower() == "equation":
                pde_elem_type = kPdeEquation

            elem = page_map.CreateElement(pde_elem_type, parent)
            elem.SetBBox(bbox)
            if region["type"].lower() == "title":  # title
                elem.SetTextStyle(kTextH1)

        # Recognize page
        page_map.CreateElements()

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
