import argparse
import os
import re
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Optional

from autotag import AutotagUsingPaddleXRecognition
from constants import IMAGE_FILE_EXT_REGEX, SUPPORTED_IMAGE_EXT
from create_template import CreateTemplateJsonUsingPaddleXRecognition
from generate_mathml import GenerateMathmlFromImage, GenerateMathmlInPdf
from image_update import DockerImageContainerUpdateChecker


def str2bool(value: Any) -> bool:
    """
    Helper function to convert argument to boolean.

    Args:
        value (Any): The value to convert to boolean.

    Returns:
        Parsed argument as boolean.
    """
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise ValueError("Boolean value expected.")


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Helper function to clamp float value.

    Args:
        value (float): Value to be clamped.
        min_value (float): Value will be at least this value.
        max_value (float): Values will be at max this value.

    Returns:
        Clamped value.
    """
    return max(min_value, min(max_value, value))


def set_arguments(
    parser: argparse.ArgumentParser,
    names: list,
    required_output: bool = True,
    input_file_type: str = "PDF",
    output_file_type: str = "PDF",
) -> None:
    """
    Set arguments for the parser based on the provided names and options.

    Args:
        parser (argparse.ArgumentParser): The argument parser to set arguments for.
        names (list): List of argument names to set.
        required_output (bool): Whether the output argument is required. Defaults to True.
        input_file_type (str): The type of input file being processed. Defaults to "PDF".
        output_file_type (str): The type of output file being created. Defaults to "PDF".
    """
    for name in names:
        match name:
            case "input":
                parser.add_argument("--input", "-i", type=str, required=True, help=f"The input {input_file_type} file.")
            case "key":
                parser.add_argument("--key", type=str, default="", nargs="?", help="PDFix license key.")
            case "model":
                parser.add_argument(
                    "--model",
                    type=str,
                    choices=["PP-DocLayout-L", "RT-DETR-H_layout_17cls"],
                    default="PP-DocLayout-L",
                    help="Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls.",
                )
            case "name":
                parser.add_argument("--name", type=str, default="", nargs="?", help="PDFix license name.")
            case "output":
                parser.add_argument(
                    "--output", "-o", type=str, required=required_output, help=f"The output {output_file_type} file."
                )
            case "process_formula":
                parser.add_argument(
                    "--process_formula",
                    type=str2bool,
                    default=True,
                    help="Process formulas in the PDF document using formula model. Default is True.",
                )
            case "process_table":
                parser.add_argument(
                    "--process_table",
                    type=str2bool,
                    default=True,
                    help="Process tables in the PDF document using table models. Default is True.",
                )
            case "threshold_paragraph_title":  # "0"
                parser.add_argument(
                    "--threshold_paragraph_title",
                    type=float,
                    default=0.3,
                    help="Threshold for paragraph title. Value between 0.0 and 1.0. Default is 0.3.",
                )
            case "threshold_image":  # "1"
                parser.add_argument(
                    "--threshold_image",
                    type=float,
                    default=0.5,
                    help="Threshold for image. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_text":  # "2"
                parser.add_argument(
                    "--threshold_text",
                    type=float,
                    default=0.5,
                    help="Threshold for text. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_number":  # "3"
                parser.add_argument(
                    "--threshold_number",
                    type=float,
                    default=0.5,
                    help="Threshold for number. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_abstract":  # "4"
                parser.add_argument(
                    "--threshold_abstract",
                    type=float,
                    default=0.5,
                    help="Threshold for abstract. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_content":  # "5"
                parser.add_argument(
                    "--threshold_content",
                    type=float,
                    default=0.5,
                    help="Threshold for content. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_figure_title":  # "6"
                parser.add_argument(
                    "--threshold_figure_title",
                    type=float,
                    default=0.5,
                    help="Threshold for figure title. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_formula":  # "7"
                parser.add_argument(
                    "--threshold_formula",
                    type=float,
                    default=0.3,
                    help="Threshold for formula. Value between 0.0 and 1.0. Default is 0.3.",
                )
            case "threshold_table":  # "8"
                parser.add_argument(
                    "--threshold_table",
                    type=float,
                    default=0.5,
                    help="Threshold for table. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_table_title":  # "9"
                parser.add_argument(
                    "--threshold_table_title",
                    type=float,
                    default=0.5,
                    help="Threshold for table title. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_reference":  # "10"
                parser.add_argument(
                    "--threshold_reference",
                    type=float,
                    default=0.5,
                    help="Threshold for reference. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_doc_title":  # "11"
                parser.add_argument(
                    "--threshold_doc_title",
                    type=float,
                    default=0.5,
                    help="Threshold for doc title. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_footnote":  # "12"
                parser.add_argument(
                    "--threshold_footnote",
                    type=float,
                    default=0.5,
                    help="Threshold for footnote. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_header":  # "13"
                parser.add_argument(
                    "--threshold_header",
                    type=float,
                    default=0.3,
                    help="Threshold for header. Value between 0.0 and 1.0. Default is 0.3.",
                )
            case "threshold_algorithm":  # "14"
                parser.add_argument(
                    "--threshold_algorithm",
                    type=float,
                    default=0.5,
                    help="Threshold for algorithm. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_footer":  # "15"
                parser.add_argument(
                    "--threshold_footer",
                    type=float,
                    default=0.5,
                    help="Threshold for footer. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_seal":  # "16"
                parser.add_argument(
                    "--threshold_seal",
                    type=float,
                    default=0.3,
                    help="Threshold for seal. Value between 0.0 and 1.0. Default is 0.3.",
                )
            case "threshold_chart_title":  # "17"
                parser.add_argument(
                    "--threshold_chart_title",
                    type=float,
                    default=0.5,
                    help="Threshold for chart title. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_chart":  # "18"
                parser.add_argument(
                    "--threshold_chart",
                    type=float,
                    default=0.5,
                    help="Threshold for chart. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_formula_number":  # "19"
                parser.add_argument(
                    "--threshold_formula_number",
                    type=float,
                    default=0.5,
                    help="Threshold for formula number. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_header_image":  # "20"
                parser.add_argument(
                    "--threshold_header_image",
                    type=float,
                    default=0.3,
                    help="Threshold for header image. Value between 0.0 and 1.0. Default is 0.3.",
                )
            case "threshold_footer_image":  # "21"
                parser.add_argument(
                    "--threshold_footer_image",
                    type=float,
                    default=0.5,
                    help="Threshold for footer image. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "threshold_aside_text":  # "22"
                parser.add_argument(
                    "--threshold_aside_text",
                    type=float,
                    default=0.5,
                    help="Threshold for aside text. Value between 0.0 and 1.0. Default is 0.5.",
                )
            case "zoom":
                parser.add_argument(
                    "--zoom", type=float, default=2.0, help="Zoom level for the PDF page rendering (default: 2.0)."
                )


def run_config_subcommand(args) -> None:
    get_pdfix_config(args.output)


def get_pdfix_config(path: str) -> None:
    """
    If Path is not provided, output content of config.
    If Path is provided, copy config to destination path.

    Args:
        path (str): Destination path for config.json file
    """
    config_path = os.path.join(Path(__file__).parent.absolute(), "../config.json")

    with open(config_path, "r", encoding="utf-8") as file:
        if path is None:
            print(file.read())
        else:
            with open(path, "w") as out:
                out.write(file.read())


def run_autotag_subcommand(args) -> None:
    thresholds = create_threshold_dictionary(args)
    autotagging_pdf(
        args.name,
        args.key,
        args.input,
        args.output,
        args.model,
        args.zoom,
        args.process_formula,
        args.process_table,
        thresholds,
    )


def autotagging_pdf(
    license_name: Optional[str],
    license_key: Optional[str],
    input_path: str,
    output_path: str,
    model: str,
    zoom: float,
    process_formula: bool,
    process_table: bool,
    thresholds: dict,
) -> None:
    """
    Autotagging PDF document with provided arguments

    Args:
        license_name (Optional[str]): Name used in authorization in PDFix-SDK.
        license_key (Optional[str]): Key used in authorization in PDFix-SDK.
        input_path (str): Path to PDF document.
        output_path (str): Path to PDF document.
        model (str): Paddle layout model.
        zoom (float): Zoom level for rendering the page.
        process_formula (bool): Whether to process formulas.
        process_table (bool): Whether to process tables.
        thresholds (dict): Thresholds for layout detection.
    """
    if zoom < 1.0 or zoom > 10.0:
        raise Exception("Zoom level must between 1.0 and 10.0")

    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
        autotag = AutotagUsingPaddleXRecognition(
            license_name, license_key, input_path, output_path, model, zoom, process_formula, process_table, thresholds
        )
        autotag.process_file()
    else:
        raise Exception("Input and output file must be PDF documents")


def run_template_subcommand(args) -> None:
    thresholds = create_threshold_dictionary(args)
    create_template_json(
        args.name, args.key, args.input, args.output, args.model, args.zoom, args.process_table, thresholds
    )


def create_template_json(
    license_name: Optional[str],
    license_key: Optional[str],
    input_path: str,
    output_path: str,
    model: str,
    zoom: float,
    process_table: bool,
    thresholds: dict,
) -> None:
    """
    Creating template json for PDF document using provided arguments

    Args:
        license_name (Optional[str]): Name used in authorization in PDFix-SDK.
        license_key (Optional[str]): Key used in authorization in PDFix-SDK.
        input_path (str): Path to PDF document.
        output_path (str): Path to JSON file.
        model (str): Paddle layout model.
        zoom (float): Zoom level for rendering the page.
        process_table (bool): Whether to process tables.
        thresholds (dict): Thresholds for layout detection.
    """
    if zoom < 1.0 or zoom > 10.0:
        raise Exception("Zoom level must between 1.0 and 10.0")

    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".json"):
        template_creator = CreateTemplateJsonUsingPaddleXRecognition(
            license_name, license_key, input_path, output_path, model, zoom, process_table, thresholds
        )
        template_creator.process_file()
    else:
        raise Exception("Input file must be PDF and output file must be JSON")


def run_mathml_subcommand(args) -> None:
    formula_to_mathml(args.name, args.key, args.input, args.output)


def formula_to_mathml(
    license_name: Optional[str], license_key: Optional[str], input_path: str, output_path: str
) -> None:
    """
    Processing all formulas in PDF document and adding Associate Files to them.

    Args:
        license_name (Optional[str]): Name used in authorization in PDFix-SDK.
        license_key (Optional[str]): Key used in authorization in PDFix-SDK.
        input_path (str): Path to PDF document.
        output_path (str): Path to PDF document.
    """
    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
        generateMathml = GenerateMathmlInPdf(license_name, license_key, input_path, output_path)
        generateMathml.process_file()
    elif re.search(IMAGE_FILE_EXT_REGEX, input_path, re.IGNORECASE) and output_path.lower().endswith(".xml"):
        ai = GenerateMathmlFromImage(input_path, output_path)
        ai.process_image()
    else:
        raise Exception('See "mathml --help" for allowed file combinations')


def create_threshold_dictionary(args) -> dict:
    """
    Create a dictionary of threshold values from the provided arguments.

    Args:
        args (argparse.Namespace): Parsed command line arguments.

    Returns:
        dict: Dictionary containing threshold values.
    """
    return {
        0: clamp(float(args.threshold_paragraph_title), 0.05, 0.95),
        1: clamp(float(args.threshold_image), 0.05, 0.95),
        2: clamp(float(args.threshold_text), 0.05, 0.95),
        3: clamp(float(args.threshold_number), 0.05, 0.95),
        4: clamp(float(args.threshold_abstract), 0.05, 0.95),
        5: clamp(float(args.threshold_content), 0.05, 0.95),
        6: clamp(float(args.threshold_figure_title), 0.05, 0.95),
        7: clamp(float(args.threshold_formula), 0.05, 0.95),
        8: clamp(float(args.threshold_table), 0.05, 0.95),
        9: clamp(float(args.threshold_table_title), 0.05, 0.95),
        10: clamp(float(args.threshold_reference), 0.05, 0.95),
        11: clamp(float(args.threshold_doc_title), 0.05, 0.95),
        12: clamp(float(args.threshold_footnote), 0.05, 0.95),
        13: clamp(float(args.threshold_header), 0.05, 0.95),
        14: clamp(float(args.threshold_algorithm), 0.05, 0.95),
        15: clamp(float(args.threshold_footer), 0.05, 0.95),
        16: clamp(float(args.threshold_seal), 0.05, 0.95),
        17: clamp(float(args.threshold_chart_title), 0.05, 0.95),
        18: clamp(float(args.threshold_chart), 0.05, 0.95),
        19: clamp(float(args.threshold_formula_number), 0.05, 0.95),
        20: clamp(float(args.threshold_header_image), 0.05, 0.95),
        21: clamp(float(args.threshold_footer_image), 0.05, 0.95),
        22: clamp(float(args.threshold_aside_text), 0.05, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autotag PDF document Paddle Engine and PDFix SDK",
    )

    subparsers = parser.add_subparsers(dest="subparser")

    threshold_arguments = [
        "threshold_paragraph_title",
        "threshold_image",
        "threshold_text",
        "threshold_number",
        "threshold_abstract",
        "threshold_content",
        "threshold_figure_title",
        "threshold_formula",
        "threshold_table",
        "threshold_table_title",
        "threshold_reference",
        "threshold_doc_title",
        "threshold_footnote",
        "threshold_header",
        "threshold_algorithm",
        "threshold_footer",
        "threshold_seal",
        "threshold_chart_title",
        "threshold_chart",
        "threshold_formula_number",
        "threshold_header_image",
        "threshold_footer_image",
        "threshold_aside_text",
    ]

    # Config subparser
    config_subparser = subparsers.add_parser(
        "config",
        help="Extract config file for integration.",
    )
    set_arguments(config_subparser, ["output"], False, "JSON", "JSON")
    config_subparser.set_defaults(func=run_config_subcommand)

    # Tagging subparser
    autotag_subparser = subparsers.add_parser(
        "tag",
        help="Run AutoTag of PDF document.",
    )
    tagging_arguments = ["name", "key", "input", "output", "model", "zoom", "process_formula", "process_table"]
    set_arguments(autotag_subparser, tagging_arguments + threshold_arguments, True, "PDF", "PDF")
    autotag_subparser.set_defaults(func=run_autotag_subcommand)

    # Template subparser
    template_subparser = subparsers.add_parser(
        "template",
        help="Create layout template JSON.",
    )
    template_arguments = ["name", "key", "input", "output", "model", "zoom", "process_table"]
    set_arguments(template_subparser, template_arguments + threshold_arguments, True, "PDF", "JSON")
    template_subparser.set_defaults(func=run_template_subcommand)

    # MathML subparser
    mathml_help = "Generate MathML representation of formula. Support 2 modes."
    mathml_help += " First mode takes PDF and processes all Formula tags."
    mathml_help += " Second mode takes image and outputs XML file with MathML representation of formula in image."
    mathml_help += f" Supported image files are: {SUPPORTED_IMAGE_EXT}."
    mathml_subparser = subparsers.add_parser("mathml", help=mathml_help)
    set_arguments(mathml_subparser, ["name", "key", "input", "output"], True, "PDF or IMG", "PDF or XML")
    mathml_subparser.set_defaults(func=run_mathml_subcommand)

    # Parse arguments
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            # This happens when --help is used, exit gracefully
            sys.exit(0)
        print("Failed to parse arguments. Please check the usage and try again.", file=sys.stderr)
        sys.exit(e.code)

    if hasattr(args, "func"):
        # Check for updates only when help is not checked
        update_checker = DockerImageContainerUpdateChecker()
        # Check it in separate thread not to be delayed when there is slow or no internet connection
        update_thread = threading.Thread(target=update_checker.check_for_image_updates)
        update_thread.start()

        # Run subcommand
        try:
            args.func(args)
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            print(f"Failed to run the program: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            # Make sure to let update thread finish before exiting
            update_thread.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
