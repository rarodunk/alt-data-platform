"""
Base forecasting model with walk-forward cross-validation,
ensemble of Ridge / ElasticNet / XGBoost / LightGBM / ARIMA.
Models are weighted by 1/CV-MAE so better-performing models dominate.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def _make_ridge():
    return Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=0.1))])


def _make_enet():
    return Pipeline([("scaler", StandardScaler()), ("model", ElasticNet(alpha=0.05, l1_ratio=0.3, max_iter=5000))])


def _make_xgb():
    try:
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=200, max_depth=2, learning_rate=0.05,
                            subsample=0.9, colsample_bytree=0.8,
                            min_child_weight=2, random_state=42, verbosity=0)
    except ImportError:
        return None


def _make_lgbm():
    try:
        import lightgbm as lgb
        return lgb.LGBMRegressor(n_estimators=100, max_depth=3, learning_rate=0.1,
                                  subsample=0.8, random_state=42, verbose=-1)
    except (ImportError, OSError, Exception):
        return None


class _ARIMAWrapper:
    """Thin wrapper so ARIMA fits the same fit/predict interface as sklearn models."""

    def fit(self, X, y):
        from statsmodels.tsa.arima.model import ARIMA
        self._y = np.array(y) if not isinstance(y, np.ndarray) else y
        try:
            model = ARIMA(self._y, order=(1, 1, 1))
            self._result = model.fit()
            self._fitted = True
        except Exception as e:
            logger.warning(f"ARIMA fit failed: {e}")
            self._fitted = False

    def predict(self, X):
        if not getattr(self, "_fitted", False):
            return np.array([self._y[-1]]) if hasattr(self, "_y") and len(self._y) else np.array([0.0])
        try:
            fc = self._result.forecast(steps=1)
            return np.array([float(fc.iloc[0]) if hasattr(fc, "iloc") else float(fc[0])])
        except Exception as e:
            logger.warning(f"ARIMA predict failed: {e}")
            return np.array([self._y[-1]])


def _cv_mae(model_factory, X: pd.DataFrame, y: pd.Series, val_start: int) -> float:
    """Compute walk-forward CV MAE for a single model factory on (X, y)."""
    n = len(X)
    if n < val_start + 2:
        return 1e9
    errors = []
    for t in range(val_start, n):
        X_tr, X_te = X.iloc[:t], X.iloc[[t]]
        y_tr, y_te = y.iloc[:t], float(y.iloc[t])
        try:
            m = model_factory()
            m.fit(X_tr, y_tr)
            pred = float(m.predict(X_te)[0])
            errors.append(abs(y_te - pred))
        except Exception:
            pass
    return float(np.mean(errors)) if errors else 1e9


class BaseForecaster(ABC):
    """Base class for company-specific forecasting models."""

    def __init__(self, target_col: str, min_train_quarters: int = 6):
        self.target_col = target_col
        self.min_train_quarters = min_train_quarters
        self._models: Dict[str, object] = {}
        self._model_weights: Dict[str, float] = {}
        self._feature_names: List[str] = []
        self._fitted = False

    @abstractmethod
    def prepare_features(self, actuals_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        pass

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y: pd.Series):
        """Fit all sub-models; compute CV-MAE-based weights."""
        self._feature_names = list(X.columns)

        import os
        lightweight = os.environ.get("LIGHTWEIGHT_MODELS", "false").lower() == "true"

        candidates = {
            "ridge": _make_ridge,
            "enet": _make_enet,
        }
        if not lightweight:
            if _make_xgb() is not None:
                candidates["xgb"] = _make_xgb
            if _make_lgbm() is not None:
                candidates["lgbm"] = _make_lgbm
            candidates["arima"] = _ARIMAWrapper
        # In lightweight mode: Ridge + ElasticNet only — trains in <5s on free tier

        # Use last ~30% of data for CV weighting
        val_start = max(self.min_train_quarters, int(len(X) * 0.7))

        cv_maes: Dict[str, float] = {}
        for name, factory in candidates.items():
            if name == "arima":
                arima_errors = []
                y_arr = y.values
                for t in range(val_start, len(y_arr)):
                    try:
                        w = _ARIMAWrapper()
                        w.fit(None, y_arr[:t])
                        pred = float(w.predict(None)[0])
                        arima_errors.append(abs(y_arr[t] - pred))
                    except Exception:
                        pass
                cv_maes["arima"] = float(np.mean(arima_errors)) if arima_errors else 1e9
            else:
                cv_maes[name] = _cv_mae(factory, X, y, val_start)

        # Weight = 1 / (MAE + epsilon), then normalize
        raw_weights = {n: 1.0 / (mae + 1e-6) for n, mae in cv_maes.items()}
        total_w = sum(raw_weights.values())
        self._model_weights = {n: w / total_w for n, w in raw_weights.items()}
        logger.info(f"Model weights: { {k: round(v, 3) for k, v in self._model_weights.items()} }")

        # Fit all models on full data
        for name, factory in candidates.items():
            try:
                if name == "arima":
                    m = _ARIMAWrapper()
                    m.fit(X, y)
                else:
                    m = factory()
                    m.fit(X, y)
                self._models[name] = m
            except Exception as e:
                logger.warning(f"Could not fit {name}: {e}")
                self._model_weights.pop(name, None)

        # Renormalize after any fit failures
        total_w = sum(self._model_weights.get(n, 0) for n in self._models)
        if total_w > 0:
            self._model_weights = {n: self._model_weights.get(n, 0) / total_w for n in self._models}

        self._fitted = True
        logger.info(f"Fitted models: {list(self._models.keys())} on {len(X)} samples")

    def predict(self, X: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Returns (point_estimate, lower_bound, upper_bound).
        Point = weighted ensemble mean; bounds use weighted std across models.
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted yet")

        preds = []
        weights = []
        for name, model in self._models.items():
            try:
                p = float(model.predict(X)[0])
                w = self._model_weights.get(name, 1.0 / len(self._models))
                preds.append(p)
                weights.append(w)
            except Exception as e:
                logger.warning(f"Prediction failed for {name}: {e}")

        if not preds:
            return 0.0, 0.0, 0.0

        weights_arr = np.array(weights)
        weights_arr /= weights_arr.sum()
        point = float(np.average(preds, weights=weights_arr))

        if len(preds) > 1:
            variance = float(np.average((np.array(preds) - point) ** 2, weights=weights_arr))
            std = float(np.sqrt(variance))
        else:
            std = point * 0.05

        lower = point - 1.5 * std
        upper = point + 1.5 * std
        return round(point, 4), round(lower, 4), round(upper, 4)

    # ------------------------------------------------------------------
    # Feature importance
    # ------------------------------------------------------------------
    def feature_importance(self) -> Dict[str, float]:
        """Return normalized feature importance (weighted over all models)."""
        importances: Dict[str, float] = {}

        for name, model in self._models.items():
            raw_model = model.steps[-1][1] if hasattr(model, "steps") else model
            fi = None
            if hasattr(raw_model, "feature_importances_"):
                fi = raw_model.feature_importances_
            elif hasattr(raw_model, "coef_"):
                fi = np.abs(raw_model.coef_)

            if fi is not None and len(fi) == len(self._feature_names):
                total = fi.sum()
                if total > 0:
                    fi = fi / total
                w = self._model_weights.get(name, 1.0)
                for fname, score in zip(self._feature_names, fi):
                    importances[fname] = importances.get(fname, 0.0) + float(score) * w

        if importances:
            total = sum(importances.values())
            if total > 0:
                importances = {k: round(v / total * 100, 2) for k, v in importances.items()}

        return dict(sorted(importances.items(), key=lambda x: -x[1]))

    # ------------------------------------------------------------------
    # Cross-validation metrics
    # ------------------------------------------------------------------
    def cv_score(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """TimeSeriesSplit CV — informational only."""
        from sklearn.metrics import mean_absolute_error, mean_squared_error

        n = len(X)
        splits = min(3, n // self.min_train_quarters)
        if splits < 2:
            return {}

        tscv = TimeSeriesSplit(n_splits=splits)
        all_errors = []

        ridge = _make_ridge()
        for train_idx, test_idx in tscv.split(X):
            if len(train_idx) < self.min_train_quarters:
                continue
            X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
            y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
            try:
                ridge.fit(X_tr, y_tr)
                preds = ridge.predict(X_te)
                for a, p in zip(y_te, preds):
                    all_errors.append((a, p))
            except Exception:
                pass

        if not all_errors:
            return {}

        actuals_arr = np.array([e[0] for e in all_errors])
        preds_arr = np.array([e[1] for e in all_errors])
        mae = float(mean_absolute_error(actuals_arr, preds_arr))
        rmse = float(np.sqrt(mean_squared_error(actuals_arr, preds_arr)))
        mape = float(np.mean(np.abs((actuals_arr - preds_arr) / (actuals_arr + 1e-9))) * 100)
        return {"mae": round(mae, 4), "mape": round(mape, 4), "rmse": round(rmse, 4)}
