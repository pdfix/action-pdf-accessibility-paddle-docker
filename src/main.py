import argparse
import json
import logging
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from autotag import AutotagUsingPaddleXRecognition
from constants import CONFIG_FILE, SUPPORTED_IMAGE_EXT
from create_template import CreateTemplateJsonUsingPaddleXRecognition
from exceptions import (
    EC_ARG_GENERAL,
    MESSAGE_ARG_GENERAL,
    MESSAGE_ARG_OUTPUT_NOT_JSON,
    MESSAGE_ARG_OUTPUT_NOT_PDF,
    MESSAGE_ARG_OUTPUT_NOT_PDF_OR_XML,
    ArgumentInputNotImageException,
    ArgumentInputNotPdfException,
    ArgumentOutputExtensionException,
    ArgumentOutputFolderNotExistsException,
    ArgumentZoomException,
    ExpectedException,
    InvalidRegexOrTemplateException,
)
from generate_mathml import GenerateMathmlFromImage, GenerateMathmlInPdf
from image_update import DockerImageContainerUpdateChecker
from logger import get_logger
from params_parser import ParamsParser

logger: logging.Logger = get_logger("app_logger")

DEFAULT_TAGS_MATHML: str = "Formula"


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
            case "password":
                parser.add_argument(
                    "--password", type=str, default="", help="Password to open a password-protected PDF document."
                )
            case "params":
                parser.add_argument(
                    "--params",
                    type=str,
                    required=False,
                    help="Path to JSON file with tag filter parameters (required for PDF → PDF).",
                )
            case "overwrite":
                parser.add_argument(
                    "--overwrite",
                    type=str2bool,
                    default=False,
                    help=(
                        "Overwrite existing MathML associated file for the current version "
                        "(PDF → PDF only). Default is false."
                    ),
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
                    "--zoom",
                    type=float,
                    default=2.0,
                    help="Zoom level for the PDF page rendering, from 1.0 to 4.0 (default: 2.0).",
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
    config_path: Path = Path(__file__).parent.parent.joinpath(CONFIG_FILE).resolve()
    with open(config_path, "r", encoding="utf-8") as file:
        if path is None:
            print(file.read())
        else:
            with open(path, "w") as out:
                out.write(file.read())


def check_output_file(output_path: str, extensions: tuple[str, ...], message: str) -> str:
    """
    Check the output file extension and that its folder exists before any processing.

    Args:
        output_path (str): Path to the output file.
        extensions (tuple[str, ...]): Allowed lowercase extensions, for example (".pdf",).
        message (str): Error message when the extension is not allowed.

    Returns:
        Lowercase extension of the output file.
    """
    extension: str = Path(output_path).suffix.lower()
    if extension not in extensions:
        raise ArgumentOutputExtensionException(message)
    output_folder: Path = Path(output_path).resolve().parent
    if not output_folder.is_dir():
        raise ArgumentOutputFolderNotExistsException(output_folder.as_posix())
    return extension


def check_input_pdf(input_path: str) -> None:
    """
    Check that the input is an existing PDF file.

    Args:
        input_path (str): Path to the input PDF file.
    """
    path: Path = Path(input_path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise ArgumentInputNotPdfException(input_path)


def check_input_image(input_path: str) -> None:
    """
    Check that the input is an existing image file (JPG, JPEG, PNG or BMP).

    Args:
        input_path (str): Path to the input image file.
    """
    path: Path = Path(input_path)
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXT.split() or not path.is_file():
        raise ArgumentInputNotImageException(input_path)


def check_zoom(zoom: float) -> None:
    """
    Check the rendering zoom level.

    Args:
        zoom (float): Zoom level for rendering the page.
    """
    if zoom < 1.0 or zoom > 4.0:
        raise ArgumentZoomException()


# @KA:action pdfix_autotag_paddle
# @KA:desc Tags a PDF document using Paddle AI models: every page is rendered as an image, the Paddle layout model finds
# headings, paragraphs, lists, tables, images, formulas, headers and footers, and PDFix SDK tags the document from this
# layout. Tables and formulas can be recognized in detail. The input file is not changed; the result is saved as the
# output file.
# @KA:context Use it to tag untagged PDFs, scanned PDFs with OCR text or PDFs with formulas and tables. Runs locally in
# Docker and nothing leaves your computer; the first run downloads the image (about 5 GB) and takes longer.
# @KA:param input_pdf
# @KA:desc PDF document to process. It is only read, never changed.
# @KA:problem "Input file must be an existing PDF document." (error 14)
# @KA:solution The file shown in the message was not found or does not have the `.pdf` extension. Select an existing PDF
# file.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 30" (error 24)
# @KA:solution The file is not a valid PDF. Open and save it again in a PDF editor and run the action again.
# @KA:problem "PDF document is password-protected. Remove the password with another action first." (error 32)
# @KA:solution The PDF needs a password to open. Remove the password with another action or in a PDF editor and run the
# action again. From the command line, pass the password with `--password`.
# @KA:param output_pdf
# @KA:desc Where the tagged PDF is saved, a file with the `.pdf` extension. The folder must already exist; an existing
# file with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be PDF document." (error 16)
# @KA:solution Select an output file with the `.pdf` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:param model
# @KA:desc Paddle layout model that finds the regions of each page. PP-DocLayout-L (default) knows 23 region types,
# including charts, chart titles, seals, header and footer images and aside text. RT-DETR-H_layout_17cls knows 17 types;
# the thresholds of the other 6 types are not used with it.
# @KA:param zoom
# @KA:desc Zoom level used to render pages for recognition, from 1.0 to 4.0 (default 2.0). A higher zoom can help with
# small text and dense tables and takes longer.
# @KA:problem "Zoom level must be between 1.0 and 4.0." (error 17)
# @KA:solution Enter a zoom level from 1.0 to 4.0.
# @KA:param process_formula
# @KA:desc When on (default), every detected formula is recognized by the Paddle formula model and its MathML is
# attached to the `Formula` tag as an associated file, like Set Formula MathML (Paddle) does. When off, formulas are
# tagged without MathML.
# @KA:param process_table
# @KA:desc When on (default), every detected table is recognized by the Paddle table models (wired or wireless table,
# then cells), so the table gets rows, columns and merged cells. When off, the table area is tagged without its cell
# structure.
# @KA:param threshold_paragraph_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting headings, tagged `H1`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting images, tagged `Figure`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_text
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting paragraphs, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_number
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting page numbers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_abstract
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting abstracts, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_content
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting tables of contents, tagged `P`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_figure_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting figure titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_formula
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting formulas, tagged `Formula`. A lower value
# finds more of them but also wrong ones.
# @KA:param threshold_table
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting tables, tagged `Table`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_table_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting table titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_reference
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting references, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_doc_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting the document title, tagged `Title`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_footnote
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting footnotes, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_header
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting page headers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_algorithm
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting algorithms, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_footer
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting page footers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_seal
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting seals and stamps, artifacts. A lower value
# finds more of them but also wrong ones.
# @KA:param threshold_chart_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting chart titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_chart
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting charts, tagged `Figure`. A lower value finds
# more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_formula_number
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting formula numbers, tagged `P`. A lower value
# finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_header_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting images in page headers, artifacts. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_footer_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting images in page footers, artifacts. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_aside_text
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting side notes, artifacts. A lower value finds
# more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:logic Detection thresholds
# @KA:desc Each region type has its own threshold. Lower it when regions of a type are missed, raise it when other
# content is wrongly detected as that type. A value outside 0.05 to 0.95 is changed to the nearest limit and the log
# shows a warning.
# @KA:logic Existing tags
# @KA:desc The whole document is tagged from scratch: the old structure tree and all old tags are removed first, nothing
# of them is kept.
# @KA:problem "Failed to tag PDF document." (error 26)
# @KA:solution PDFix SDK could not tag the document with the detected layout. Try Create Layout Template JSON (Paddle),
# check the template in the template editor and tag with AutoTag (PDFix).
# @KA:logic How detected regions become tags
# @KA:desc Text becomes `P`; every heading becomes `H1`, because Paddle gives no heading levels; the document title
# becomes `Title`; figure, table and chart titles become `Caption`; images and charts become `Figure` without alternate
# text; tables keep rows, columns and merged cells; formulas become `Formula` without alternate text; headers, footers,
# page numbers, header and footer images, side notes and seals become artifacts.
# @KA:problem All headings have level 1 (`H1`).
# @KA:solution Paddle detects headings but not their levels. Set the heading levels in PDFix Desktop afterwards.
# @KA:problem Figures or formulas have no alternate text.
# @KA:solution The action does not describe images or formulas. Use Set Alternate Description (BLIP AI) for figures and
# write the alternate text of formulas manually.
# @KA:logic Page rendering
# @KA:desc Each page is rendered into the JPG image `paddle_page_<n>.jpg` in the working folder with the selected
# **Rendering Zoom Level** and deleted after it is read.
# @KA:problem "Failed to render PDF Page into image." (error 23)
# @KA:solution The page cannot be drawn by PDFix SDK. Open and save the PDF again in a PDF editor and run the action
# again.
# @KA:logic PDFix license
# @KA:desc PDFix Desktop passes your PDFix license to the action automatically. Without a license the action runs in
# trial mode, which adds watermarks and may redact random content in the output PDF.
# @KA:problem The output PDF has watermarks or randomly redacted content.
# @KA:solution Trial mode is active. Activate your PDFix license in PDFix Desktop and run the action again.
# @KA:problem "Failed to authorize PDFix SDK account." and the next log line shows "PDFix SDK error 420" (error 22)
# @KA:solution The license name or key is not valid. Check the license in PDFix Desktop settings.
# @KA:problem "Failed to activate PDFix SDK account." and the next log line shows "PDFix SDK error 1205" (error 21)
# @KA:solution The license key is not valid. Check the license in PDFix Desktop settings.
def run_autotag_subcommand(args) -> None:
    check_output_file(args.output, (".pdf",), MESSAGE_ARG_OUTPUT_NOT_PDF)
    check_input_pdf(args.input)
    check_zoom(args.zoom)
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
        args.password,
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
    password: str = "",
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
        password (str): Password of the PDF document, empty when it has none.
    """
    autotag = AutotagUsingPaddleXRecognition(
        license_name,
        license_key,
        input_path,
        output_path,
        model,
        zoom,
        process_formula,
        process_table,
        thresholds,
        password,
    )
    autotag.process_file()


# @KA:action pdfix_create_layout_template_json_paddle
# @KA:desc Creates a PDFix layout template JSON from the page layout that the Paddle AI models find: headings,
# paragraphs, tables with cells, images, formulas, headers and footers. The PDF is not changed and not tagged.
# @KA:context Use it to check or edit the detected layout in the template editor before tagging, for example with
# AutoTag (PDFix). Runs locally in Docker and nothing leaves your computer; the first run downloads the image (about 5
# GB) and takes longer. The template is created in PDFix SDK trial mode, which does not affect the template.
# @KA:param input_pdf
# @KA:desc PDF document to process. It is only read, never changed.
# @KA:problem "Input file must be an existing PDF document." (error 14)
# @KA:solution The file shown in the message was not found or does not have the `.pdf` extension. Select an existing PDF
# file.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 30" (error 24)
# @KA:solution The file is not a valid PDF. Open and save it again in a PDF editor and run the action again.
# @KA:problem "PDF document is password-protected. Remove the password with another action first." (error 32)
# @KA:solution The PDF needs a password to open. Remove the password with another action or in a PDF editor and run the
# action again. From the command line, pass the password with `--password`.
# @KA:param output_json
# @KA:desc Where the layout template is saved, a file with the `.json` extension. The folder must already exist; an
# existing file with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be JSON file." (error 16)
# @KA:solution Select an output file with the `.json` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:param model
# @KA:desc Paddle layout model that finds the regions of each page. PP-DocLayout-L (default) knows 23 region types,
# including charts, chart titles, seals, header and footer images and aside text. RT-DETR-H_layout_17cls knows 17 types;
# the thresholds of the other 6 types are not used with it.
# @KA:param zoom
# @KA:desc Zoom level used to render pages for recognition, from 1.0 to 4.0 (default 2.0). A higher zoom can help with
# small text and dense tables and takes longer.
# @KA:problem "Zoom level must be between 1.0 and 4.0." (error 17)
# @KA:solution Enter a zoom level from 1.0 to 4.0.
# @KA:param process_table
# @KA:desc When on (default), every detected table is recognized by the Paddle table models (wired or wireless table,
# then cells), so the table gets rows, columns and merged cells. When off, the table area is tagged without its cell
# structure.
# @KA:param threshold_paragraph_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting headings, tagged `H1`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting images, tagged `Figure`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_text
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting paragraphs, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_number
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting page numbers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_abstract
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting abstracts, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_content
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting tables of contents, tagged `P`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_figure_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting figure titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_formula
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting formulas, tagged `Formula`. A lower value
# finds more of them but also wrong ones.
# @KA:param threshold_table
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting tables, tagged `Table`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_table_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting table titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_reference
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting references, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_doc_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting the document title, tagged `Title`. A lower
# value finds more of them but also wrong ones.
# @KA:param threshold_footnote
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting footnotes, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_header
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting page headers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_algorithm
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting algorithms, tagged `P`. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_footer
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting page footers, artifacts. A lower value finds
# more of them but also wrong ones.
# @KA:param threshold_seal
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting seals and stamps, artifacts. A lower value
# finds more of them but also wrong ones.
# @KA:param threshold_chart_title
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting chart titles, tagged `Caption`. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_chart
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting charts, tagged `Figure`. A lower value finds
# more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_formula_number
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting formula numbers, tagged `P`. A lower value
# finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_header_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.3) for detecting images in page headers, artifacts. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_footer_image
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting images in page footers, artifacts. A lower
# value finds more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:param threshold_aside_text
# @KA:desc Minimum confidence from 0.05 to 0.95 (default 0.5) for detecting side notes, artifacts. A lower value finds
# more of them but also wrong ones. Used only with PP-DocLayout-L.
# @KA:logic Detection thresholds
# @KA:desc Each region type has its own threshold. Lower it when regions of a type are missed, raise it when other
# content is wrongly detected as that type. A value outside 0.05 to 0.95 is changed to the nearest limit and the log
# shows a warning.
# @KA:logic Template content
# @KA:desc The template has one `element_create` rule per page with the detected regions in PDF coordinates, and
# metadata with the image version, the layout model and the zoom. Formulas are not recognized in the template.
# @KA:problem "Failed to create template JSON." (error 27)
# @KA:solution The template could not be created from the detected layout. Run the action again; if it fails again, send
# the log to PDFix support.
# @KA:logic How detected regions become tags
# @KA:desc Text becomes `P`; every heading becomes `H1`, because Paddle gives no heading levels; the document title
# becomes `Title`; figure, table and chart titles become `Caption`; images and charts become `Figure` without alternate
# text; tables keep rows, columns and merged cells; formulas become `Formula` without alternate text; headers, footers,
# page numbers, header and footer images, side notes and seals become artifacts.
def run_template_subcommand(args) -> None:
    check_output_file(args.output, (".json",), MESSAGE_ARG_OUTPUT_NOT_JSON)
    check_input_pdf(args.input)
    check_zoom(args.zoom)
    thresholds = create_threshold_dictionary(args)
    create_template_json(
        args.name,
        args.key,
        args.input,
        args.output,
        args.model,
        args.zoom,
        args.process_table,
        thresholds,
        args.password,
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
    password: str = "",
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
        password (str): Password of the PDF document, empty when it has none.
    """
    template_creator = CreateTemplateJsonUsingPaddleXRecognition(
        license_name, license_key, input_path, output_path, model, zoom, process_table, thresholds, password
    )
    template_creator.process_file()


# @KA:action pdfix_generate_formula_mathml_paddle
# @KA:desc Recognizes the formulas of a tagged PDF with the Paddle formula model and attaches the result as MathML 3 to
# each selected tag as an associated file. The area of each tag is rendered as an image, recognized as LaTeX and
# converted to MathML. The input file is not changed; the result is saved as the output file.
# @KA:context Use it on a tagged PDF whose `Formula` tags need MathML, for example for PDF/UA-2 or for assistive
# technology that reads MathML. Runs locally in Docker and nothing leaves your computer; the first run downloads the
# image (about 5 GB) and takes longer.
# @KA:param input_pdf
# @KA:desc PDF document to process. It is only read, never changed.
# @KA:problem "Input file must be an existing PDF document." (error 14)
# @KA:solution The file shown in the message was not found or does not have the `.pdf` extension. Select an existing PDF
# file.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 30" (error 24)
# @KA:solution The file is not a valid PDF. Open and save it again in a PDF editor and run the action again.
# @KA:problem "PDF document has no tags." (error 28)
# @KA:solution The PDF is not tagged. Tag it first, for example with AutoTag (Paddle), and run the action again.
# @KA:problem "PDF document is password-protected. Remove the password with another action first." (error 32)
# @KA:solution The PDF needs a password to open. Remove the password with another action or in a PDF editor and run the
# action again. From the command line, pass the password with `--password`.
# @KA:param output_pdf
# @KA:desc Where the PDF with MathML is saved, a file with the `.pdf` extension. The folder must already exist; an
# existing file with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be PDF document or XML file." (error 16)
# @KA:solution Select an output file with the `.pdf` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:param overwrite
# @KA:desc When off (default), tags that already have a MathML 3 associated file keep it. When on, it is replaced by the
# new MathML.
# @KA:param tag_names
# @KA:desc Which tags get MathML: a regular expression of tag types (default `Formula`), or a template `tag_update` that
# selects tags by their properties.
# @KA:problem "Missing or invalid parameters." (error 12)
# @KA:solution The parameters from PDFix Desktop could not be read or do not contain **Tags**. Select the tags again and
# run the action again.
# @KA:problem "Invalid regex or template. Please check the usage and try again." (error 11)
# @KA:solution **Tags** is neither a regular expression nor a template. Enter a regular expression such as `Formula`.
# @KA:problem "Failed to load template file." (error 29)
# @KA:solution PDFix SDK cannot read the regular expression or template of **Tags**. Check it and run the action again.
# @KA:logic MathML associated file
# @KA:desc The MathML is attached like PDFix Desktop does: file `mathml-3.xml`, description "Presentation MathML
# alternative for Formula", AFRelationship `Supplement`, type `application/mathml+xml`. The MathML is wrapped in
# `semantics` with the annotation "Generated by Paddle". Each tag is rendered at zoom 1 from its bounding box on its
# first page. When no formula is recognized, the tag keeps its MathML and the log shows a warning.
# @KA:problem A formula has no MathML and the log says that no formula was recognized or the bounding box is missing.
# @KA:solution The formula model could not read the area of the tag, or the tag has no content on a page. Check that the
# tag contains the formula and write the MathML manually if needed.
# @KA:problem The MathML does not match the formula.
# @KA:solution Formula recognition makes mistakes, mostly with handwritten, very small or complex formulas. Check the
# MathML and correct it manually.
# @KA:logic PDFix license
# @KA:desc PDFix Desktop passes your PDFix license to the action automatically. Without a license the action runs in
# trial mode, which adds watermarks and may redact random content in the output PDF.
# @KA:problem The output PDF has watermarks or randomly redacted content.
# @KA:solution Trial mode is active. Activate your PDFix license in PDFix Desktop and run the action again.
# @KA:problem "Failed to authorize PDFix SDK account." and the next log line shows "PDFix SDK error 420" (error 22)
# @KA:solution The license name or key is not valid. Check the license in PDFix Desktop settings.
# @KA:problem "Failed to activate PDFix SDK account." and the next log line shows "PDFix SDK error 1205" (error 21)
# @KA:solution The license key is not valid. Check the license in PDFix Desktop settings.
# @KA:action pdfix_generate_formula_mathml_from_image_to_xml_paddle
# @KA:desc Recognizes the formula in an image file with the Paddle formula model and saves it as MathML 3 in an XML
# file.
# @KA:context PDFix Desktop runs it for a selected `Formula` tag: the tag is rendered into an image, recognized, and the
# MathML is attached to the tag. Runs locally in Docker and nothing leaves your computer; the first run downloads the
# image (about 5 GB) and takes longer.
# @KA:param input_jpg
# @KA:desc Image of one formula (JPG; the action also accepts JPEG, PNG and BMP).
# @KA:problem "Input file must be an existing image file (JPG, JPEG, PNG or BMP)." (error 15)
# @KA:solution The file shown in the message was not found or is not an image of a supported type.
# @KA:problem "Failed to read image file." (error 30)
# @KA:solution The image is damaged or is not really an image. Save it again as JPG or PNG.
# @KA:problem "No formula was recognized in the image." (error 31)
# @KA:solution The formula model found nothing in the image. Use an image that shows only the formula. An almost empty
# image can still give a formula such as `=`.
# @KA:param output_xml
# @KA:desc Where the MathML is saved, a file with the `.xml` extension. The folder must already exist; an existing file
# with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be PDF document or XML file." (error 16)
# @KA:solution Select an output file with the `.xml` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:param zoom
# @KA:desc Used by PDFix Desktop to render the selected tag into the image (default 2.0).
# @KA:param overwrite
# @KA:desc Used by PDFix Desktop: when on, an existing MathML 3 associated file of the selected tag is replaced; when
# off (default), it is kept.
def run_mathml_subcommand(args) -> None:
    output_extension: str = check_output_file(args.output, (".pdf", ".xml"), MESSAGE_ARG_OUTPUT_NOT_PDF_OR_XML)
    if output_extension == ".xml":
        check_input_image(args.input)
        ai = GenerateMathmlFromImage(args.input, args.output)
        ai.process_image()
        return

    check_input_pdf(args.input)
    tag_filter: str | Path | dict = resolve_regex_template(getattr(args, "params", None))
    if isinstance(tag_filter, dict):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as template_file:
            with open(template_file.name, "w", encoding="utf-8") as template_file_write:
                json.dump(tag_filter, template_file_write)
            formula_to_mathml(
                args.name, args.key, args.input, args.output, Path(template_file.name), args.overwrite, args.password
            )
    else:
        formula_to_mathml(args.name, args.key, args.input, args.output, tag_filter, args.overwrite, args.password)


def resolve_regex_template(params_path: Optional[str]) -> str | Path | dict:
    """
    Resolve tag filter from --params (regex or template) or the default Formula regex.

    Args:
        params_path (Optional[str]): Path to params JSON, or None.

    Returns:
        Either a regex string or a template dict.
    """
    if not params_path:
        return DEFAULT_TAGS_MATHML

    params_parser = ParamsParser(params_path, ["tag_names"])
    params_parser.parse()
    tag_names: Any = params_parser.params["tag_names"]
    if isinstance(tag_names, str):
        return tag_names
    if isinstance(tag_names, dict):
        return tag_names
    raise InvalidRegexOrTemplateException()


def formula_to_mathml(
    license_name: Optional[str],
    license_key: Optional[str],
    input_path: str,
    output_path: str,
    regex_template: str | Path,
    overwrite: bool,
    password: str = "",
) -> None:
    """
    Processing all formulas in PDF document and adding Associate Files to them.

    Args:
        license_name (Optional[str]): Name used in authorization in PDFix-SDK.
        license_key (Optional[str]): Key used in authorization in PDFix-SDK.
        input_path (str): Path to PDF document.
        output_path (str): Path to PDF document.
        regex_template (str | Path): Regex or path to template JSON for matching tags.
        overwrite (bool): Replace existing MathML associated files of the current version.
        password (str): Password of the PDF document, empty when it has none.
    """
    generateMathml = GenerateMathmlInPdf(
        license_name, license_key, input_path, output_path, regex_template, overwrite, password
    )
    generateMathml.process_file()


# Paddle layout class index of each threshold argument (order of the PP-DocLayout-L classes)
THRESHOLD_ARGUMENTS: list[str] = [
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
THRESHOLD_MIN: float = 0.05
THRESHOLD_MAX: float = 0.95


def create_threshold_dictionary(args) -> dict:
    """
    Create a dictionary of threshold values from the provided arguments. Values out of range are clamped and
    the change is logged.

    Args:
        args (argparse.Namespace): Parsed command line arguments.

    Returns:
        dict: Dictionary containing threshold values by Paddle layout class index.
    """
    thresholds: dict[int, float] = {}
    for index, name in enumerate(THRESHOLD_ARGUMENTS):
        value: float = float(getattr(args, name))
        clamped: float = clamp(value, THRESHOLD_MIN, THRESHOLD_MAX)
        if clamped != value:
            logger.warning(
                f"--{name} {value} is out of range {THRESHOLD_MIN} to {THRESHOLD_MAX}, using {clamped} instead."
            )
        thresholds[index] = clamped
    return thresholds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autotag PDF document Paddle Engine and PDFix SDK",
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    threshold_arguments = THRESHOLD_ARGUMENTS

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
    tagging_arguments = [
        "name",
        "key",
        "input",
        "output",
        "password",
        "model",
        "zoom",
        "process_formula",
        "process_table",
    ]
    set_arguments(autotag_subparser, tagging_arguments + threshold_arguments, True, "PDF", "PDF")
    autotag_subparser.set_defaults(func=run_autotag_subcommand)

    # Template subparser
    template_subparser = subparsers.add_parser(
        "template",
        help="Create layout template JSON.",
    )
    template_arguments = ["name", "key", "input", "output", "password", "model", "zoom", "process_table"]
    set_arguments(template_subparser, template_arguments + threshold_arguments, True, "PDF", "JSON")
    template_subparser.set_defaults(func=run_template_subcommand)

    # MathML subparser
    mathml_help = "Generate MathML representation of formula. Support 2 modes."
    mathml_help += " First mode takes PDF and processes all Formula tags."
    mathml_help += " Second mode takes image and outputs XML file with MathML representation of formula in image."
    mathml_help += f" Supported image files are: {SUPPORTED_IMAGE_EXT}."
    mathml_subparser = subparsers.add_parser("mathml", help=mathml_help)
    set_arguments(
        mathml_subparser,
        ["name", "key", "input", "output", "password", "params", "overwrite"],
        True,
        "PDF or IMG",
        "PDF or XML",
    )
    mathml_subparser.set_defaults(func=run_mathml_subcommand)

    # Parse arguments
    try:
        args = parser.parse_args()
    except ExpectedException as e:
        logger.error(e.message)
        sys.exit(e.error_code)
    except SystemExit as e:
        if e.code != 0:
            logger.error(MESSAGE_ARG_GENERAL)
            sys.exit(EC_ARG_GENERAL)
        # This happens when --help is used, exit gracefully
        sys.exit(0)
    except Exception as e:
        logger.error("Failed to run the program:")
        logger.exception(e)
        sys.exit(1)

    if hasattr(args, "func"):
        # Check for updates only when help is not checked
        update_checker = DockerImageContainerUpdateChecker()
        # Check it in separate thread not to be delayed when there is slow or no internet connection
        update_thread = threading.Thread(target=update_checker.check_for_image_updates)
        update_thread.start()

        # Measure the time it takes to process the input
        start_time: float = time.time()
        current_time: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.info(f"Processing started at: {current_time}")

        # Run subcommand
        try:
            args.func(args)
        except ExpectedException as e:
            logger.error(e.message)
            if e.sdk_error:
                logger.error(e.sdk_error)
            sys.exit(e.error_code)
        except Exception as e:
            # not expected exception -> print stack trace and what exception happened
            logger.error("Failed to run the program:")
            logger.exception(e)
            sys.exit(1)
        finally:
            elapsed_time: float = time.time() - start_time
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logger.info(f"Processing finished at: {current_time}. Elapsed time: {elapsed_time:.2f} seconds")

            # Make sure to let update thread finish before exiting
            update_thread.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
