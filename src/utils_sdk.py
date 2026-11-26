import ctypes
import json
import logging
from typing import Optional

from pdfixsdk import (
    PdfDoc,
    Pdfix,
    PdsFileSpec,
    PdsStructElement,
    PdsStructTree,
    PsAccountAuthorization,
    PsStandardAuthorization,
)

from constants import MATH_ML_DESCRIPTION
from exceptions import PdfixActivationException, PdfixAuthorizationException
from logger import get_logger

logger: logging.Logger = get_logger("app_logger")


def index_of_associated_file(element: PdsStructElement, math_ml_version: str) -> int:
    """
    Find the index of an associated file whose name contains the MathML version marker.

    Match is case-insensitive and uses substring containment (e.g. ``mathml-3`` and
    ``mathml-3.xml`` both match ``mathml-3``).

    Args:
        element (PdsStructElement): Structure element to inspect.
        math_ml_version (str): Version marker to look for in the filespec name.

    Returns:
        Index of the first matching associated file, or ``-1`` if none found.
    """
    for index in range(element.GetNumAssociatedFiles()):
        file_spec: Optional[PdsFileSpec] = element.GetAssociatedFile(index)
        if file_spec is None:
            continue
        if math_ml_version.lower() in file_spec.GetFileName().lower():
            return index
    return -1


def authorize_sdk(pdfix: Pdfix, license_name: Optional[str], license_key: Optional[str]) -> None:
    """
    Tries to authorize or activate Pdfix license.

    Args:
        pdfix (Pdfix): Pdfix sdk instance.
        license_name (string): Pdfix sdk license name (e-mail)
        license_key (string): Pdfix sdk license key
    """
    if license_name and license_key:
        authorization: Optional[PsAccountAuthorization] = pdfix.GetAccountAuthorization()
        if authorization is None or not authorization.Authorize(license_name, license_key):
            raise PdfixAuthorizationException(pdfix)
    elif license_key:
        standard_authorization: Optional[PsStandardAuthorization] = pdfix.GetStandardAuthorization()
        if standard_authorization is None or not standard_authorization.Activate(license_key):
            raise PdfixActivationException(pdfix)
    else:
        logger.info("No license name or key provided. Using PDFix SDK trial")


def json_to_raw_data(json_dict: dict) -> tuple[ctypes.Array[ctypes.c_ubyte], int]:
    """
    Converts a JSON dictionary into a raw byte array (c_ubyte array) that can be used for low-level data operations.

    Parameters:
        json_dict (dict): A Python dictionary to be converted into JSON format and then into raw bytes.

    Returns:
        tuple: A tuple containing:
            - json_data_raw (ctypes.c_ubyte array): The raw byte array representation of the JSON data.
            - json_data_size (int): The size of the JSON data in bytes.
    """
    json_str: str = json.dumps(json_dict)
    json_data: bytearray = bytearray(json_str.encode("utf-8"))
    # Size in bytes, not characters
    json_data_size: int = len(json_data)
    json_data_raw: ctypes.Array[ctypes.c_ubyte] = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
    return json_data_raw, json_data_size


def bytearray_to_data(byte_array: bytearray) -> ctypes.Array[ctypes.c_ubyte]:
    """
    Utility function to convert a bytearray to a ctypes array.

    Args:
        byte_array (bytearray): The bytearray to convert.

    Returns:
        The converted ctypes array.
    """
    size: int = len(byte_array)
    return (ctypes.c_ubyte * size).from_buffer(byte_array)


def set_associated_file_math_ml(element: PdsStructElement, math_ml: str, math_ml_version: str) -> bool:
    """
    Attach MathML as associated file (AF) to a structure element, like PDFix Desktop does.

    The file specification is created by PDFix SDK: file name "<version>.xml", AFRelationship Supplement,
    embedded file of subtype application/mathml+xml.

    Args:
        element (PdsStructElement): The structure element to set the MathML for.
        math_ml (str): The MathML content to set.
        math_ml_version (str): The MathML version, for example "mathml-3".

    Returns:
        True when the associated file was added.
    """
    structure_tree: Optional[PdsStructTree] = element.GetStructTree()
    document: Optional[PdfDoc] = structure_tree.GetDoc() if structure_tree else None
    if document is None:
        logger.warning("Failed to get document of the structure element")
        return False

    data: bytes = math_ml.encode("utf-8")
    raw_data: ctypes.Array[ctypes.c_ubyte] = bytearray_to_data(bytearray(data))
    file_spec: Optional[PdsFileSpec] = document.CreateFileSpec(
        f"{math_ml_version}.xml", MATH_ML_DESCRIPTION, "Supplement", "application/mathml+xml", raw_data, len(data)
    )
    if file_spec is None:
        logger.warning("Failed to create file specification for MathML")
        return False
    if not element.AddAssociatedFile(file_spec, 0):
        logger.warning("Failed to add MathML associated file to the structure element")
        return False
    return True
