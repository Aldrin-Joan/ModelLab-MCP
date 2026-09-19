"""Diagnostic evaluators for overfitting, data leakage, and error patterns."""

from typing import Any
import numpy as np


class OverfittingDetector:
    """Diagnoses generalization gaps between training and validation splits."""

    @staticmethod
    def evaluate(
        train_metrics: dict[str, float],
        val_metrics: dict[str, float],
        threshold: float = 0.15,
    ) -> dict[str, Any]:
        gap_details: dict[str, float] = {}
        overfitting_detected = False

        common_keys = set(train_metrics.keys()).intersection(val_metrics.keys())
        for k in common_keys:
            tr_v = train_metrics[k]
            val_v = val_metrics[k]
            if isinstance(tr_v, (int, float)) and isinstance(val_v, (int, float)):
                # For metrics where higher is better (accuracy, auc, f1, r2)
                if k in ("accuracy", "roc_auc", "pr_auc", "f1", "f1_macro", "r2"):
                    gap = tr_v - val_v
                    gap_details[k] = round(gap, 4)
                    if gap >= threshold:
                        overfitting_detected = True

        return {
            "overfitting_detected": overfitting_detected,
            "metric_gaps": gap_details,
            "severity": "HIGH" if any(g > 0.25 for g in gap_details.values()) else ("MEDIUM" if overfitting_detected else "LOW"),
            "observation": (
                f"Validation performance lags training metrics by {max(gap_details.values()):.2%}, indicating model memorization."
                if overfitting_detected and gap_details else "Generalization gap is within acceptable operational tolerance."
            ),
        }


class DataLeakageDetector:
    """Detects suspicious statistical patterns indicative of label or feature leakage."""

    @staticmethod
    def evaluate(
        train_metrics: dict[str, float],
        val_metrics: dict[str, float],
    ) -> dict[str, Any]:
        signals: list[str] = []
        suspicious = False

        # Suspiciously perfect validation performance
        for k in ("roc_auc", "accuracy", "f1"):
            if val_metrics.get(k) is not None and val_metrics[k] >= 0.999:
                signals.append(f"Metric '{k}' is suspiciously perfect ({val_metrics[k]:.4f}) on validation split.")
                suspicious = True

        # Validation strictly outperforms training by a large margin (often indicates wrong split or inverted leakage)
        for k in ("accuracy", "f1", "roc_auc"):
            if k in train_metrics and k in val_metrics:
                if val_metrics[k] - train_metrics[k] > 0.20:
                    signals.append(f"Validation '{k}' ({val_metrics[k]:.2f}) significantly exceeds training ({train_metrics[k]:.2f}).")
                    suspicious = True

        return {
            "leakage_risk_detected": suspicious,
            "signals": signals,
            "confidence": "HIGH" if len(signals) > 1 else ("MEDIUM" if suspicious else "NONE"),
        }


class ErrorPatternAnalyzer:
    """Analyzes confusion matrices and residual error distributions."""

    @staticmethod
    def evaluate_confusion_matrix(cm: list[list[int]]) -> dict[str, Any]:
        """Analyze false positives and false negatives in binary or multiclass matrix."""
        cm_arr = np.array(cm)
        total_samples = int(cm_arr.sum())
        if total_samples == 0:
            return {"status": "EMPTY"}

        if cm_arr.shape == (2, 2):
            tn, fp, fn, tp = cm_arr.ravel()
            fp_rate = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
            fn_rate = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

            dominant_error = "FALSE_POSITIVES" if fp > fn else ("FALSE_NEGATIVES" if fn > fp else "BALANCED")

            return {
                "total_samples": total_samples,
                "true_positives": int(tp),
                "true_negatives": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "false_positive_rate": round(fp_rate, 4),
                "false_negative_rate": round(fn_rate, 4),
                "dominant_error_pattern": dominant_error,
            }
        else:
            # Multiclass
            diagonal = np.diag(cm_arr)
            per_class_accuracy = diagonal / np.maximum(cm_arr.sum(axis=1), 1)
            lowest_class = int(np.argmin(per_class_accuracy))
            return {
                "total_samples": total_samples,
                "classes_count": int(cm_arr.shape[0]),
                "lowest_performing_class_index": lowest_class,
                "lowest_class_accuracy": round(float(per_class_accuracy[lowest_class]), 4),
            }
