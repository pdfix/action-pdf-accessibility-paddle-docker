from pdfixsdk import Pdfix


class PdfixException(Exception):
    def __init__(self, pdfix: Pdfix, message: str = "") -> None:
        self.errno = pdfix.GetErrorType()
        self.add_note(message if len(message) else str(pdfix.GetError()))


class PdfixAuthorizationException(Exception):
    def __init__(self, message: str) -> None:
        self.add_note(message)


class PdfixActivationException(Exception):
    def __init__(self, message: str) -> None:
        self.add_note(message)
