class PaddleXPostProcessingBBoxes:
    """
    Class that take PaddleX results for bounding boxes (bboxes) and compares all overlaps between them.
    Accordingly decices which bboxes will be removed from results.
    """

    def __init__(self, results: dict) -> None:
        """
        Initialize the PaddleXPostProcessingBBoxes class.

        Args:
            Dictionary results containing bounding boxes and their scores.
        """
        self.results = results
        self.overlaps: list = []

    def find_bboxes_that_overlaps(self) -> None:
        """
        Find bounding boxes that overlap with each other and process them accordingly.
        """
        number_bboxes = len(self.results["boxes"])  # Ensure there are boxes to process

        for index1 in range(number_bboxes):
            for index2 in range(index1 + 1, number_bboxes):
                if self._is_overlapping(index1, index2):
                    self.overlaps.append((index1, index2))

    def return_results_without_overlap(self) -> list:
        """
        Return results without overlaping bounding boxes (bboxes).

        Returns:
            Remove overlapping bboxes according to some heuristics.
        """
        remove_indexes = []
        for index1, index2 in self.overlaps:
            # one of the indexes is already removed
            if index1 in remove_indexes:
                continue
            if index2 in remove_indexes:
                continue

            remove_index = self._choose_which_bbox_to_remove(index1, index2)
            if remove_index == -1:
                continue

            remove_indexes.append(remove_index)

        output_boxes: list = []
        for index, box in enumerate(self.results["boxes"]):
            if index not in remove_indexes:
                output_boxes.append(box)

        return output_boxes

    def _choose_which_bbox_to_remove(self, index1: int, index2: int) -> int:
        """
        Choose which bounding box (bbox) to remove based on the overlap percentage.

        Args:
            index1 (int): Index of the first bbox.
            index2 (int): Index of the second bbox.

        Returns:
            Index of the bbox to remove.
        """
        box1 = self.results["boxes"][index1]
        box2 = self.results["boxes"][index2]
        overlap_1, overlap_2 = self._get_overlap_percentage(index1, index2)

        # Too small overlap, ignore
        if overlap_1 < 50.0 and overlap_2 < 50.0:
            return -1

        score1 = box1["score"]
        score2 = box2["score"]

        # One bbox is inside another bigger one bbox (remove small bbox)
        if (overlap_1 > 95.0 and overlap_2 < 75.0) or (overlap_2 > 95.0 and overlap_1 < 75.0):
            # TODO ignore formulas inside text ...
            return index1 if overlap_1 > overlap_2 else index2

        # One bbox has much greater score from paddlex (remove smaller score bbox)
        if abs(score1 - score2) > 0.3:  # 30% difference
            return index1 if score1 > score2 else index2

        # by default, use size to decide (remove smaller bbox)
        size1 = self._calculate_size(box1["coordinate"])
        size2 = self._calculate_size(box2["coordinate"])

        return index1 if size1 < size2 else index2

    def _is_overlapping(self, index1: int, index2: int) -> bool:
        """
        Check if two bounding boxes overlap.

        Args:
            index1 (int): Index of the first bounding box.
            index2 (int): Index of the second bounding box.

        Returns:
            True if the bounding boxes overlap, False otherwise.
        """
        x_min_1, y_min_1, x_max_1, y_max_1 = self.results["boxes"][index1]
        x_min_2, y_min_2, x_max_2, y_max_2 = self.results["boxes"][index2]

        return not (
            x_max_1 < x_min_2  # box1 is left of box2
            or x_min_1 > x_max_2  # box1 is right of box2
            or y_max_1 < y_min_2  # box1 is above box2
            or y_min_1 > y_max_2  # box1 is below box2
        )

    def _calculate_size(self, coordinate: list) -> float:
        """
        Calculate the size of a bounding box (bbox).

        Args:
            coordinate (list): bbox coordinates in the format [x_min, y_min, x_max, y_max].

        Returns:
            Size of the bbox.
        """
        x_min, y_min, x_max, y_max = coordinate
        return max(0, x_max - x_min) * max(0, y_max - y_min)

    def _intersection_size(self, coordinate_1: list, coordinate_2: list) -> float:
        """
        Calculate the intersection size of two bounding boxes.

        Args:
            coordinate_1 (list): First bounding box.
            coordinate_2 (list): Second bounding box.
        """
        x_min_1, y_min_1, x_max_1, y_max_1 = coordinate_1
        x_min_2, y_min_2, x_max_2, y_max_2 = coordinate_2

        x_overlap = max(0, min(x_max_1, x_max_2) - max(x_min_1, x_min_2))
        y_overlap = max(0, min(y_max_1, y_max_2) - max(y_min_1, y_min_2))

        return x_overlap * y_overlap

    def _get_overlap_percentage(self, index1: int, index2: int) -> tuple:
        """
        Calculate the overlap percentage between two bounding boxes.

        Args:
            index1 (int): Index of the first bounding box.
            index2 (int): Index of the second bounding box.

        Returns:
            First value is percent (0-100) how much first bounding box has in overlaping area
            Second value is percent (0-100) how much second bounding box has in overlaping area.
        """
        box1 = self.results["boxes"][index1]["coordinate"]
        box2 = self.results["boxes"][index2]["coordinate"]
        area1 = self._calculate_size(box1)
        area2 = self._calculate_size(box2)
        inter_area = self._intersection_size(box1, box2)

        percent1 = (inter_area / area1) * 100 if area1 > 0 else 0
        percent2 = (inter_area / area2) * 100 if area2 > 0 else 0

        return percent1, percent2
