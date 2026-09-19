"""Leak-free feature preprocessing and dataset splitting pipeline."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split,
)
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml_mcp.domain.value_objects import (
    SplitStrategy,
    SplitStrategyType,
    TaskType,
)


class PreprocessingPipeline:
    """Encapsulates dataset partitioning and strict leak-free feature transformations."""

    def __init__(
        self,
        target_column: str,
        task_type: TaskType,
        feature_columns: list[str] | None = None,
        split_strategy: SplitStrategy | None = None,
    ) -> None:
        self.target_column = target_column
        self.task_type = task_type
        self.feature_columns = feature_columns
        self.split_strategy = split_strategy or SplitStrategy()
        self.transformer: ColumnTransformer | None = None
        self.numeric_features: list[str] = []
        self.categorical_features: list[str] = []

    def prepare_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        """Validate presence of target and features and separate X and y."""
        if self.target_column not in df.columns:
            raise ValueError(
                f"Target column '{self.target_column}' not found in dataset columns: {list(df.columns)}"
            )

        y = df[self.target_column]
        if self.feature_columns:
            missing = [c for c in self.feature_columns if c not in df.columns]
            if missing:
                raise ValueError(f"Feature columns {missing} missing from dataset")
            X = df[self.feature_columns].copy()
        else:
            X = df.drop(columns=[self.target_column]).copy()

        # Identify numeric vs categorical columns
        self.numeric_features = list(X.select_dtypes(include=[np.number]).columns)
        self.categorical_features = [c for c in X.columns if c not in self.numeric_features]

        return X, y

    def build_transformer(self) -> ColumnTransformer:
        """Construct scikit-learn ColumnTransformer for leak-free transformations."""
        transformers = []
        if self.numeric_features:
            from sklearn.pipeline import Pipeline

            num_pipe = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]
            )
            transformers.append(("numeric", num_pipe, self.numeric_features))

        if self.categorical_features:
            from sklearn.pipeline import Pipeline

            cat_pipe = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]
            )
            transformers.append(("categorical", cat_pipe, self.categorical_features))

        return ColumnTransformer(transformers=transformers, remainder="drop")

    def split_data(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """Split data into (X_train, X_val, y_train, y_val) folds based on SplitStrategy."""
        strat = self.split_strategy
        seed = strat.random_seed

        if strat.strategy == SplitStrategyType.TRAIN_TEST_SPLIT:
            stratify = (
                y
                if self.task_type
                in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION)
                else None
            )
            X_tr, X_val, y_tr, y_val = train_test_split(
                X,
                y,
                test_size=strat.test_size,
                random_state=seed,
                shuffle=strat.shuffle,
                stratify=stratify,
            )
            return [(X_tr, X_val, y_tr, y_val)]

        elif strat.strategy == SplitStrategyType.STRATIFIED_K_FOLD:
            skf = StratifiedKFold(n_splits=strat.n_splits, shuffle=strat.shuffle, random_state=seed)
            folds = []
            for train_idx, val_idx in skf.split(X, y):
                folds.append(
                    (X.iloc[train_idx], X.iloc[val_idx], y.iloc[train_idx], y.iloc[val_idx])
                )
            return folds

        elif strat.strategy == SplitStrategyType.K_FOLD:
            kf = KFold(n_splits=strat.n_splits, shuffle=strat.shuffle, random_state=seed)
            folds = []
            for train_idx, val_idx in kf.split(X):
                folds.append(
                    (X.iloc[train_idx], X.iloc[val_idx], y.iloc[train_idx], y.iloc[val_idx])
                )
            return folds

        elif strat.strategy == SplitStrategyType.TIME_SERIES_SPLIT:
            tscv = TimeSeriesSplit(n_splits=strat.n_splits)
            folds = []
            for train_idx, val_idx in tscv.split(X):
                folds.append(
                    (X.iloc[train_idx], X.iloc[val_idx], y.iloc[train_idx], y.iloc[val_idx])
                )
            return folds

        else:
            raise ValueError(f"Unknown split strategy: {strat.strategy}")

    def fit_transform_folds(
        self,
        df: pd.DataFrame,
    ) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, ColumnTransformer]]:
        """Separate, split, and fit transformers strictly on train folds to prevent data leakage."""
        X, y = self.prepare_data(df)
        raw_folds = self.split_data(X, y)

        transformed_folds = []
        for X_tr_raw, X_val_raw, y_tr_raw, y_val_raw in raw_folds:
            transformer = self.build_transformer()
            # STRICT LEAK-FREE RULE: fit strictly on train fold
            X_tr_proc = transformer.fit_transform(X_tr_raw)
            # transform validation fold using fitted statistics
            X_val_proc = transformer.transform(X_val_raw)

            y_tr_arr = np.asarray(y_tr_raw)
            y_val_arr = np.asarray(y_val_raw)

            transformed_folds.append((X_tr_proc, X_val_proc, y_tr_arr, y_val_arr, transformer))

        # Retain last transformer as primary fitted reference
        if transformed_folds:
            self.transformer = transformed_folds[-1][4]

        return transformed_folds
