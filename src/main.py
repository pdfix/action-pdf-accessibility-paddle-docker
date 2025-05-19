import argparse
import os
import sys
import traceback
from pathlib import Path

from autotag import AutotagUsingPaddleXRecognition
from formula import FormulaDescriptionUsingPaddle


def set_arguments(
    parser: argparse.ArgumentParser, names: list, required_output: bool = True, file_type: str = "PDF"
) -> None:
    for name in names:
        match name:
            case "input":
                parser.add_argument("--input", "-i", type=str, required=True, help=f"The input {file_type} file")
            case "key":
                parser.add_argument("--key", type=str, help="PDFix license key")
            case "model":
                parser.add_argument(
                    "--model",
                    type=str,
                    choices=["PP-DocLayout-L", "RT-DETR-H_layout_17cls"],
                    default="PP-DocLayout-L",
                    help="Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls",
                )
            case "name":
                parser.add_argument("--name", type=str, help="PDFix license name")
            case "output":
                parser.add_argument(
                    "--output", "-o", type=str, required=required_output, help=f"The output {file_type} file"
                )
            case "zoom":
                parser.add_argument(
                    "--zoom", type=float, default=1.0, help="Zoom level for the PDF page rendering (default: 1.0)"
                )


def run_config_subcommand(args) -> None:
    get_pdfix_config(args.output)


def get_pdfix_config(path: str) -> None:
    """
        If Path is not provided, output content of config.
        If Path is provided, copy config to destination path.

    Args:
        path (string): Destination path for config.json file
    """
    config_path = os.path.join(Path(__file__).parent.absolute(), "../config.json")

    with open(config_path, "r", encoding="utf-8") as file:
        if path is None:
            print(file.read())
        else:
            with open(path, "w") as out:
                out.write(file.read())


def run_autotag_subcommand(args) -> None:
    autotagging_pdf(args.name, args.key, args.input, args.output, args.model, args.zoom)


def autotagging_pdf(
    license_name: str, license_key: str, input_path: str, output_path: str, model: str, zoom: float
) -> None:
    """
        Autotaggin PDF with provided arguments
    Args:
        license_name (string): Name used in authorization in PDFix-SDK
        license_key (string): Key used in authorization in PDFix-SDK
        input_path (string): Path to pdf of folder
        output_path (string): Path to pdf of folder
        model (string): Paddle layout model
    """
    if zoom < 0.1:
        raise Exception("Zoom level must be greater than 0.1")

    if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
        autotag = AutotagUsingPaddleXRecognition(license_name, license_key, input_path, output_path, model, zoom)
        autotag.process_file()
    else:
        raise Exception("Input and output file must be PDF")


def run_formula_subcommand(args) -> None:
    describing_formula(args.input, args.output)


def describing_formula(input_path: str, output_path: str) -> None:
    """
    Taking input and output arguments and passing them to formula description
    that uses Paddle Engine to describe what it sees.

    Args:
        input_path (string): Path to json
        output_path (string): Path to json
    """
    if input_path.lower().endswith(".json") and output_path.lower().endswith(".json"):
        ai = FormulaDescriptionUsingPaddle(input_path, output_path)
        ai.describe_formula()
    else:
        raise Exception("Input and output file must be JSON files")


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
    set_arguments(config_subparser, ["output"], False, "JSON")
    config_subparser.set_defaults(func=run_config_subcommand)

    # Tagging subparser
    autotag_subparser = subparsers.add_parser(
        "tag",
        help="Run autotag PDF document",
    )
    set_arguments(autotag_subparser, ["name", "key", "input", "output", "model", "zoom"], True, "PDF")
    autotag_subparser.set_defaults(func=run_autotag_subcommand)

    # Formula subparser
    formula_subparser = subparsers.add_parser(
        "generate_alt_text_formula",
        help="Generates alternate description for formula using Paddle Engine",
    )
    set_arguments(formula_subparser, ["input", "output"], True, "JSON")
    formula_subparser.set_defaults(func=run_formula_subcommand)

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
    try:
        args.func(args)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        print(f"Failed to run the program: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
