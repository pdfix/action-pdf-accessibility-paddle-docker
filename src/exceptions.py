from pdfixsdk import Pdfix

EC_ARG_GENERAL = 10
EC_ARG_ZOOM = 11
EC_ARG_INPUT_PDF_OUTPUT_JSON = 12
EC_ARG_INPUT_PDF_OUTPUT_PDF = 13
EC_ARG_INPUT_OUTPUT_NOT_ALLOWED = 14

EC_PDFIX_INITIALIZE = 20
EC_PDFIX_ACTIVATION_FAILED = 21
EC_PDFIX_AUTHORIZATION_FAILED = 22
EC_PDFIX_FAILED_TO_RENDER = 23
EC_PDFIX_FAILED_TO_OPEN = 24
EC_PDFIX_FAILED_TO_SAVE = 25
EC_PDFIX_FAILED_TO_TAG = 26
EC_PDFIX_FAILED_TO_CREATE_TEMPLATE = 27
EC_PDFIX_NO_TAGS = 28

MESSAGE_ARG_GENERAL = "Failed to parse arguments. Please check the usage and try again."
MESSAGE_ARG_ZOOM = "Zoom level must between 1.0 and 10.0."
MESSAGE_ARG_INPUT_PDF_OUTPUT_JSON = "Input file must be PDF document and output file must be JSON."
MESSAGE_ARG_INPUT_PDF_OUTPUT_PDF = "Input and output file must be PDF documents."
MESSAGE_ARG_INPUT_OUTPUT_NOT_ALLOWED = "Not allowed input output file combination. Please see --help."

MESSAGE_PDFIX_INITIALIZE = "Failed to initialize PDFix SDK."
MESSAGE_PDFIX_ACTIVATION_FAILED = "Failed to activate PDFix SDK acount."
MESSAGE_PDFIX_AUTHORIZATION_FAILED = "Failed to authorize PDFix SDK acount."
MESSAGE_PDFIX_FAILED_TO_RENDER = "Failed to render PDF Page into image."
MESSAGE_PDFIX_FAILED_TO_OPEN = "Failed to open PDF document."
MESSAGE_PDFIX_FAILED_TO_SAVE = "Failed to save PDF document."
MESSAGE_PDFIX_FAILED_TO_TAG = "Failed to tag PDF document."
MESSAGE_PDFIX_FAILED_TO_CREATE_TEMPLATE = "Failed to create template JSON."
MESSAGE_PDFIX_NO_TAGS = "PDF document has no tags."


class ExpectedException(BaseException):
    def __init__(self, error_code: int) -> None:
        self.error_code: int = error_code
        self.message: str = ""

    def _add_note(self, note: str) -> None:
        self.message = note


class ArgumentException(ExpectedException):
    def __init__(self, message: str = MESSAGE_ARG_GENERAL, error_code: int = EC_ARG_GENERAL) -> None:
        super().__init__(error_code)
        self._add_note(message)


class ArgumentZoomException(ArgumentException):
    def __init__(self) -> None:
        super().__init__(MESSAGE_ARG_ZOOM, EC_ARG_ZOOM)


class ArgumentInputPdfOutputJsonException(ArgumentException):
    def __init__(self) -> None:
        super().__init__(MESSAGE_ARG_INPUT_PDF_OUTPUT_JSON, EC_ARG_INPUT_PDF_OUTPUT_JSON)


class ArgumentInputPdfOutputPdfException(ArgumentException):
    def __init__(self) -> None:
        super().__init__(MESSAGE_ARG_INPUT_PDF_OUTPUT_PDF, EC_ARG_INPUT_PDF_OUTPUT_PDF)


class ArgumentInputOutputNotAllowedException(ArgumentException):
    def __init__(self) -> None:
        super().__init__(MESSAGE_ARG_INPUT_OUTPUT_NOT_ALLOWED, EC_ARG_INPUT_OUTPUT_NOT_ALLOWED)


class PdfixInitializeException(ExpectedException):
    def __init__(self) -> None:
        super().__init__(EC_PDFIX_INITIALIZE)
        self._add_note(MESSAGE_PDFIX_INITIALIZE)


class PdfixException(ExpectedException):
    def __init__(self, pdfix: Pdfix, error_code: int, message: str = "") -> None:
        super().__init__(error_code)
        pdfix_error_code: int = pdfix.GetErrorType()
        pdfix_error: str = str(pdfix.GetError())
        self.add_note(
            f"[{pdfix_error_code}] [{pdfix_error}]: {message}"
            if len(message) > 0
            else f"[{pdfix_error_code}] {pdfix_error}"
        )


class PdfixActivationException(PdfixException):
    def __init__(self, pdfix: Pdfix) -> None:
        super().__init__(pdfix, EC_PDFIX_ACTIVATION_FAILED, MESSAGE_PDFIX_ACTIVATION_FAILED)


class PdfixAuthorizationException(PdfixException):
    def __init__(self, pdfix: Pdfix) -> None:
        super().__init__(pdfix, EC_PDFIX_AUTHORIZATION_FAILED, MESSAGE_PDFIX_AUTHORIZATION_FAILED)


class PdfixFailedToRenderException(PdfixException):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        super().__init__(pdfix, EC_PDFIX_FAILED_TO_RENDER, f"{MESSAGE_PDFIX_FAILED_TO_RENDER} {message}")


class PdfixFailedToOpenException(PdfixException):
    def __init__(self, pdfix: Pdfix, pdf_path: str = "") -> None:
        super().__init__(pdfix, EC_PDFIX_FAILED_TO_OPEN, f"{MESSAGE_PDFIX_FAILED_TO_OPEN} {pdf_path}")


class PdfixFailedToSaveException(PdfixException):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        super().__init__(pdfix, EC_PDFIX_FAILED_TO_SAVE, f"{MESSAGE_PDFIX_FAILED_TO_SAVE} {message}")


class PdfixFailedToTagException(PdfixException):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        super().__init__(pdfix, EC_PDFIX_FAILED_TO_TAG, f"{MESSAGE_PDFIX_FAILED_TO_TAG} {message}")


class PdfixFailedToCreateTemplateException(PdfixException):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        super().__init__(
            pdfix, EC_PDFIX_FAILED_TO_CREATE_TEMPLATE, f"{MESSAGE_PDFIX_FAILED_TO_CREATE_TEMPLATE} {message}"
        )


class PdfixNoTagsException(PdfixException):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        super().__init__(pdfix, EC_PDFIX_NO_TAGS, f"{MESSAGE_PDFIX_NO_TAGS} {message}")
