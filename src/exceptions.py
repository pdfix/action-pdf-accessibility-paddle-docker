from pdfixsdk import Pdfix


class PdfixException(Exception):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        error_code = pdfix.GetErrorType()
        error = str(pdfix.GetError())
        self.errno = error_code
        self.add_note(f"[{error_code}] [{error}]: {message}" if len(message) > 0 else f"[{error_code}] {error}")
