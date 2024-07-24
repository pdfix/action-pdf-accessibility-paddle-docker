from paddleocr import PPStructure


def layout_analysis(img):
    ocr_engine = PPStructure(
        show_log=True,
        lang="en",
        enable_mkldnn=True,  # results may be unstable
        layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
        table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
        det_model_dir="models/det/en_PP-OCRv3_det_infer/",
        rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
    )
    return ocr_engine(img)
