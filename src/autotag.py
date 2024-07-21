import tempfile
from paddleocr import PaddleOCR, PPStructure, draw_structure_result, save_structure_res
from pdfixsdk.Pdfix import (
    GetPdfix,
    Pdfix,
    kSaveFull,
    kRotate0,
    kImageFormatJpg,
    kImageDIBFormatArgb,
    PdfPageRenderParams,
    PdfMatrix,
    kPsTruncate,
    PdfImageParams,
    PdfPage,
    kPdsPageText,
)
from tqdm import tqdm
import utils


class PdfixException(Exception):
    def __init__(self, message: str = ""):
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


"""
def ocr(input_path: str, output_path: str):
    table_engine = PPStructure(
        show_log=True,
        lang="en",
        enable_mkldnn=True,  # results may be unstable
        layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
        table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
        det_model_dir="models/det/en_PP-OCRv3_det_infer/",
        rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
    )

    save_folder = "./data"
    img_path = "1.png"
    img = cv2.imread(img_path)
    result = table_engine(img)
    save_structure_res(result, save_folder, os.path.basename(img_path).split(".")[0])

    for line in result:
        # line.pop("img")
        print(line)

    from PIL import Image

    font_path = "simfang.ttf"  # PaddleOCR
    image = Image.open(img_path).convert("RGB")
    im_show = draw_structure_result(image, result, font_path=font_path)
    im_show = Image.fromarray(im_show)
    im_show.save("data/result.jpg")
"""


def ocr_page(page: PdfPage, pdfix: Pdfix, lang: str) -> bytes:
    """
    Renders a PDF page into a temporary file, which is then used for OCR.

    Parameters
    ----------
    page : PdfPage
        The PDF page to be processed for OCR.
    pdfix : Pdfix
        The Pdfix SDK object.
    lang : str
        The language identifier for OCR.

    Returns
    -------
    bytes
        Raw PDF bytes.
    """
    zoom = 2.0
    pageView = page.AcquirePageView(zoom, kRotate0)
    if pageView is None:
        raise PdfixException("Unable to acquire the page view")

    width = pageView.GetDeviceWidth()
    height = pageView.GetDeviceHeight()
    # Create an image
    image = pdfix.CreateImage(width, height, kImageDIBFormatArgb)
    if image is None:
        raise PdfixException("Unable to create the image")

    # Render page
    renderParams = PdfPageRenderParams()
    renderParams.image = image
    renderParams.matrix = pageView.GetDeviceMatrix()
    if not page.DrawContent(renderParams):
        raise PdfixException("Unable to draw the content")

    # Create temp file for rendering
    with tempfile.NamedTemporaryFile() as tmp:
        # Save image to file
        stm = pdfix.CreateFileStream(tmp.name + ".jpg", kPsTruncate)
        if stm is None:
            raise PdfixException("Unable to create the file stream")

        imgParams = PdfImageParams()
        imgParams.format = kImageFormatJpg
        imgParams.quality = 100
        if not image.SaveToStream(stm, imgParams):
            raise PdfixException("Unable to save the image to the stream")

        ocr = PaddleOCR(use_angle=True, lang="en")
        # ocr = PaddleOCR(
        #    use_angle_cls=True,
        #    det_db_thresh=0.4,
        #    det_db_box_thresh=0.5,
        #    det_db_unclip_ratio=1.4,
        #    max_batch_size=32,
        #    det_limit_side_len=1000,
        #    det_db_score_mode="slow",
        #    dilation=False,
        #    lang="japan",
        #    ocr_version="PP-OCRv4",
        # )
        result = ocr.ocr(tmp.name + ".jpg", cls=True)
        return result


