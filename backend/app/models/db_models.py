from sqlalchemy import Column, String, Float, DateTime, Integer, JSON, Boolean, Text
from datetime import datetime
from ..database import Base


class ActualMetric(Base):
    __tablename__ = "actual_metrics"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    quarter = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AltDataPoint(Base):
    __tablename__ = "alt_data_points"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    source_name = Column(String, nullable=False)
    date = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    raw_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    quarter = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    predicted_value = Column(Float, nullable=False)
    confidence_lower = Column(Float, nullable=True)
    confidence_upper = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)
    features_used = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    quarter = Column(String, nullable=False)
    actual_value = Column(Float, nullable=False)
    predicted_value = Column(Float, nullable=False)
    error = Column(Float, nullable=True)
    pct_error = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    run_at = Column(DateTime, default=datetime.utcnow)
    model_type = Column(String, nullable=True)
    mae = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    directional_accuracy = Column(Float, nullable=True)
    feature_importance = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)


class RefreshLog(Base):
    __tablename__ = "refresh_logs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True, nullable=False)
    source_name = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    success = Column(Boolean, default=False)
    records_fetched = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
