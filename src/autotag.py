import ctypes
import json
import os
import re
from pathlib import Path

from pdfixsdk import (
    GetPdfix,
    PdfDoc,
    Pdfix,
    PdfPage,
    PdfTagsParams,
    PdsDictionary,
    PdsStructElement,
    create_unicode_buffer,
    kDataFormatJson,
    kPdsStructChildElement,
    kRotate0,
    kSaveFull,
)
from tqdm import tqdm

from ai import PaddleXEngine
from exceptions import (
    PdfixActivationException,
    PdfixAuthorizationException,
    PdfixException,
)
from page_renderer import create_image_from_pdf_page
from template_json import TemplateJsonCreator


class AutotagUsingPaddleXRecognition:
    """
    Class that takes care of Autotagging provided PDF document using Paddle Engine.
    """

    def __init__(
        self,
        license_name: str,
        license_key: str,
        input_path: str,
        output_path: str,
        model: str,
        zoom: float,
        process_formula: bool,
        process_table: bool,
        thresholds: dict,
    ) -> None:
        """
        Initialize class for tagging pdf(s).

        Args:
            license_name (string): Pdfix sdk license name (e-mail)
            license_key (string): Pdfix sdk license key
            input_path (string): Path to PDF document
            output_path (string): Path where tagged PDF should be saved
            model (string): Paddle model for layout recognition
            zoom (float): Zoom level for rendering the page
            process_formula (bool): Whether to process formulas
            process_table (bool): Whether to process tables
            thresholds (dict): Thresholds for layout detection
        """
        self.license_name = license_name
        self.license_key = license_key
        self.input_path_str = input_path
        self.output_path_str = output_path
        self.model = model
        self.zoom = zoom
        self.process_formula = process_formula
        self.process_table = process_table
        self.thresholds = thresholds

    def process_file(self) -> None:
        """
        Automatically tags a PDF document.
        """
        id: str = Path(self.input_path_str).stem

        pdfix = GetPdfix()
        if pdfix is None:
            raise Exception("Pdfix Initialization failed")

        # Try to authorize so results don't contain watermarks
        self._authorize(pdfix)

        # Open the document
        doc = pdfix.OpenDoc(self.input_path_str, "")
        if doc is None:
            raise Exception(f"Unable to open PDF : {str(pdfix.GetError())} [{pdfix.GetErrorType()}]")

        # Process images of each page
        num_pages = doc.GetNumPages()
        paddlex = PaddleXEngine(self.model, self.process_formula, self.process_table, self.thresholds)
        template_json_creator = TemplateJsonCreator()
        max_formulas_and_tables_per_page = 1000
        progress_bar = tqdm(total=num_pages * max_formulas_and_tables_per_page, desc="Processing pages")

        for page_index in range(0, num_pages):
            # Acquire the page
            page = doc.AcquirePage(page_index)
            if page is None:
                raise PdfixException("Unable to acquire the page")

            try:
                # Process the page
                self._process_pdf_file_page(
                    id, page, page_index, paddlex, template_json_creator, progress_bar, max_formulas_and_tables_per_page
                )
            except Exception:
                raise
            finally:
                # Clean-up
                page.Release()

        # Create template json for whole document
        template_json_dict: dict = template_json_creator.create_json_dict_for_document(self.model, self.zoom)

        # Save template json to fileoutput_name = f"{id}-page{page_number}.png"
        template_path = os.path.join(Path(__file__).parent.absolute(), f"../output/{id}-template_json.json")
        with open(template_path, "w") as file:
            file.write(json.dumps(template_json_dict, indent=2))

        # Remove old structure and prepare an empty structure tree
        doc.RemoveTags()
        doc.RemoveStructTree()

        # Convert template json to memory stream
        memory_stream = GetPdfix().CreateMemStream()
        try:
            raw_data, raw_data_size = self._json_to_raw_data(template_json_dict)
            if not memory_stream.Write(0, raw_data, raw_data_size):
                raise Exception(GetPdfix().GetError())

            doc_template = doc.GetTemplate()
            if not doc_template.LoadFromStream(memory_stream, kDataFormatJson):
                raise Exception(f"Unable to open pdf : {pdfix.GetError()}")
        except Exception as e:
            raise PdfixException(f"Unable to load template json for tagging: {e}")
        finally:
            memory_stream.Destroy()

        # Autotag document
        tagsParams = PdfTagsParams()
        if not doc.AddTags(tagsParams):
            raise Exception(pdfix.GetError())

        # Add AF to document
        if self.process_formula:
            formulas: list = template_json_creator.get_formulas()
            for formula in formulas:
                print(f"ID: {formula[0]}")
            self._process_formulas(pdfix, doc, paddlex, formulas)

        # Save the processed document
        if not doc.Save(self.output_path_str, kSaveFull):
            raise RuntimeError(f"{pdfix.GetError()} [{pdfix.GetErrorType()}]")

    def _json_to_raw_data(self, json_dict: dict) -> tuple[ctypes.Array[ctypes.c_ubyte], int]:
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

    def _authorize(self, pdfix: Pdfix) -> None:
        """
        Tries to authorize or activate Pdfix license.

        Args:
            pdfix (Pdfix): Pdfix sdk instance.
        """

        if self.license_name and self.license_key:
            authorization = pdfix.GetAccountAuthorization()
            if not authorization.Authorize(self.license_name, self.license_key):
                raise PdfixAuthorizationException(str(pdfix.GetError()))
        elif self.license_key:
            if not pdfix.GetStandarsAuthorization().Activate(self.license_key):
                raise PdfixActivationException(str(pdfix.GetError()))
        else:
            print("No license name or key provided. Using PDFix SDK trial")

    def _process_pdf_file_page(
        self,
        id: str,
        page: PdfPage,
        page_index: int,
        paddlex: PaddleXEngine,
        templateJsonCreator: TemplateJsonCreator,
        progress_bar: tqdm,
        max_formulas_and_tables_per_page: int,
    ) -> None:
        """
        Create template json for current PDF document page.

        Args:
            id (string): PDF document name.
            page (PdfPage): The PDF document page to process.
            page_index (int): PDF file page index.
            paddlex (PaddleXEngine): PaddleX engine instance for processing.
            templateJsonCreator (TemplateJsonCreator): Template JSON creator.
            progress_bar (tqdm): Progress bar that we update for each model
                call.
            max_formulas_and_tables_per_page (int): Our estimation how many
                tables and formulas can be in one page.
        """
        page_number = page_index + 1

        # Define rotation for rendering the page
        page_view = page.AcquirePageView(self.zoom, kRotate0)

        try:
            # Render the page as an image
            image = create_image_from_pdf_page(page, page_view)

            # Run layout model analysis and formula and table model analysis using the PaddleX engine
            results = paddlex.process_pdf_page_image_with_ai(
                image, id, page_number, progress_bar, max_formulas_and_tables_per_page
            )

            # Create template json from PaddleX results for this page
            templateJsonCreator.process_page(results, page_number, page_view, self.zoom)
        except Exception:
            raise
        finally:
            # Release resources
            page_view.Release()

    def _process_formulas(self, pdfix: Pdfix, doc: PdfDoc, paddlex: PaddleXEngine, formulas: list) -> None:
        """
        For each formula add associate file to PDF.

        Args:
            pdfix (Pdfix): PDFix SDK.
            doc (PdfDoc): Tagged PDF document.
            paddlex (PaddleXEngine): PaddleX engine instance for processing.
            formulas (list): List of formulas to process.
        """
        print("XXXXXX START HERE XXXXX")
        struct_tree = doc.GetStructTree()
        if struct_tree is None:
            raise Exception(f"PDF has no structure tree : {str(pdfix.GetError())} [{pdfix.GetErrorType()}]")

        child_element = struct_tree.GetStructElementFromObject(struct_tree.GetChildObject(0))
        items = self._browse_tags_recursive(child_element, "Formula")
        for formula_element in items:
            element_id = self._get_id_from_formula_element(formula_element)
            if element_id == "":
                print('This formula element does not have "id"')
                # This formula element does not have "id"
                continue
            print(f"We have element with id: {element_id}")

            index = next((i for i, data in enumerate(formulas) if data[0] == element_id), -1)
            if index < 0:
                # We don't have data for this formula "id"
                print('We don\'t have data for this formula "id"')
                continue
            formula = formulas.pop(index)
            print(f"Setting AF for: ({formula[0]}: {formula[1]})")
            self._set_associated_file_math_ml(formula_element, formula[1], paddlex.MATH_ML_VERSION)

    def _browse_tags_recursive(self, element: PdsStructElement, regex_tag: str) -> list[PdsStructElement]:
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
        result = []
        count = element.GetNumChildren()
        structure_tree = element.GetStructTree()
        for i in range(0, count):
            if element.GetChildType(i) != kPdsStructChildElement:
                continue
            child_element: PdsStructElement = structure_tree.GetStructElementFromObject(element.GetChildObject(i))
            if re.match(regex_tag, child_element.GetType(True)) or re.match(regex_tag, child_element.GetType(False)):
                # process element
                result.append(child_element)
            else:
                result.extend(self._browse_tags_recursive(child_element, regex_tag))
        return result

    def _get_id_from_formula_element(self, element: PdsStructElement) -> str:
        """
        Get id from formula element.

        Args:
            element (PdsStructElement): The formula structure element.

        Returns:
            Id if found, empty string otherwise.
        """
        for index in reversed(range(element.GetNumAttrObjects())):
            attribute_object = element.GetAttrObject(index)
            if not attribute_object:
                continue
            attribute_dictionary = PdsDictionary(attribute_object.obj)
            key = "O"
            print(f"Attribute Text: {attribute_dictionary.GetText(key)}")
            print(f"Attribute Id: {attribute_dictionary.GetId()}")
            try:
                lenght = attribute_dictionary.GetString(key, None, 0)
                buffer = create_unicode_buffer(lenght)
                string = attribute_dictionary.GetString(key, buffer, lenght)
                print(f"Attribute str: {string}")
                if attribute_dictionary.GetText(key) == "Formula":
                    id: int = attribute_dictionary.GetString("id")
                    if id:
                        return str(id)
            except Exception:
                pass

        return ""

    def _bytearray_to_data(self, byte_array: bytearray) -> ctypes.Array[ctypes.c_ubyte]:
        """
        Utility function to convert a bytearray to a ctypes array.

        Args:
            byte_array (bytearray): The bytearray to convert.

        Returns:
            The converted ctypes array.
        """
        size = len(byte_array)
        return (ctypes.c_ubyte * size).from_buffer(byte_array)

    def _set_associated_file_math_ml(self, element: PdsStructElement, math_ml: str, math_ml_version: str) -> None:
        """
        Set the MathML associated file for a structure element.

        Args:
            element (PdsStructElement): The structure element to set the MathML for.
            math_ml (str): The MathML content to set.
            math_ml_version (str): The MathML version to set.
        """
        # create mathML object
        document = element.GetStructTree().GetDoc()
        associated_file_data = document.CreateDictObject(True)
        associated_file_data.PutName("Type", "Filespec")
        associated_file_data.PutName("AFRelationshhip", "Supplement")
        associated_file_data.PutString("F", math_ml_version)
        associated_file_data.PutString("UF", math_ml_version)
        associated_file_data.PutString("Desc", math_ml_version)

        raw_data = self._bytearray_to_data(bytearray(math_ml.encode("utf-8")))
        file_dictionary = document.CreateDictObject(False)
        file_stream = document.CreateStreamObject(True, file_dictionary, raw_data, len(math_ml))

        ef_dict = associated_file_data.PutDict("EF")
        ef_dict.Put("F", file_stream)
        ef_dict.Put("UF", file_stream)

        self._add_associated_file(element, associated_file_data)

    def _add_associated_file(self, element: PdsStructElement, associated_file_data: PdsDictionary) -> None:
        """
        Add an associated file to a structure element.

        Args:
            element (PdsStructElement): The structure element to add the associated file to.
            associated_file_data (PdsDictionary): The associated file data to add.
        """
        element_object = PdsDictionary(element.GetObject().obj)
        associated_file_dictionary = element_object.GetDictionary("AF")
        if associated_file_dictionary:
            # convert dict to an array
            associated_file_array = GetPdfix().CreateArrayObject(False)
            associated_file_array.Put(0, associated_file_dictionary.Clone(False))
            element_object.Put("AF", associated_file_array)

        associated_file_array = element_object.GetArray("AF")
        if not associated_file_array:
            associated_file_array = element_object.PutArray("AF")
        associated_file_array.Put(associated_file_array.GetNumObjects(), associated_file_data)
