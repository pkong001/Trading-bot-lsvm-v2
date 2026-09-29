import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pickle
import warnings
from joblib import load
import logging


def initialize_mt5(LOGIN, PASSWORD, SERVER):

    is_initialized = mt5.initialize()
    logging.info(f"Initilize: {is_initialized}")

    is_logged_in = mt5.login(LOGIN, PASSWORD, SERVER)
    logging.info(f"Login: {is_logged_in}")
    account_info = mt5.account_info()
    logging.info(
        f"| Login: {account_info.login}, | Balance: {account_info.balance}, | Equity: {account_info.equity}"
    )


def initialize_trading_log(history_destination, symbol, timeframe):
    #### RUN ONCE TO CREATE A RECORD.CSV FILE
    try:
        trading_log = pd.read_csv(history_destination)
        logging.info(f"Already have a trading log: {history_destination}")
        return trading_log
    except:
        price_data = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[0]
        open_price = price_data[1]
        high_price = price_data[2]
        low_price = price_data[3]
        close_price = price_data[4]
        time_trade = datetime.fromtimestamp(price_data[0])
        time_trade = time_trade - timedelta(hours=1)
        time_trade_str = time_trade.strftime("%Y-%m-%d %H:%M:%S")
        time_trade_ts = pd.Timestamp(time_trade_str)

        data = {
            "time_trade": [time_trade_ts],
            "open": [open_price],
            "high": [high_price],
            "low": [low_price],
            "close": [close_price],
            "ticket": [""],
            "order_price": [0.0],
            "prediction_long": [False],
            "prediction_short": [False],
        }

        trading_log = pd.DataFrame(data)
        trading_log.to_csv(history_destination, index=False)
        logging.info(f"Created a time_records file: {history_destination}")
        logging.info(f"Trading log initialized: {history_destination}")
        return trading_log


def load_models(long_model, short_model):
    # To ignore error on sklearn version, which proved irrelevant
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lsvm_long = pickle.load(open(f"{long_model}.pkl", "rb"))
        lsvm_short = pickle.load(open(f"{short_model}.pkl", "rb"))
    logging.info(f"Loaded models: {long_model}, {short_model}")
    return lsvm_long, lsvm_short


def load_scaler(scaler):
    # The scaler for long and short are train on the same data interval so we can use just one of them
    scaler = load(f"{scaler}.pkl")
    logging.info(f"Loaded scaler: {scaler}")
    return scaler


def check_allowed_trading_hours(symbol):
    tick = mt5.symbol_info_tick(symbol)
    # check the last price value to determine if the market is closed or available
    if tick.time != 0:
        market_status = True
        # market open
    else:
        market_status = False
        # market close
    return market_status


def make_order(
    strategy_name,
    symbol,
    volume,
    order_type,
    deviation=0,
    magic=123992,
    sl_price_range=3,
    tp_price_range=3,
    spread=0.125,
):

    order_type_dict = {"buy": mt5.ORDER_TYPE_BUY, "sell": mt5.ORDER_TYPE_SELL}

    price_dict = {
        "buy": mt5.symbol_info_tick(symbol).ask,
        "sell": mt5.symbol_info_tick(symbol).bid,
    }

    if order_type == "buy":
        sl = mt5.symbol_info_tick(symbol).ask - (sl_price_range + spread)
        tp = mt5.symbol_info_tick(symbol).ask + (tp_price_range + spread)

    if order_type == "sell":
        sl = mt5.symbol_info_tick(symbol).bid + (sl_price_range + spread)
        tp = mt5.symbol_info_tick(symbol).bid - (tp_price_range + spread)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,  # FLOAT
        "type": order_type_dict[order_type],
        "price": price_dict[order_type],
        "sl": sl,  # FLOAT
        "tp": tp,  # FLOAT
        "deviation": deviation,  # INTERGER
        "magic": magic,  # INTERGER
        "comment": strategy_name,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    order_result = mt5.order_send(request)
    return order_result

class OrderExecutor:
    def __init__(
        self,
        strategy_name,
        symbol,
        volume,
        deviation,
        magic,
        sl_price_range,
        tp_price_range,
        spread,
    ):
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.volume = volume
        self.deviation = deviation
        self.magic = magic
        self.sl_price_range = sl_price_range
        self.tp_price_range = tp_price_range
        self.spread = spread

    def execute_make_order(self, order_type):
        return make_order(
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            volume=self.volume,
            order_type=order_type,
            deviation=self.deviation,
            magic=self.magic,
            sl_price_range=self.sl_price_range,
            tp_price_range=self.tp_price_range,
            spread=self.spread,
        )


def close_all_positions(symbol, deviation=0, magic=123993):
    # Fetch all active positions for the target symbol
    positions = mt5.positions_get(symbol=symbol)
    if len(positions) > 0:
        logging.info(f"Found {len(positions)} active positions for {symbol}. Closing them now...")

        # Loop through each position and close it
        for position_i in positions:
            ticket = position_i.ticket
            volume = position_i.volume
            pos_type = position_i.type  # 0 for BUY, 1 for SELL
            current_tick = mt5.symbol_info_tick(symbol)


            # Determine opposite order type and correct execution price
            if pos_type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                current_price = current_tick.bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                current_price = current_tick.ask

            # Construct the close request
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "position": ticket,  # Ties this trade to the specific open position
                "price": current_price,
                "deviation": deviation,
                "magic": magic,
                "comment": "Python bulk close script",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Send the order to the terminal
            result = mt5.order_send(close_request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logging.info(f"Successfully closed Position #{ticket} ({volume} lots)")
            else:
                logging.error(f"Failed to close Position #{ticket}. Error code: {result.retcode}")



def record_trade(
    trading_log_df,
    history_destination,
    time_trade,
    open,
    high,
    low,
    close,
    ticket,
    order_price,
    prediction_long,
    prediction_short,
):
    new_row = pd.DataFrame(
        {
            "time_trade": [time_trade],
            "open": [open],
            "high": [high],
            "low": [low],
            "close": [close],
            "ticket": [ticket],
            "order_price": [order_price],
            "prediction_long": [prediction_long],
            "prediction_short": [prediction_short],
        }
    )
    trading_log_df = pd.concat([trading_log_df, new_row], axis=0, ignore_index=True)
    trading_log_df.to_csv(history_destination, index=False)
    return trading_log_df
