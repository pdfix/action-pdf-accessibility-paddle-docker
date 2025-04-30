import cv2
from paddleocr import PPStructure

# In top part of source code paddleocr/paddleocr.py is list of all available
# models (AKA Model Zoo).
# During paddleocr update please check if there are newer models.
# Latest models can also be found:
# https://paddlepaddle.github.io/PaddleOCR/main/en/ppstructure/models_list.html

# Good source of what to expect from Paddle:
# https://medium.com/adevinta-tech-blog/deep-dive-in-paddleocr-inference-e86f618a0937

# Architecture:
# https://paddlepaddle.github.io/PaddleOCR/main/en/ppstructure/overview.html#1-introduction

# Parameters documentations:
# https://github.com/PaddlePaddle/PaddleOCR/blob/18ddb6d5f9bdc2c1b0aa7f6e399ec0f76119dc87/doc/doc_en/inference_args_en.md
# https://github.com/heyudage/PaddleOCR-DBnetClf/blob/master/ppstructure/docs/quickstart_en.md
# https://github.com/Mushroomcat9998/PaddleOCR/blob/main/doc/doc_en/quickstart_en.md

PP_ENGINE = PPStructure(
    # Global parameters:
    # drop_score=0.5,
    # use_mp=False,  # enable multi-process
    # total_process_num=6,
    show_log=True,
    # use_onnx=False,  # enable onnx prediction

    # Prediction engine parameters:
    # use_gpu=False,
    # enable_mkldnn=False,  # results may be unstable
    # cpu_threads=10,  # when mkldnn is enabled, number of threads

    # Text detection model parameters:
    # det=True,
    det_model_dir="models/det/en_PP-OCRv3_det_infer/",
    # det_algorithm="DB",
    # det_limit_side_len=960,
    # det_limit_type="max",

    # DB algorithm parameters:
    # det_db_thresh=0.3,
    # det_db_box_thresh= 0.5,
    # det_db_unclip_ratio= 1.5,
    # det_db_score_mode="fast",

    # SAST algorithm parameters:
    # det_sast_score_thresh=0.5,
    # det_sast_nms_thresh=0.2,
    # det_sast_polygon=False,

    # PSE algoritm parameters
    # det_pse_thresh=0,
    # det_pse_box_thresh=0.85,
    # det_pse_min_area=16,
    # det_pse_box_type="quad",
    # det_pse_scale=1,

    # Text recognition model parameters:
    # rec=True,
    rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
    # rec_algorithm="SVTR_LCNet",
    # rec_image_shape="3, 48, 320",
    # rec_batch_num=6,
    # max_text_length=25,
    # rec_char_dict_path="./ppocr/utils/ppocr_keys_v1.txt"
    # use_space_char=True,

    # Not documented parameters:

    # layout=True,
    layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
    # layout_dict_path=None,
    layout_score_threshold=0.1,  # default 0.5
    layout_nms_threshold=0.1,  # default 0.5

    # table=True,
    table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
    # table_max_len=488,
    # table_algorithm="TableAttn",
    # table_char_dict_path=None,

    formula_model_dir="models/formula/rec_latex_ocr_infer/",

    lang="en",
    # kie_algorithm="LayoutXLM",
    # set_model_dir=None,
    # ser_dict_path="train_data/XFUND/class_list_xfun.txt",
    # ocr=True,
    # ocr_order_method=None,
    # type="ocr",
    # ocr_version="PP-OCRv3",
    # mode="structure",
    # structure_version="PP-Structurev2",
    # image_orientation=False,
)


def process_image_with_ai(image: cv2.typing.MatLike) -> list:
    """
    Let AI do its magic.

    Args:
        image (cv2.typing.MatLike): Rendered image of PDF page.

    Returns:
        List of recognized elements with data about possition and type.
    """
    results: list = PP_ENGINE(image)
    
    return results
