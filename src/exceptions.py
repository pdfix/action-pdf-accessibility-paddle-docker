from pdfixsdk import GetPdfix


class PdfixException(Exception):
    def __init__(self, message: str = "") -> None:
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))

class UnvalidDirectoryException(Exception):
    def __init__(self, path: str) -> None:
        self.add_note(f"Error: '{path}' is not a valid directory.")

class SameDirectoryException(Exception):
    def __init__(self) -> None:
        self.add_note("Input and output directories cannot have the same path")

class PdfixAuthorizationException(Exception):
    def __init__(self, message: str) -> None:
        self.add_note(message)

class PdfixAuthorizationFailedException(Exception):
    pass
