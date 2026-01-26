"""
Evaluation metrics for medical search systems.
"""

import numpy as np


class MedicalEvaluator:
    """Evaluator for medical search performance."""

    def __init__(self, relevance_threshold: float = 0.5):
        """
        Initialize the evaluator.

        Args:
            relevance_threshold: Score above which a result is considered relevant
        """
        self.relevance_threshold = relevance_threshold

    def compute_recall_at_k(
        self, predictions: list[list[str]], ground_truth: list[list[str]], k: int = 10
    ) -> float:
        """
        Compute Recall@K for search results.

        Args:
            predictions: List of lists of predicted document IDs for each query
            ground_truth: List of lists of relevant document IDs for each query
            k: Number of top results to consider

        Returns:
            Average recall@k across all queries
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(
                "Number of prediction lists must match number of ground truth lists"
            )

        recalls = []
        for pred_list, true_list in zip(predictions, ground_truth, strict=False):
            # Take top k predictions
            top_k_pred = pred_list[:k]

            # Convert to sets for easier comparison
            pred_set = set(top_k_pred)
            true_set = set(true_list)

            # Compute recall
            if len(true_set) == 0:
                # If there are no relevant documents, recall is 1.0 by convention
                recall = 1.0
            else:
                relevant_retrieved = len(pred_set.intersection(true_set))
                recall = relevant_retrieved / len(true_set)

            recalls.append(recall)

        # Return average recall
        return float(np.mean(recalls))

    def compute_mrr(
        self, predictions: list[list[str]], ground_truth: list[list[str]]
    ) -> float:
        """
        Compute Mean Reciprocal Rank (MRR) for search results.

        Args:
            predictions: List of lists of predicted document IDs for each query
            ground_truth: List of lists of relevant document IDs for each query

        Returns:
            MRR score
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(
                "Number of prediction lists must match number of ground truth lists"
            )

        reciprocal_ranks = []
        for pred_list, true_list in zip(predictions, ground_truth, strict=False):
            true_set = set(true_list)

            # Find the rank of the first relevant document
            rank = None
            for i, doc_id in enumerate(pred_list, start=1):
                if doc_id in true_set:
                    rank = i
                    break

            if rank is not None:
                reciprocal_ranks.append(1.0 / rank)
            else:
                # No relevant document found
                reciprocal_ranks.append(0.0)

        # Return average reciprocal rank
        return float(np.mean(reciprocal_ranks))

    def compute_precision_at_k(
        self, predictions: list[list[str]], ground_truth: list[list[str]], k: int = 10
    ) -> float:
        """
        Compute Precision@K for search results.

        Args:
            predictions: List of lists of predicted document IDs for each query
            ground_truth: List of lists of relevant document IDs for each query
            k: Number of top results to consider

        Returns:
            Average precision@k across all queries
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(
                "Number of prediction lists must match number of ground truth lists"
            )

        precisions = []
        for pred_list, true_list in zip(predictions, ground_truth, strict=False):
            # Take top k predictions
            top_k_pred = pred_list[:k]

            # Convert to sets
            true_set = set(true_list)

            # Count relevant documents in top k
            relevant_in_top_k = sum(1 for doc_id in top_k_pred if doc_id in true_set)

            # Compute precision
            precision = relevant_in_top_k / k if k > 0 else 0.0
            precisions.append(precision)

        return float(np.mean(precisions))

    def compute_average_precision(
        self, predictions: list[list[str]], ground_truth: list[list[str]]
    ) -> float:
        """
        Compute Average Precision (AP) for each query, then average across queries.

        Args:
            predictions: List of lists of predicted document IDs for each query
            ground_truth: List of lists of relevant document IDs for each query

        Returns:
            Mean Average Precision (MAP)
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(
                "Number of prediction lists must match number of ground truth lists"
            )

        average_precisions = []
        for pred_list, true_list in zip(predictions, ground_truth, strict=False):
            true_set = set(true_list)

            relevant_count = 0
            precision_sum = 0.0

            for i, doc_id in enumerate(pred_list, start=1):
                if doc_id in true_set:
                    relevant_count += 1
                    precision_at_i = relevant_count / i
                    precision_sum += precision_at_i

            if len(true_set) > 0:
                ap = precision_sum / len(true_set)
            else:
                ap = 0.0

            average_precisions.append(ap)

        return float(np.mean(average_precisions))
