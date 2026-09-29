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
    close_all_positions,
    record_trade,
    datetime,
    mt5,
    pd,
    logging,
    OrderExecutor
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(r".\bot.log", mode="a"), logging.StreamHandler()],
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

history_name = "trading_log_202609"  # file name for the trading log
history_extension = "csv"  # file extension for the trading log
history_destination = fr".\history\{history_name}.{history_extension}"

# Preparing
logging.info("Preparing")
order_executor = OrderExecutor(
    strategy_name=strategy_name,
    symbol=symbol,
    volume=volume,
    deviation=deviation,
    magic=magic,
    sl_price_range=sl_price_range,
    tp_price_range=tp_price_range,
    spread=spread,
)
initialize_mt5(LOGIN, PASSWORD, SERVER)
trading_log = initialize_trading_log(history_destination, symbol, timeframe)
scaler = load_scaler(r".\models\scaler")
lsvm_long, lsvm_short = load_models(
    r".\models\lsvm_xauusd_long", r".\models\lsvm_xauusd_short"
)

time.sleep(5)
logging.info("Start Trading")
iterations = 0
while True:
    if check_allowed_trading_hours(symbol) == False:
        if mt5.positions_total() > 0:
            close_all_positions(symbol, deviation=deviation, magic=magic)
            logging.debug("Closed all position")

    elif check_allowed_trading_hours(symbol) == True:
        # Get the latest completed bar ( position [0])
        # This is all bid price on both completed and current candlestick
        price_data = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[0]
        current_candle = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[1]
        open = price_data[1]
        high = price_data[2]
        low = price_data[3]
        close = price_data[4]
        time_trade = datetime.fromtimestamp(price_data[0])
        accept_deviation_range = abs(price_data[4] - current_candle[4])

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
        data_raw = np.array([[open, high, low, close]])
        data_scaled = scaler.transform(data_raw)
        
        # Declare variabls for order history
        ticket = ""
        order_price = 0.0

        ### Model LSVM BUY ------ INDICATOR RETRIEVAL ----------------------------------------------------------
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

            ### DECISION MAKING ----------------------------------------------------------
            if (prediction_long == 1 and prediction_short == 1) or (
                prediction_long == 0 and prediction_short == 0
            ):
                logging.info(f"prediction_long: {prediction_long}")
                logging.info(f"prediction_short: {prediction_short}")
                logging.info(
                    "No trade, both long and short are predicted the same, recorded and wait for the next completed candle"
                )

            elif prediction_long == 1 and prediction_short == 0:
                if accept_deviation_range > deviation_delayed_trade:
                    logging.info(
                        f"<<LONG>> Deviation = {accept_deviation_range} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour"
                    )
                elif accept_deviation_range <= deviation_delayed_trade:
                    logging.info(
                        f"<<LONG>> Deviation = {accept_deviation_range} >>> Making a trade"
                    )
                    order_result = order_executor.execute_make_order("buy")
                    if order_result.retcode == mt5.TRADE_RETCODE_DONE:
                        ticket = order_result.order
                        order_price = order_result[4]
                        logging.info(
                            f"<<LONG>> Deviation = {accept_deviation_range} >>> Made a trade at: {time_trade_str}"
                        )
                    else:
                        logging.error("Sending order is not successful")

            elif prediction_long == 0 and prediction_short == 1:
                if accept_deviation_range > deviation_delayed_trade:
                    logging.info(
                        f"<<SHORT>> Deviation = {accept_deviation_range} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour")
                elif accept_deviation_range <= deviation_delayed_trade:
                    logging.info(
                        f"<<SHORT>> Deviation = {accept_deviation_range} >>> Making a trade")
                    order_result = order_executor.execute_make_order("sell")
                    # check if trading order is successful
                    if order_result.retcode == mt5.TRADE_RETCODE_DONE:
                        ticket = order_result.order
                        order_price = order_result[4]
                        logging.info(
                            f"<<SHORT>> Deviation = {accept_deviation_range} >>> Made a trade at: {time_trade_str}"
                        )
                    else:
                        logging.error("Sending order is not successful")

            else:
                raise ValueError(
                    "THIS LOGGING SHOULD NOT BE POSSIBLE TO REACH, CHECK THE LOGIC OF THE PREDICTION MODEL"
                )
            # Record both no trade and successful trade for later analysis and debugging
            trading_log = record_trade(
                            trading_log_df=trading_log,
                            history_destination=history_destination,
                            time_trade=time_trade_ts,
                            open=open,
                            high=high,
                            low=low,
                            close=close,
                            ticket=ticket,
                            order_price=order_price,
                            prediction_long=prediction_long,
                            prediction_short=prediction_short
                        )
    else:
        raise ValueError("Failed on Checking market status")

    time.sleep(1)
