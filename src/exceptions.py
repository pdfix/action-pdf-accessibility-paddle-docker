from pdfixsdk import GetPdfix


class PdfixException(Exception):
    def __init__(self, message: str = "") -> None:
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


class PdfixAuthorizationException(Exception):
    def __init__(self, message: str) -> None:
        self.add_note(message)


class PdfixAuthorizationFailedException(Exception):
    pass
