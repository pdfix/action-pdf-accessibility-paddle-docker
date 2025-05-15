import argparse
import os
import shutil
import sys
import traceback
from pathlib import Path

from autotag import AutotagUsingPaddleXRecognition
from formula import FormulaDescriptionUsingPaddle


def add_config_arguments(config_subparser: argparse.ArgumentParser) -> None:
    """
        Add arguments when providing PDFix SDK config json

    Args:
        config_subparser (ArgumentParser): subparser to add arguments
    """
    config_subparser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output to save the config JSON file. Application output\
              is used if not provided",
    )


def add_tagging_arguments(tagging_subparser: argparse.ArgumentParser) -> None:
    """
        Add arguments when autotagging PDF

    Args:
        tagging_subparser (ArgumentParser): subparser to add arguments
    """
    tagging_subparser.add_argument("--name", type=str, default="", help="Pdfix license name")
    tagging_subparser.add_argument("--key", type=str, default="", help="Pdfix license key")
    tagging_subparser.add_argument("-i", "--input", type=str, help="The input PDF file", required=True)
    tagging_subparser.add_argument(
        "-o",
        "--output",
        type=str,
        help="The output PDF file",
        required=True,
    )
    tagging_subparser.add_argument(
        "--model",
        type=str,
        choices=["PP-DocLayout-L", "RT-DETR-H_layout_17cls"],
        default="PP-DocLayout-L",
        help="Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls",
    )


def add_formula_arguments(formula_subparser: argparse.ArgumentParser) -> None:
    """
        Add arguments when using Paddle formula description

    Args:
        formula_subparser (ArgumentParser): subparser to add arguments
    """
    formula_subparser.add_argument("-i", "--input", type=str, help="The input JSON file", required=True)
    formula_subparser.add_argument("-o", "--output", type=str, help="The output JSON file", required=True)


def get_pdfix_config(path: str) -> None:
    """
        If Path is not provided, output content of config.
        If Path is provided, copy config to destination path.

    Args:
        path (string): Destination path for config.json file
    """
    config_path = os.path.join(Path(__file__).parent.absolute(), "../config.json")

    if path is None:
        try:
            # Print content to output
            with open(config_path, "r", encoding="utf-8") as f:
                print(f.read())
        except Exception as e:
            print(f'Problem with reading file "{config_path}": {e}', file=sys.stderr)
            sys.exit(1)
    else:
        try:
            # Copy to provided path
            shutil.copyfile(config_path, path)
        except Exception as e:
            print(f'Problem with copying to path "{path}": {e}', file=sys.stderr)
            sys.exit(1)


def autotagging_pdf(license_name: str, license_key: str, input_path: str, output_path: str, model: str) -> None:
    """
        Autotaggin PDF with provided arguments
    Args:
        license_name (string): Name used in authorization in PDFix-SDK
        license_key (string): Key used in authorization in PDFix-SDK
        input_path (string): Path to pdf of folder
        output_path (string): Path to pdf of folder
        model (string): Paddle layout model
    """
    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
        try:
            autotag = AutotagUsingPaddleXRecognition(license_name, license_key, input_path, output_path, model)
            autotag.process_file()
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            print(f"Failed to run autotagging PDF document: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Input and output file must be PDF", file=sys.stderr)
        sys.exit(1)


def describing_formula(input_path: str, output_path: str) -> None:
    """
    Taking input and output arguments and passing them to formula description
    that uses Paddle Engine to describe what it sees.

    Args:
        input_path (string): Path to json
        output_path (string): Path to json
    """
    if input_path.lower().endswith(".json") and output_path.lower().endswith(".json"):
        try:
            ai = FormulaDescriptionUsingPaddle(input_path, output_path)
            ai.describe_formula()
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            print(f"Failed to run formula description using Paddle: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Input and output file must be JSON files (.json)", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autotag PDF document Paddle Engine and PDFix SDK",
    )

    subparsers = parser.add_subparsers(dest="subparser")

    # Config subparser
    config_subparser = subparsers.add_parser(
        "config",
        help="Extract config file for integration",
    )
    add_config_arguments(config_subparser)

    # Tagging subparser
    tagging_subparser = subparsers.add_parser(
        "tag",
        help="Run autotag PDF document",
    )
    add_tagging_arguments(tagging_subparser)

    # Formula subparser
    formula_subparser = subparsers.add_parser(
        "generate_alt_text_formula",
        help="Generates alternate description for formula using Paddle Engine",
    )
    add_formula_arguments(formula_subparser)

    # Parse arguments
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            # This happens when --help is used, exit gracefully
            sys.exit(0)
        print("Failed to parse arguments. Please check the usage and try again.", file=sys.stderr)
        sys.exit(1)

    # Check which arguments program was called with
    match args.subparser:
        case "config":
            get_pdfix_config(args.output)

        case "tag":
            autotagging_pdf(args.name, args.key, args.input, args.output, args.model)

        case "generate_alt_text_formula":
            describing_formula(args.input, args.output)


if __name__ == "__main__":
    main()
