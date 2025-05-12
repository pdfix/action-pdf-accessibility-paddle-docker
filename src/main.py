import argparse
import os
import shutil
import sys
import traceback
from pathlib import Path

from autotag import AutotagUsingPaddleXRecognition


def get_config(path: str) -> None:
    """
        If Path is not provided, output content of config.
        If Path is provided, copy config to destination path.

    Args:
        path (string): Destination path for config.json file
    """
    config_path = os.path.join(Path(__file__).parent.absolute(), "../config.json")

    if path is None:
        # Print content to output
        with open(config_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        # Copy to provided path
        shutil.copyfile(config_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a PDF file using Paddle layout recognition",
    )

    # Authorization for PDFix-SDK
    parser.add_argument("--name", type=str, default="", help="Pdfix license name")
    parser.add_argument("--key", type=str, default="", help="Pdfix license key")

    subparsers = parser.add_subparsers(dest="subparser")

    # Config subparser
    config_subparser = subparsers.add_parser(
        "config",
        help="Extract config file for integration",
    )
    config_subparser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output to save the config JSON file. Application output\
              is used if not provided",
    )

    # Tagging subparser
    tagging_subparser = subparsers.add_parser(
        "tag",
        help="Run autotag",
    )

    tagging_subparser.add_argument("-i", "--input", type=str, help="The input PDF file")
    tagging_subparser.add_argument(
        "-o",
        "--output",
        type=str,
        help="The output PDF file",
    )
    tagging_subparser.add_argument(
        "--model",
        type=str,
        choices=["PP-DocLayout-L", "RT-DETR-H_layout_17cls"],
        default="PP-DocLayout-L",
        help="Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls",
    )

    # Parse arguments
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            # This happens when --help is used, exit gracefully
            sys.exit(0)
        print("Failed to parse arguments. Please check the usage and try again.")
        sys.exit(1)

    # Check which arguments program was called with
    match args.subparser:
        case "config":
            # Config found, process config and exit with 0
            get_config(args.output)
            sys.exit(0)

        case "tag":
            # Tagging found, process arguments and autotag PDF
            if not args.input or not args.output:
                parser.error(
                    "The following arguments are required: -i/--input, -o/--output",
                )

            input_path = args.input
            output_path = args.output
            model = args.model

            autotag = AutotagUsingPaddleXRecognition(args.name, args.key, input_path, output_path, model)

            # Start autotagging PDF
            if input_path.lower().endswith(".pdf") and output_path.lower().endswith(".pdf"):
                try:
                    autotag.process_file()
                except Exception as e:
                    print(traceback.format_exc())
                    sys.exit("Failed to run tagging by Paddle: {}".format(e))
            elif Path(input_path).is_dir():
                try:
                    autotag.process_folder()
                except Exception as e:
                    sys.exit("Failed to run tagging by Paddle: {}".format(e))
            else:
                print("Input and output file must be PDF")
                sys.exit(1)


if __name__ == "__main__":
    main()
