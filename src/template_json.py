from typing import Any

from pdfixsdk import PdfDevRect


def create_json_from_results(results: list) -> list:
    """
    Prepare initial structural elements for the template based on
    detected regions.

    Args:
        results (list): A list of detected regions, each containing
            bounding box and type.

    Returns:
        List of elements with parameters.
    """
    elements = []

    for result in results:
        elem: dict[str, Any] = {}

        rect = PdfDevRect()
        rect.left = int(result["bbox"][0])
        rect.top = int(result["bbox"][1])
        rect.right = int(result["bbox"][2])
        rect.bottom = int(result["bbox"][3])
        elem["bbox"] = [rect.left, rect.bottom, rect.right, rect.top]

        # Determine element type
        region_type = result["type"].lower()
        match region_type:
            case "figure":
                elem["type"] = "pde_image"
            case "list":
                elem["type"] = "pde_list"
                # TODO label + lbody
            case "table":
                elem["type"] = "pde_table"
                # TODO
                # update_table_cells(element, region, page_view, image)
            case "text":
                elem["type"] = "pde_text"
            case "title":
                elem["type"] = "pde_text"
                elem["tag"] = "H1"
            case _:
                elem["type"] = "pde_text"

        elements.append(elem)

    return elements
