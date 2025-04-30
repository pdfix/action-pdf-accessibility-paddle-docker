import cv2
from paddlex import (
    # create_model,
    create_pipeline,
)


# TODO maybe change name to process pdf page image
def process_image_with_ai(image: cv2.typing.MatLike) -> list:
    """
    Let AI do its magic.

    Args:
        image (cv2.typing.MatLike): Rendered image of PDF page.

    Returns:
        List of recognized elements with data about possition and type.
    """
    # list of some pipelines:
    # - "doc_preprocessor"
    # - "doc_understanding"
    # - "formula_recognition"
    # - "layout_parsing"
    # - "OCR"
    # - "table_recognition"
    # - "table_recognition_v2"
    pipeline = create_pipeline(pipeline="layout_parsing", device="cpu")
    output = pipeline.predict(
        input=image,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        # use_general_ocr=True,
        # use_table_recognition=True,
        # use_formula_recognition=True,
        # layout_threshold=0.5,
        # layout_nms= True,
        # layout_merge_bboxes_mode="large", # "small", "union"
    )

    # list of some models:
    # "PP-DocLayout-L" - large layout model
    # model = create_model(
    #   model_name="PP-DocLayout-L",
    #   device="cpu",
    #   threshold=v{0: 0.45, 2: 0.48, 7: 0.4},
    # )
    # output = model.predict(image, batch_size=1, layout_nms=True)

    # table recognition on table selection (wireless ?? )
    # model = create_model(model_name="RT-DETR-L_wired_table_cell_det")
    # output = model.predict("table_recognition.jpg",  threshold=0.3, batch_size=1)

    for res in output:
        res.print()
        res.save_to_img(save_path="./output/")

    # table recognition V2
    # pipeline = create_pipeline(pipeline="table_recognition_v2")

    # output = pipeline.predict(
    #     input="table_recognition_v2.jpg",
    #     use_doc_orientation_classify=False,
    #     use_doc_unwarping=False,
    # )

    # for res in output:
    #     res.print()
    #     res.save_to_img("./output/")
    #     res.save_to_xlsx("./output/")
    #     res.save_to_html("./output/")
    #     res.save_to_json("./output/")

    # TODO temporary
    return []
