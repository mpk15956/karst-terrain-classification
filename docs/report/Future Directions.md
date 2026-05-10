## RF vs Gradient Boosting

XGBoost achieved 92.8% (best) vs RF 73-87% typical.

Start with Random Forest, then test XGBoost if time permits Why RF first:

The 73-87% range is RF-based Feature importance: RF gives cleaner interpretability for your "which features matter" analysis

Hyperparameter simplicity: RF has fewer knobs to tune (trees, mtry vs XGBoost's learning rate, max_depth, subsample, etc.)

Literature precedent: Most geomorphometry studies use RF

XGBoost advantage is small: 92.8% vs 87% = 5-6% gain, but at cost of complexity

If you have time later: Add XGBoost as an additional comparison to show TDA competitive with "best possible" baseline.