import os
from dotenv import load_dotenv
import numpy as np
import time

from trading_functions import (
    initialize_mt5,
    initialize_trading_log,
    load_models,
    load_scaler,
    check_allowed_trading_hours,
    make_order,
    close_position,
    close_positions,
    record_trade,
    datetime,
    mt5,
    pd,
    pickle,
    warnings,
    load,
    logging,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("bot_log.log", mode="a"), logging.StreamHandler()],
)

# Get the logger instance
logger = logging.getLogger()
logging.info("Logger initialized")

load_dotenv()
logging.info("Loaded .env file")

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
SERVER = os.getenv("SERVER")

symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_H1
volume = 0.01
strategy_name = "Mentis2026"
sl_price_range = 3
tp_price_range = 3
spread = 0.125
deviation = 0
deviation_delayed_trade = 0.300  # abs(current close price - previous complete close price) for example |1900.000 -1901.111| = 1.111
num_positions_max = 5
magic = 123992
file_name = "trading_log_202609"  # file name for the trading log
file_extension = "csv"  # file extension for the trading log
file_destination = f"{file_name}.{file_extension}"

initialize_mt5(LOGIN, PASSWORD, SERVER)
trading_log = initialize_trading_log(file_name, file_extension, symbol, timeframe)
scaler = load_scaler("scaler_long_c")
lsvm_long, lsvm_short = load_models("lsvm_xauusd_long_c", "lsvm_xauusd_short_c")

time.sleep(5)
logging.debug("Start Trading")

