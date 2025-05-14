import base64
import json

# import os
# from pathlib import Path
import cv2
import numpy as np

from ai import PaddleXEngine


class FormulaDescriptionUsingPaddle:
    def describe_formula(self, input_path: str, output_path: str) -> None:
        """
        Processes a JSON file by extracting a base64-encoded image,
        generating a response using Paddle, and saving the result to an output file.

        Parameters:
            input_path (str): Path to the input JSON file.
            output_path (str): Path to the output JSON file.

        The input JSON file should have the following structure:
        {
            "image": "<base64_encoded_image>"
        }

        The function performs the following steps:
        1. Reads the input JSON file.
        2. Extracts the base64-encoded image.
        3. Passes the image to paddle engine (using formula module)
        4. Saves the response as a dictionary {"text": response} in the output JSON file.
        """
        with open(input_path, "r", encoding="utf-8") as input_file:
            data = json.load(input_file)

        base64_image = data["image"]
        header, encoded = base64_image.split(",", 1)
        image_data = base64.b64decode(encoded)
        numpy_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)

        # image_path = os.path.join(Path(__file__).parent.absolute(), f"../output/formula-{Path(input_path).stem}.png")
        # cv2.imwrite(image_path, image)

        ai = PaddleXEngine()
        formula_rec = ai.process_formula_image_with_ai(image)
        content: dict = {"text": formula_rec}

        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(content, output_file)
