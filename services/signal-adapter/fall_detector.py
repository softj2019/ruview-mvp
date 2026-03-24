"""
Fall Detection ML Framework — Phase 3-1~3-3.

ML-based fall detection with feature extraction and ensemble classification.

Features extracted from CSI data:
- jerk: rate of change of acceleration (d³x/dt³)
- peak_amplitude: maximum signal change during event
- duration: time of impact event (ms)
- recovery_slope: how fast signal returns to baseline after fall
- pre_fall_motion: motion level before the event
"""

import csv
import os
from pathlib import Path

import numpy as np

# Training data directory (next to this file)
_DATA_DIR = Path(__file__).parent / "fall_data"
_TRAINING_CSV = _DATA_DIR / "training.csv"
_MODEL_PATH = _DATA_DIR / "fall_model.joblib"

FEATURE_NAMES = ["jerk", "peak_amplitude", "duration", "recovery_slope", "pre_fall_motion"]


def extract_features(motion_history: list[float], sample_rate: float) -> dict:
    """Extract fall-detection features from a motion history window.

    Args:
        motion_history: Recent motion index values (at least 10 samples recommended).
        sample_rate: CSI frame rate in Hz (e.g. 20.0).

    Returns:
        Dict with keys: jerk, peak_amplitude, duration, recovery_slope, pre_fall_motion.
    """
    arr = np.array(motion_history, dtype=np.float64)
    n = len(arr)

    if n < 4:
        return {
            "jerk": 0.0,
            "peak_amplitude": 0.0,
            "duration": 0.0,
            "recovery_slope": 0.0,
            "pre_fall_motion": 0.0,
        }

    # --- jerk: max of 3rd-order difference (approximation of d³x/dt³) ---
    if n >= 4:
        d3 = np.diff(arr, n=3)
        jerk = float(np.max(np.abs(d3))) * (sample_rate ** 3)
    else:
        jerk = 0.0

    # --- peak_amplitude: max deviation from baseline ---
    # Baseline = mean of the first quarter of the window (pre-event)
    baseline_len = max(n // 4, 1)
    baseline = float(np.mean(arr[:baseline_len]))
    peak_amplitude = float(np.max(arr) - baseline)

    # --- duration: time above 2x baseline (in ms) ---
    threshold = 2.0 * max(baseline, 0.5)  # floor at 0.5 to avoid zero threshold
    above_mask = arr > threshold
    samples_above = int(np.sum(above_mask))
    duration = (samples_above / sample_rate) * 1000.0  # convert to ms

    # --- recovery_slope: slope of signal after peak ---
    peak_idx = int(np.argmax(arr))
    if peak_idx < n - 2:
        post_peak = arr[peak_idx:]
        if len(post_peak) >= 2:
            # Fit linear regression to post-peak segment
            t = np.arange(len(post_peak)) / sample_rate
            if np.std(t) > 0:
                recovery_slope = float(np.polyfit(t, post_peak, 1)[0])
            else:
                recovery_slope = 0.0
        else:
            recovery_slope = 0.0
    else:
        recovery_slope = 0.0

    # --- pre_fall_motion: mean of 5 samples before peak ---
    pre_start = max(0, peak_idx - 5)
    pre_end = max(pre_start, peak_idx)
    if pre_end > pre_start:
        pre_fall_motion = float(np.mean(arr[pre_start:pre_end]))
    else:
        pre_fall_motion = 0.0

    return {
        "jerk": round(jerk, 4),
        "peak_amplitude": round(peak_amplitude, 4),
        "duration": round(duration, 2),
        "recovery_slope": round(recovery_slope, 4),
        "pre_fall_motion": round(pre_fall_motion, 4),
    }


class FallDetector:
    """ML-based fall detection with feature extraction and ensemble classification.

    Uses an ensemble of SVC, RandomForest, and GradientBoosting classifiers.
    Falls back to threshold-based detection when no trained model is available.
    """

    # Threshold fallback parameters (used when no ML model exists)
    JERK_THRESHOLD = 5000.0
    PEAK_AMP_THRESHOLD = 5.0
    DURATION_MIN_MS = 50.0
    DURATION_MAX_MS = 2000.0

    def __init__(self):
        self._model = None
        self._model_name: str | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load saved model from disk if it exists."""
        if _MODEL_PATH.exists():
            try:
                import joblib
                self._model = joblib.load(str(_MODEL_PATH))
                self._model_name = type(self._model).__name__
                print(f"[fall-detector] Loaded model: {self._model_name}")
            except Exception as e:
                print(f"[fall-detector] Failed to load model: {e}")
                self._model = None

    def detect(self, features: dict) -> tuple[bool, float]:
        """Detect fall from extracted features.

        Args:
            features: Dict with keys from FEATURE_NAMES.

        Returns:
            (is_fall, confidence) where confidence is 0.0-1.0.
        """
        if self._model is not None:
            return self._detect_ml(features)
        return self._detect_threshold(features)

    def _detect_ml(self, features: dict) -> tuple[bool, float]:
        """ML-based detection using trained ensemble model."""
        x = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])
        try:
            prediction = self._model.predict(x)[0]
            # Try to get probability if available
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(x)[0]
                # proba[1] = probability of class 1 (fall)
                confidence = float(proba[1]) if len(proba) > 1 else float(proba[0])
            elif hasattr(self._model, "decision_function"):
                # SVC without probability — use sigmoid of decision function
                decision = float(self._model.decision_function(x)[0])
                confidence = 1.0 / (1.0 + np.exp(-decision))
            else:
                confidence = 0.85 if prediction else 0.15
            is_fall = bool(prediction)
            return (is_fall, round(confidence, 4))
        except Exception as e:
            print(f"[fall-detector] ML prediction error: {e}")
            return self._detect_threshold(features)

    def _detect_threshold(self, features: dict) -> tuple[bool, float]:
        """Threshold-based fallback when no ML model is available."""
        jerk = features.get("jerk", 0.0)
        peak_amp = features.get("peak_amplitude", 0.0)
        duration = features.get("duration", 0.0)
        recovery_slope = features.get("recovery_slope", 0.0)

        score = 0.0
        # Jerk contribution (0-0.35)
        if jerk > self.JERK_THRESHOLD:
            score += min(jerk / (self.JERK_THRESHOLD * 4), 0.35)
        # Peak amplitude contribution (0-0.30)
        if peak_amp > self.PEAK_AMP_THRESHOLD:
            score += min(peak_amp / (self.PEAK_AMP_THRESHOLD * 4), 0.30)
        # Duration in valid range contribution (0-0.20)
        if self.DURATION_MIN_MS <= duration <= self.DURATION_MAX_MS:
            score += 0.20
        # Negative recovery slope (signal drops after peak = fall pattern) (0-0.15)
        if recovery_slope < -1.0:
            score += min(abs(recovery_slope) / 20.0, 0.15)

        is_fall = score >= 0.5
        confidence = min(score, 1.0)
        return (is_fall, round(confidence, 4))

    def record_event(self, features: dict, label: bool) -> None:
        """Record a fall/non-fall event to training CSV.

        Args:
            features: Dict with keys from FEATURE_NAMES.
            label: True = fall, False = not a fall.
        """
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        file_exists = _TRAINING_CSV.exists() and _TRAINING_CSV.stat().st_size > 0

        with open(_TRAINING_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(FEATURE_NAMES + ["label"])
            row = [features.get(name, 0.0) for name in FEATURE_NAMES]
            row.append(1 if label else 0)
            writer.writerow(row)

    def train(self) -> dict:
        """Train ensemble from collected CSV data.

        Uses sklearn SVC, RandomForestClassifier, GradientBoostingClassifier.
        Performs 5-fold cross-validation and saves the best model.

        Returns:
            Dict with training results (best_model, cv_scores, etc.).
        """
        if not _TRAINING_CSV.exists():
            return {"error": "No training data found", "status": "failed"}

        # Load training data
        import joblib
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC

        data = []
        labels = []
        with open(_TRAINING_CSV, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    features = [float(row[name]) for name in FEATURE_NAMES]
                    label = int(row["label"])
                    data.append(features)
                    labels.append(label)
                except (KeyError, ValueError):
                    continue

        if len(data) < 10:
            return {
                "error": f"Need at least 10 samples, got {len(data)}",
                "status": "failed",
                "samples": len(data),
            }

        X = np.array(data)
        y = np.array(labels)

        # Check class balance
        n_falls = int(np.sum(y == 1))
        n_non_falls = int(np.sum(y == 0))
        if n_falls == 0 or n_non_falls == 0:
            return {
                "error": "Need both fall and non-fall samples",
                "status": "failed",
                "falls": n_falls,
                "non_falls": n_non_falls,
            }

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Define ensemble candidates
        candidates = {
            "SVC": SVC(kernel="rbf", probability=True, class_weight="balanced"),
            "RandomForest": RandomForestClassifier(
                n_estimators=100, class_weight="balanced", random_state=42
            ),
            "GradientBoosting": GradientBoostingClassifier(
                n_estimators=100, random_state=42
            ),
        }

        # 5-fold cross-validation
        n_folds = min(5, min(n_falls, n_non_falls))
        n_folds = max(n_folds, 2)  # at least 2-fold

        results = {}
        best_name = None
        best_score = -1.0
        best_model = None

        for name, clf in candidates.items():
            try:
                scores = cross_val_score(clf, X_scaled, y, cv=n_folds, scoring="f1")
                mean_score = float(np.mean(scores))
                results[name] = {
                    "cv_scores": [round(s, 4) for s in scores.tolist()],
                    "mean_f1": round(mean_score, 4),
                }
                if mean_score > best_score:
                    best_score = mean_score
                    best_name = name
                    best_model = clf
            except Exception as e:
                results[name] = {"error": str(e)}

        if best_model is None:
            return {"error": "All classifiers failed", "status": "failed", "results": results}

        # Train best model on full dataset and save
        best_model.fit(X_scaled, y)

        # Save model + scaler together via a simple wrapper
        from sklearn.pipeline import Pipeline
        pipeline = Pipeline([("scaler", scaler), ("classifier", best_model)])
        pipeline.fit(X, y)  # re-fit pipeline end-to-end

        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, str(_MODEL_PATH))

        # Reload into detector
        self._model = pipeline
        self._model_name = best_name

        print(f"[fall-detector] Trained and saved model: {best_name} (F1={best_score:.4f})")

        return {
            "status": "success",
            "best_model": best_name,
            "best_f1": round(best_score, 4),
            "samples": len(data),
            "falls": n_falls,
            "non_falls": n_non_falls,
            "results": results,
        }

    def get_training_stats(self) -> dict:
        """Get training data statistics.

        Returns:
            Dict with total samples, class balance, model status.
        """
        stats = {
            "total_samples": 0,
            "falls": 0,
            "non_falls": 0,
            "model_loaded": self._model is not None,
            "model_name": self._model_name,
            "training_file": str(_TRAINING_CSV),
        }

        if not _TRAINING_CSV.exists():
            return stats

        try:
            with open(_TRAINING_CSV, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        label = int(row["label"])
                        stats["total_samples"] += 1
                        if label == 1:
                            stats["falls"] += 1
                        else:
                            stats["non_falls"] += 1
                    except (KeyError, ValueError):
                        continue
        except Exception:
            pass

        if stats["total_samples"] > 0:
            stats["fall_ratio"] = round(stats["falls"] / stats["total_samples"], 4)
        else:
            stats["fall_ratio"] = 0.0

        return stats