# Flag for loggin
log_flag1 = False
log_flag2 = False
log_flag3 = False
iterations = 0
while True:
    if check_allowed_trading_hours(symbol) == False:
        if  mt5.positions_total() > 0:
            close_position("all")
            logging.debug("Closed all position")

    elif check_allowed_trading_hours(symbol) == True:
        # get the latest completed bar ( position [0])
        # This is all bid price on both completed and current candlestick
        price_data = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[0]
        current_candle = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[1]
        open = price_data[1]
        high = price_data[2]
        low = price_data[3]
        close = price_data[4]
        time_trade = datetime.fromtimestamp(price_data[0])

        # Adjust time_trade format
        time_trade_str = time_trade.strftime("%Y-%m-%d %H:%M:%S")
        time_trade_ts = pd.Timestamp(time_trade_str)

        # Check if the current trading time is already in the historical trading log
        pandas_time_series = pd.to_datetime(
            trading_log["time_trade"], format="%Y-%m-%d %H:%M:%S"
        )
        current_time_rounded_str = str(time_trade_ts.floor("h"))
        history_time_rounded_list = list(pandas_time_series.dt.floor("h"))
        history_time_rounded_list_str = [str(i) for i in history_time_rounded_list]

        # Prepare data for model to predict
        data_raw = np.array(
            [[open, high, low, close]]
        )  # use this np.array instead of reshape
        data_scaled = scaler.transform(data_raw)

        ### Model LSVM BUY----------------------------------------------------------------
        if (current_time_rounded_str not in history_time_rounded_list_str) and (
             mt5.positions_total() <= num_positions_max
        ):
            iterations += 1
            logging.info(
                f"Iteration: {iterations} | Current Time: {time_trade_ts} | Current Complete Candle: {time_trade_ts.floor('h')}"
            )
            prediction_long_array = lsvm_long.predict(data_scaled)
            prediction_short_array = lsvm_short.predict(data_scaled)
            prediction_long = float(prediction_long_array[0])
            prediction_short = float(prediction_short_array[0])
            if not log_flag3:
                logging.info("prediction_long: {0}".format(prediction_long))
                logging.info("prediction_short: {0}".format(prediction_short))
                log_flag3 = True

            if prediction_long == 1 and prediction_short == 1:
                trading_log = record_trade(
                    trading_log_df=trading_log,
                    file_name=file_name,
                    file_extension=file_extension,
                    time_trade=time_trade_ts,
                    open=open,
                    high=high,
                    low=low,
                    close=close,
                    ticket="",
                    order_price=0.0,
                    prediction_long=prediction_long,
                    prediction_short=prediction_short,
                )
                log_flag3 = False
            if prediction_long == 1 and prediction_short == 0:
                if abs(price_data[4] - current_candle[4]) > deviation_delayed_trade:
                    if not log_flag1:
                        logging.info(
                            "<<LONG>> Deviation = {0} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour".format(
                                (price_data[4] - current_candle[4])
                            )
                        )
                        log_flag1 = True
                elif abs(price_data[4] - current_candle[4]) <= deviation_delayed_trade:
                    logging.info(
                        "<<LONG>> Deviation = {0} >>> Making a trade".format(
                            (price_data[4] - current_candle[4])
                        )
                    )
                    log_flag1 = False
                    order_result = make_order(
                        strategy_name=strategy_name,
                        symbol=symbol,
                        volume=volume,
                        order_type="buy",
                        deviation=deviation,
                        magic=magic,
                        sl_price_range=sl_price_range,
                        tp_price_range=tp_price_range,
                        spread=spread,
                    )
                    if (
                        order_result.retcode == mt5.TRADE_RETCODE_DONE
                    ):  # check if trading order is successful
                        logging.info(
                            "<<LONG>> Deviation = {0} >>> Made a trade at: {1}".format(
                                abs(price_data[4] - current_candle[4]), time_trade
                            )
                        )
                        trading_log = record_trade(
                            trading_log_df=trading_log,
                            file_name=file_name,
                            file_extension=file_extension,
                            time_trade=time_trade_ts,
                            open=open,
                            high=high,
                            low=low,
                            close=close,
                            ticket=order_result.order,
                            order_price=order_result[4],
                            prediction_long=prediction_long,
                            prediction_short=prediction_short,
                        )
                        log_flag3 = False
                    else:
                        "Sending order is not successful"

            if prediction_long == 0 and prediction_short == 1:
                if abs(price_data[4] - current_candle[4]) > deviation_delayed_trade:
                    if not log_flag2:
                        logging.info(
                            "<<SHORT>> Deviation = {0} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour".format(
                                (price_data[4] - current_candle[4])
                            )
                        )
                        log_flag2 = True
                elif abs(price_data[4] - current_candle[4]) <= deviation_delayed_trade:
                    logging.info(
                        "<<SHORT>> Deviation = {0} >>> Making a trade".format(
                            (price_data[4] - current_candle[4])
                        )
                    )
                    log_flag2 = False
                    order_result = make_order(
                        strategy_name=strategy_name,
                        symbol=symbol,
                        volume=volume,
                        order_type="sell",
                        deviation=deviation,
                        magic=magic,
                        sl_price_range=sl_price_range,
                        tp_price_range=tp_price_range,
                        spread=spread,
                    )
                    # check if trading order is successful
                    if order_result.retcode == mt5.TRADE_RETCODE_DONE:
                        logging.info(
                            "<<SHORT>> Deviation = {0} >>> Made a trade at: {1}".format(
                                abs(price_data[4] - current_candle[4]), time_trade
                            )
                        )
                        trading_log = record_trade(
                            trading_log_df=trading_log,
                            file_name=file_name,
                            file_extension=file_extension,
                            time_trade=time_trade_ts,
                            open=open,
                            high=high,
                            low=low,
                            close=close,
                            ticket=order_result.order,
                            order_price=order_result[4],
                            prediction_long=prediction_long,
                            prediction_short=prediction_short,
                        )
                        log_flag3 = False
                    else:
                        "Sending order is not successful"
            if prediction_long == 0 and prediction_short == 0:
                trading_log = record_trade(
                    trading_log_df=trading_log,
                    file_name=file_name,
                    file_extension=file_extension,
                    time_trade=time_trade_ts,
                    open=open,
                    high=high,
                    low=low,
                    close=close,
                    ticket="",
                    order_price=0.0,
                    prediction_long=prediction_long,
                    prediction_short=prediction_short,
                )
                log_flag3 = False
    else:
        raise ValueError("Failed on Checking market status")

    time.sleep(1)