def ocr(
    input_path: str,
    output_path: str,
    license_name: str,
    license_key: str,
    lang: str = "en",
) -> None:
    """
    Run OCR using Paddle.

    Parameters
    ----------
    input_path : str
        Input path to the PDF file.
    output_path : str
        Output path for saving the PDF file.
    license_name : str
        Pdfix SDK license name.
    license_key : str
        Pdfix SDK license key.
    lang : str, optional
        Language identifier for OCR Paddle. Default value "en".
    """
    # Paddleocr supports Chinese, English, French, German, Korean and Japanese.
    # You can set the parameter `lang` as `ch`, `en`, `fr`, `german`, `korean`, `japan`
    # to switch the language model in order.
    print("Using langauge: {}".format(lang))

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

    doc_num_pages = doc.GetNumPages()

    # Process each page
    for i in tqdm(range(0, doc_num_pages), desc="Processing pages"):
        page = doc.AcquirePage(i)
        if page is None:
            raise PdfixException("Unable to acquire the page")

        try:
            result = ocr_page(page, pdfix, lang)
        except Exception as e:
            raise e

        #[[[121.0, 137.0], [682.0, 137.0], [682.0, 200.0], [121.0, 200.0]], ('FAST FACTS', 0.9630950689315796)]
        #[[121.0, 137.0], [682.0, 137.0], [682.0, 200.0], [121.0, 200.0]]
        #FAST FACTS
        #0.9630950689315796

        #[[[110.0, 1398.0], [637.0, 1399.0], [637.0, 1422.0], [110.0, 1421.0]], ('temperature by as much as 4.4C by the end of the century.', 0.9402662515640259)]
        #[[110.0, 1398.0], [637.0, 1399.0], [637.0, 1422.0], [110.0, 1421.0]]
        #temperature by as much as 4.4C by the end of the century.
        #0.9402662515640259

        for idx in range(len(result)):
            res = result[idx]
            for line in res:
                print(line)
                boxes = line[0]
                print(boxes)
                txts = line[1][0]
                print(txts)
                scores = line[1][1]
                print(scores)

        #words = [page[1][0] for page in result[0]]
        #print(words[:10])
        # result.
        # pdf = pytesseract.image_to_pdf_or_hocr(
        #    tmp.name + ".jpg", extension="pdf", lang=lang
        # )
        # return pdf
        # ocr = PaddleOCR(use_angle_cls=True, det_db_thresh = 0.4, det_db_box_thresh = 0.5,det_db_unclip_ratio = 1.4, max_batch_size = 32,
        #        det_limit_side_len = 1000, det_db_score_mode = "slow", dilation = False, lang='japan', ocr_version = "PP-OCRv4")
        # result = ocr.ocr(tmp.name + ".jpg", cls=True)
        """
        temp_path = "_temp.pdf"  # temporary file for pdf generated by the OCR
        with open(temp_path, "w+b") as f:
            f.write(temp_pdf)
        
        temp_doc = pdfix.OpenDoc(temp_path, "")

        if temp_doc is None:
            raise Exception("Unable to open the PDF " + str(pdfix.GetError()))

        # There is always only one page in the new PDF file
        temp_page = temp_doc.AcquirePage(0)
        temp_page_box = temp_page.GetCropBox()

        # Remove other then text page objects from the page content
        temp_page_content = temp_page.GetContent()
        for i in reversed(range(0, temp_page_content.GetNumObjects())):
            obj = temp_page_content.GetObject(i)
            obj_type = obj.GetObjectType()
            if not obj_type == kPdsPageText:
                temp_page_content.RemoveObject(obj)

        temp_page.SetContent()

        xobj = doc.CreateXObjectFromPage(temp_page)
        if xobj is None:
            raise Exception(
                "Failed to create XObject from the page " + str(pdfix.GetError())
            )

        temp_page.Release()
        temp_doc.Close()

        crop_box = page.GetCropBox()
        rotate = page.GetRotate()

        width = crop_box.right - crop_box.left
        width_tmp = temp_page_box.right - temp_page_box.left
        height = crop_box.top - crop_box.bottom
        height_tmp = temp_page_box.top - temp_page_box.bottom

        if rotate == 90 or rotate == 270:
            width_tmp, height_tmp = height_tmp, width_tmp

        scale_x = width / width_tmp
        scale_y = height / height_tmp

        # Calculate matrix for placing xObject on a page
        rotate = (page.GetRotate() / 90) % 4
        matrix = PdfMatrix()
        matrix = utils.PdfMatrixRotate(matrix, rotate * utils.kPi / 2, False)
        matrix = utils.PdfMatrixScale(matrix, scale_x, scale_y, False)
        if rotate == 0:
            matrix = utils.PdfMatrixTranslate(
                matrix, crop_box.left, crop_box.bottom, False
            )
        elif rotate == 1:
            matrix = utils.PdfMatrixTranslate(
                matrix, crop_box.right, crop_box.bottom, False
            )
        elif rotate == 2:
            matrix = utils.PdfMatrixTranslate(
                matrix, crop_box.right, crop_box.top, False
            )
        elif rotate == 3:
            matrix = utils.PdfMatrixTranslate(
                matrix, crop_box.left, crop_box.top, False
            )

        content = page.GetContent()
        form = content.AddNewForm(-1, xobj, matrix)
        if form is None:
            raise Exception(
                "Failed to add XObject to the page " + str(Pdfix.GetError())
            )
    """
    if not doc.Save(output_path, kSaveFull):
        raise Exception("Unable to save PDF " + pdfix.GetError())
