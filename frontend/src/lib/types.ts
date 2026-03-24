export interface Company {
  id: string;
  name: string;
  ticker: string;
  description: string;
  lastRefreshed: string | null;
  metrics: string[];
  hasModels: boolean;
}

export interface ActualMetric {
  quarter: string;
  period_end: string;
  metric_name: string;
  value: number;
  source: string;
}

export interface Prediction {
  quarter: string;
  period_end: string;
  metric_name: string;
  predicted_value: number;
  confidence_lower: number | null;
  confidence_upper: number | null;
  model_version: string;
  created_at: string;
}

export interface BacktestPoint {
  quarter: string;
  metric_name: string;
  actual_value: number;
  predicted_value: number;
  error: number;
  pct_error: number;
}

export interface BacktestMetrics {
  mae: number;
  mape: number;
  rmse: number;
  directional_accuracy: number;
  n_quarters?: number;
}

export interface SignalPoint {
  date: string;
  value: number;
  source: string;
  metric_name: string;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
}

export interface ModelMetrics {
  mae: number | null;
  mape: number | null;
  rmse: number | null;
  directional_accuracy: number | null;
  feature_importance: Record<string, number>;
  model_type: string;
  run_at: string;
  n_quarters?: number;
}

export interface CompanyOverview {
  company: string;
  name: string;
  ticker: string;
  description: string;
  last_refreshed: string | null;
  actuals: ActualMetric[];
  latest_predictions: Prediction[];
  previous_predictions: Prediction[];
  forward_predictions: Prediction[];
  backtest_results: BacktestPoint[];
  model_metrics: Record<string, ModelMetrics>;
  signals: SignalPoint[];
  refresh_log: RefreshLogEntry[];
}

export interface RefreshLogEntry {
  source_name: string;
  started_at: string;
  completed_at: string | null;
  success: boolean;
  records_fetched: number;
  error_message: string | null;
}
