import ctypes
import json
import re
from typing import Optional

from pdfixsdk import (
    PdfDoc,
    Pdfix,
    PdsArray,
    PdsDictionary,
    PdsObject,
    PdsStream,
    PdsStructElement,
    PdsStructTree,
    PsAccountAuthorization,
    kPdsStructChildElement,
)

from exceptions import PdfixActivationException, PdfixAuthorizationException


def authorize_sdk(pdfix: Pdfix, license_name: Optional[str], license_key: Optional[str]) -> None:
    """
    Tries to authorize or activate Pdfix license.

    Args:
        pdfix (Pdfix): Pdfix sdk instance.
        license_name (string): Pdfix sdk license name (e-mail)
        license_key (string): Pdfix sdk license key
    """
    if license_name and license_key:
        authorization: PsAccountAuthorization = pdfix.GetAccountAuthorization()
        if not authorization.Authorize(license_name, license_key):
            raise PdfixAuthorizationException(pdfix)
    elif license_key:
        if not pdfix.GetStandarsAuthorization().Activate(license_key):
            raise PdfixActivationException(pdfix)
    else:
        print("No license name or key provided. Using PDFix SDK trial")


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
    json_data_size: int = len(json_str)
    json_data_raw: ctypes.Array[ctypes.c_ubyte] = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
    return json_data_raw, json_data_size


def browse_tags_recursive(element: PdsStructElement, regex_tag: str) -> list[PdsStructElement]:
    """
    Recursively browses through the structure elements of a PDF document and processes
    elements that match the specified tags.

    Description:
    This function recursively browses through the structure elements of a PDF document
    starting from the specified parent element. It checks each child element to see if it
    matches the specified tags using a regular expression. If a match is found, the element
    is processed using the `process_struct_elem` function. If no match is found, the function
    calls itself recursively on the child element.

    Args:
        element (PdsStructElement): The parent structure element to start browsing from.
        regex_tag (str): The regular expression to match tags.
    """
    result: list[PdsStructElement] = []
    count: int = element.GetNumChildren()
    structure_tree: Optional[PdsStructTree] = element.GetStructTree()
    if structure_tree is None:
        return result

    for i in range(0, count):
        if element.GetChildType(i) != kPdsStructChildElement:
            continue
        child_object: Optional[PdsObject] = element.GetChildObject(i)
        if child_object is None:
            continue
        child_element: Optional[PdsStructElement] = structure_tree.GetStructElementFromObject(child_object)
        if child_element is None:
            continue
        if re.match(regex_tag, child_element.GetType(True)) or re.match(regex_tag, child_element.GetType(False)):
            # process element
            result.append(child_element)
        else:
            result.extend(browse_tags_recursive(child_element, regex_tag))
    return result


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


def set_associated_file_math_ml(pdfix: Pdfix, element: PdsStructElement, math_ml: str, math_ml_version: str) -> None:
    """
    Set the MathML associated file for a structure element.

    Args:
        pdfix (Pdfix): PDFix SDK.
        element (PdsStructElement): The structure element to set the MathML for.
        math_ml (str): The MathML content to set.
        math_ml_version (str): The MathML version to set.
    """
    # create mathML object
    structure_tree: Optional[PdsStructTree] = element.GetStructTree()
    if structure_tree is None:
        print("Failed to get structure tree from element")
        return
    document: Optional[PdfDoc] = structure_tree.GetDoc()
    if document is None:
        print("Failed to get document from structure tree")
        return
    associated_file_data: Optional[PdsDictionary] = document.CreateDictObject(True)
    if associated_file_data is None:
        print("Failed to create dictionary in document")
        return
    associated_file_data.PutName("Type", "Filespec")
    associated_file_data.PutName("AFRelationshhip", "Supplement")
    associated_file_data.PutString("F", math_ml_version)
    associated_file_data.PutString("UF", math_ml_version)
    associated_file_data.PutString("Desc", math_ml_version)

    raw_data: ctypes.Array[ctypes.c_ubyte] = bytearray_to_data(bytearray(math_ml.encode("utf-8")))
    file_dictionary: Optional[PdsDictionary] = document.CreateDictObject(False)
    if file_dictionary is None:
        print("Failed to create dictionary in document")
        return
    file_stream: Optional[PdsStream] = document.CreateStreamObject(True, file_dictionary, raw_data, len(math_ml))
    if file_dictionary is None:
        print("Failed to create file stream object in document")
        return

    ef_dict: Optional[PdsDictionary] = associated_file_data.PutDict("EF")
    if ef_dict is None:
        print("Failed to create dictionary in dictionary")
        return
    ef_dict.Put("F", file_stream)
    ef_dict.Put("UF", file_stream)

    add_associated_file(pdfix, element, associated_file_data)


def add_associated_file(pdfix: Pdfix, element: PdsStructElement, associated_file_data: PdsDictionary) -> None:
    """
    Add an associated file to a structure element.

    Args:
        pdfix (Pdfix): PDFix SDK.
        element (PdsStructElement): The structure element to add the associated file to.
        associated_file_data (PdsDictionary): The associated file data to add.
    """
    element_object: PdsDictionary = PdsDictionary(element.GetObject().obj)
    associated_file_dictionary: Optional[PdsDictionary] = element_object.GetDictionary("AF")
    if associated_file_dictionary:
        # convert dict to an array
        associated_file_array: Optional[PdsArray] = pdfix.CreateArrayObject(False)
        if associated_file_array:
            associated_file_array.Put(0, associated_file_dictionary.Clone(False))
            element_object.Put("AF", associated_file_array)

    associated_file_array = element_object.GetArray("AF")
    if not associated_file_array:
        associated_file_array = element_object.PutArray("AF")
    if associated_file_array:
        associated_file_array.Put(associated_file_array.GetNumObjects(), associated_file_data)
