import json

# import os
# from pathlib import Path
# import cv2
from ai import PaddleXEngine
from page_renderer import convert_base64_image_to_matlike_image


class FormulaDescriptionUsingPaddle:
    """
    Class that takes care of receiving base64 encoded image in JSON file and processing it through Paddle Engine
    and writing result into output JSON file.
    """

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize class for formula description.

        The input JSON file should have the following structure:
        {
            "image": "<header>,<base64_encoded_image>"
        }

        The output JSON file will look like:
        {
            "content": "MathML ver. 3 description of formula"
        }

        Args:
            input_path (str): Path to the input JSON file.
            output_path (str): Path to the output JSON file.
        """
        self.input_path_str = input_path
        self.output_path_str = output_path

    def describe_formula(self) -> None:
        """
        Processes a JSON file by extracting a base64-encoded image,
        generating a response using Paddle, and saving the result to an output file.

        The function performs the following steps:
        1. Reads the input JSON file.
        2. Extracts the base64-encoded image.
        3. Converts the image data
        3. Passes the image to paddle engine (that uses formula model)
        4. Saves the response as a dictionary {"content": response} in the output JSON file.
        """
        with open(self.input_path_str, "r", encoding="utf-8") as input_file:
            data = json.load(input_file)

        image = convert_base64_image_to_matlike_image(data["image"])

        # image_path = os.path.join(Path(__file__).parent.absolute(), f"../output/formula-{Path(input_path).stem}.png")
        # cv2.imwrite(image_path, image)

        ai = PaddleXEngine()
        mathml_formula = ai.process_formula_image_with_ai(image)
        content: dict = {"content": mathml_formula}

        with open(self.output_path_str, "w", encoding="utf-8") as output_file:
            json.dump(content, output_file)
