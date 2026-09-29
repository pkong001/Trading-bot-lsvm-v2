# Trading Bot LSVM v2

This project is an experimental automated trading bot for XAUUSD (gold) on MetaTrader 5. It uses pre-trained long and short LSVM classifiers to turn hourly price data into trading signals and can submit buy or sell orders automatically.

## How It Works

The bot reads recent XAUUSD open, high, low, and close prices, scales those values, and passes them to separate long and short models. Based on the predictions, it may open a buy or sell position after checking the configured price-movement threshold. Orders include configured stop-loss and take-profit levels. The bot runs continuously and records predictions and trade details in a CSV trading log.

## Main Project Files

- `main.py` contains the trading loop and strategy settings.
- `trading_functions.py` contains the MetaTrader 5, model-loading, order, and trade-logging helpers.
- `models/` contains the serialized classifier and scaler artifacts.
- `data/` and `history/` contain price and trading-history CSV files.
- `debug*.ipynb` notebooks are used for investigation and debugging.
- `backup/` contains older bot versions and simulation files.

This software can place real trades. Use a demo account for testing and verify the strategy and risk settings before running it on a live account.