"""Implements the pass success probability component."""
from typing import Any, Dict, List

import mlflow
import numpy as np
import pandas as pd
import pytorch_lightning as pl
from typing import Callable, Dict, List, Optional, Union
from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier, XGBRegressor
from gplearn.genetic import SymbolicClassifier
from .base import (
    exPressComponent,
    expressXGBoostComponent,
    expressSymbolicComponent

)

class PressingComponent(exPressComponent):
    """The pass success probability component.

    From any given game situation where a player controls the ball, the model
    estimates the success probability of a pass attempted towards a potential
    destination location.
    """

    component_name = "pass_success"

    def _get_metrics(self, y, y_hat):
        y_pred = y_hat > 0.5
        return {
            "precision": precision_score(y, y_pred),
            "recall": recall_score(y, y_pred),
            "f1": f1_score(y, y_pred),
            "log_loss": log_loss(y, y_hat),
            "brier": brier_score_loss(y, y_hat),
            "roc_auc": roc_auc_score(y, y_hat),
        }

class XGBoostComponent(PressingComponent, expressXGBoostComponent):
    """A XGBoost model based on handcrafted features."""

    def __init__(
        self, model: XGBClassifier, features: Dict[str, List[str]], label: List[str] = ["counterpress"]
    ):
        super().__init__(
            model=model,
            features=features,
            label=label,
        )

    def train(self, dataset, param_grid=None, optimized_metric=None, **train_cfg) -> Optional[float]:
        mlflow.xgboost.autolog()

        # Load data
        data = self.initialize_dataset(dataset)
        X_train, y_train = data.features, data.labels
        X_train = X_train.fillna(0)

        if param_grid:
            # GridSearchCV to find the best hyperparameters
            grid_search = GridSearchCV(
                estimator=self.model,
                param_grid=param_grid,
                scoring=optimized_metric if optimized_metric else 'accuracy',
                cv=5,
                verbose=1,
                n_jobs=-1,
                refit=True     
            )
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_
            print("Best Parameters from GridSearchCV:", grid_search.best_params_)
            print("Best Score from GridSearchCV:", grid_search.best_score_)
        else:
            X_train, X_val, y_train, y_val = train_test_split(
                X_train, y_train, test_size=0.2, stratify=y_train
            )
            self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], **train_cfg)

    def test(self, dataset) -> Dict[str, float]:
        data = self.initialize_dataset(dataset)
        X_test, y_test = data.features, data.labels
        X_test = X_test.fillna(0)
        
        if isinstance(self.model, XGBClassifier):
            y_hat = self.model.predict_proba(X_test)[:, 1]
        else:
            raise AttributeError(f"Unsupported xgboost model: {type(self.model)}")
        return self._get_metrics(y_test, y_hat)

    def predict(self, dataset) -> pd.Series:
        data = self.initialize_dataset(dataset)
        X_test, y_test = data.features, data.labels
        X_test = X_test.fillna(0)

        if isinstance(self.model, XGBClassifier):
            y_hat = self.model.predict_proba(X_test)[:, 1]
        else:
            raise AttributeError(f"Unsupported xgboost model: {type(self.model)}")
        return pd.Series(y_hat, index=X_test.index)


class SymbolicComponent(PressingComponent, expressSymbolicComponent):
    """A XGBoost model based on handcrafted features."""

    def __init__(
        self, model: SymbolicClassifier, features: Dict[str, List[str]], label: List[str] = ["counterpress"]
    ):
        super().__init__(
            model=model,
            features=features,
            label=label,
        )
        self.scaler = StandardScaler()

    def train(self, dataset, optimized_metric=None, **train_cfg) -> Optional[float]:
        # Load data
        data = self.initialize_dataset(dataset)
        X_train, y_train = data.features, data.labels
        X_train = X_train.fillna(0)

        #X_train = self.scaler.fit_transform(X_train)
        self.model.fit(X_train, y_train, **train_cfg)

    def test(self, dataset) -> Dict[str, float]:
        data = self.initialize_dataset(dataset)
        X_test, y_test = data.features, data.labels
        #X_test = self.scaler.transform(X_test)
        X_test = X_test.fillna(0)
        
        if isinstance(self.model, SymbolicClassifier):
            y_hat = self.model.predict_proba(X_test)[:, 1]
        else:
            raise AttributeError(f"Unsupported xgboost model: {type(self.model)}")
        return self._get_metrics(y_test, y_hat)
    
    def predict(self, dataset) -> pd.Series:
        data = self.initialize_dataset(dataset)
        X_test, y_test = data.features, data.labels
        #X_test = self.scaler.transform(X_test)
        X_test = X_test.fillna(0)

        if isinstance(self.model, SymbolicClassifier):
            y_hat = self.model.predict_proba(X_test)[:, 1]
        else:
            raise AttributeError(f"Unsupported Symbolic model: {type(self.model)}")
        return pd.Series(y_hat, index=X_test.index)