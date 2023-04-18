import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
from account_credentials import LOGIN, PASSWORD, SERVER
import plotly.express as px
import logging
import pickle
import warnings
import numpy as np
import subprocess

# To ignore error on sklearn version, which proved irrelevant
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    lsvm_long = pickle.load(open('lsvm_xauusd_long.pkl','rb'))
    lsvm_short = pickle.load(open('lsvm_xauusd_short.pkl','rb'))

# import Scaler
from joblib import load
scaler = load('scaler_long.pkl')

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler('bot_log.log', mode='a'), logging.StreamHandler()]
)

# Get the logger instance
logger = logging.getLogger()

def check_allowed_trading_hours():
    tick = mt5.symbol_info_tick(symbol)
    # check the last price value to determine if the market is closed or available
    if tick.time != 0:
        market_status = True
        #market open
    else:
        market_status = False
        #market close
    return market_status

def market_order(symbol, volume, order_type, deviation=0, magic=123992):

    order_type_dict = {
        'buy': mt5.ORDER_TYPE_BUY,
        'sell': mt5.ORDER_TYPE_SELL
    }

    price_dict = {
        'buy': mt5.symbol_info_tick(symbol).ask,
        'sell': mt5.symbol_info_tick(symbol).bid
    }

    if order_type == 'buy':
        sl = mt5.symbol_info_tick(symbol).ask - (sl_price_range + spread)
        tp = mt5.symbol_info_tick(symbol).ask + (tp_price_range + spread)
    
    if order_type == 'sell':
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
    return(order_result)


def close_position(position, deviation=0, magic=123992):

    order_type_dict = {
        0: mt5.ORDER_TYPE_SELL,
        1: mt5.ORDER_TYPE_BUY
    }

    price_dict = {
        0: mt5.symbol_info_tick(symbol).bid,
        1: mt5.symbol_info_tick(symbol).ask
    }

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position['ticket'],  # select the position you want to close
        "symbol": symbol,
        "volume": volume,  # FLOAT
        "type": order_type_dict[position['type']],
        "price": price_dict[position['type']],
        "deviation": deviation,  # INTERGER
        "magic": magic,  # INTERGER
        "comment": strategy_name,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    order_result = mt5.order_send(request)
    return(order_result)

def close_positions(order_type):
    order_type_dict = {
        'buy': 0,
        'sell': 1
    }

    if mt5.positions_total() > 0:
        positions = mt5.positions_get()

        positions_df = pd.DataFrame(positions, columns=positions[0]._asdict().keys())

        if order_type != 'all':
            positions_df = positions_df[(positions_df['type'] == order_type_dict[order_type])]

        for i, position in positions_df.iterrows():
            order_result = close_position(position)

            logging.info('order_result: ', order_result)

# Make change to the repository so we don't get an error when define commiting line
import sys
sys.path.insert(0,'current_time')
from create_current_time import get_current_time
get_current_time()


# To run this function you have to work in the correct directory of git bash
def get_go():
    # Run git status command
    check_status = subprocess.check_output(['git', 'status'], stderr=subprocess.STDOUT)
    # Display the output of the Git status command
    print(check_status.decode())

    # Add all changes to the Git staging area
    subprocess.call(['git', 'add', '-A'])

    # Commit the changes with a commit message
    commit_msg = 'Updated at {timestamp}'.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print(commit_msg)
    commit_output = subprocess.check_output(['git', 'commit', '-m', commit_msg], stderr=subprocess.STDOUT)

    # Display the output of the Git commit command
    print(commit_output.decode())

    # Push the changes to the remote repository
    push_output = subprocess.check_output(['git', 'push', 'origin', 'main'], stderr=subprocess.STDOUT)

    # Display the output of the Git push command
    print(push_output.decode())

symbol = 'XAUUSD'
timeframe = mt5.TIMEFRAME_H1
volume = 0.01
strategy_name = 'ML_lsvm'
sl_price_range = 3
tp_price_range = 3
spread = .125
deviation_delayed_trade = 0.300 #abs(current close price - previous complete close price) for example |1900.000 -1901.111| = 1.111
num_positions_max = 5


is_initialized = mt5.initialize()
print('initialize: ', is_initialized)

is_logged_in = mt5.login(LOGIN, PASSWORD, SERVER)
print('logged in: ', is_logged_in)
print('\n')
account_info = mt5.account_info()
print(datetime.now(),
    '| Login: ', account_info.login,
    '| Balance: ', account_info.balance,
    '| Equity: ' , account_info.equity)

print("Bot version v2")
#### RUN ONCE TO CREATE A RECORD.CSV FILE
try:
    time_records = pd.read_csv('time_records_v2.csv')
    logging.debug('Your already have a time_records file: CONTINUE')
except:
    price_data = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[0]
    open_price = price_data[1]
    high_price = price_data[2]
    low_price = price_data[3]
    close_price = price_data[4]
    time_trade = datetime.fromtimestamp(price_data[0])

    time_records = [time_trade]
    records_df = pd.DataFrame({'time_records': time_records})
    records_df.to_csv('time_records_v2.csv', index = False)
    logging.debug('Created a time_records file')

time.sleep(2) # wait for server to start
logging.debug('Running')

# Define some variable before while loop begin
    #This is for pushing go github
running_count = 1
    #Flag for loggin
log_flag1 = False
log_flag2 = False
log_flag3 = False
while True:

    num_positions = mt5.positions_total()
    current_time = mt5.copy_rates_from_pos(symbol,mt5.TIMEFRAME_M1,0,1)
    current_time = datetime.fromtimestamp(current_time[0][0])
    # logging.debug('Current Number of Positions: \033[1m{0}\033[0m (max:{1}) ||| Current Time: \033[1m{2}\033[0m'.format(num_positions,num_positions_max,current_time))



    if check_allowed_trading_hours() == False:
        if num_positions > 0:
            close_position('all')
            logging.debug('Closed all position')

    elif check_allowed_trading_hours() == True:
        # get the latest completed bar ( position [0])
        price_data = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[0] 
        current_candle = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)[1]
        open = price_data[1]
        high = price_data[2]
        low = price_data[3]
        close = price_data[4] #This is all bid price on both completed and current candlestick
        time_trade = datetime.fromtimestamp(price_data[0])
        
        # logging.debug("Complete candle >> Time: {0}, Open: {1}, High: {2}, Low: {3}, Close: {4}".format(time_trade,price_data[1],price_data[2],price_data[3],price_data[4]))
        # logging.debug("Current candle >> Time: {0}, Open: {1}, High: {2}, Low: {3}, Close: \033[1m{4}\033[0m".format(datetime.fromtimestamp(current_candle[0]),current_candle[1],current_candle[2],current_candle[3],current_candle[4]))
        # logging.debug("\033[1mLastest Record Time: {0}\033[0m ||| \033[1mLastest Prediction_L {1}\033[0m ||| \033[1mLastest Prediction_L {2}\033[0m".format(str(time_records['time_records'].tail(1)),int(time_records['prediction'].tail(1).iloc[0]),int(time_records['prediction_s'].tail(1).iloc[0])))

        # Adjust time_trade format
        time_trade_str = time_trade.strftime('%Y-%m-%d %H:%M:%S')
        time_trade_ts = pd.Timestamp(time_trade_str)
        rounded_time_trade = time_trade_ts.floor('H')
        # Adjust imported time_records format
        try:
            time_records['time_records'] = pd.to_datetime(time_records['time_records'], format='%m/%d/%Y %H:%M')
            rounded_time_records = time_records['time_records'].dt.floor('H')
        except:
            try:
                time_records['time_records'] = pd.to_datetime(time_records['time_records'], format='%Y/%m/%d %H:%M:%S')
                rounded_time_records = time_records['time_records'].dt.floor('H')
            except:
                time_records['time_records'] = pd.to_datetime(time_records['time_records'], format='%Y-%m-%d %H:%M:%S')
                rounded_time_records = time_records['time_records'].dt.floor('H')

        # Prepare data for model to predict
        data_raw = np.array([[open, high, low, close]]) # use this np.array instead of reshape
        data_scaled = scaler.transform(data_raw)


                # temp check
        # if rounded_time_trade not in rounded_time_records.values:
        #     print("It's not in  SO LET TRADE")
        #     #print(rounded_time_trade)
        # else:
        #     print("It's in the recorded")
        #     #print(rounded_time_trade)


        ### Model LSVM BUY----------------------------------------------------------------
        if (rounded_time_trade not in rounded_time_records.values) and (num_positions <= 5):
            prediction_long = int(lsvm_long.predict(data_scaled))
            prediction_short = int(lsvm_short.predict(data_scaled))
            if not log_flag3:
                logging.info('prediction_long: {0}'.format(prediction_long))
                logging.info('prediction_short: {0}'.format(prediction_short))
                log_flag3 = True

            if prediction_long == 1 and prediction_short == 1:
                print('')
                new_row = pd.DataFrame({'time_records':[time_trade],
                                                'open':[open],
                                                'high':[high],
                                                'low':[low],
                                                'close':[close],
                                                'prediction':[prediction_long],
                                                'ticket':['none'],
                                                'order price':['none'],
                                                'prediction_s':[prediction_short]})
                time_records = pd.concat([time_records, new_row], axis=0)
                time_records.to_csv('time_records_v2.csv', index = False)
                log_flag3 = False
            if prediction_long == 1 and prediction_short == 0:
                if abs(price_data[4] - current_candle[4]) > deviation_delayed_trade:
                    if not log_flag1:
                        logging.info("<<LONG>> Deviation = {0} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour".format((price_data[4] - current_candle[4])))
                        logging.info("Waiting for Deviation to fall in acceptable range")
                        log_flag1 = True
                elif abs(price_data[4] - current_candle[4]) <= deviation_delayed_trade:
                    logging.info("<<LONG>> Deviation = {0} >>> Making a trade".format((price_data[4] - current_candle[4])))
                    log_flag1 = False
                    order_result = market_order(symbol, volume, 'buy')
                    if order_result.retcode == mt5.TRADE_RETCODE_DONE: # check if trading order is successful
                        logging.info("<<LONG>> Deviation = {0} >>> Made a trade at: {1}".format(abs(price_data[4] - current_candle[4]), time_trade))
                        new_row = pd.DataFrame({'time_records':[time_trade],
                                                'open':[open],
                                                'high':[high],
                                                'low':[low],
                                                'close':[close],
                                                'prediction':[prediction_long],
                                                'ticket':[order_result.order],
                                                'order price':[order_result[4]],
                                                'prediction_s':[prediction_short]})
                        time_records = pd.concat([time_records, new_row], axis=0) # love .append T.T
                        time_records.to_csv('time_records_v2.csv', index = False) # record traded order by timestamp
                        #HW RECORD OPEN HIGH LOW CLOSE, PREDICTION TO CS
                        log_flag3 = False
                    else:
                        "Sending order is not successful"
            
            if prediction_long == 0 and prediction_short == 1:
                if abs(price_data[4] - current_candle[4]) > deviation_delayed_trade:
                    if not log_flag2:
                        logging.info("<<SHORT>> Deviation = {0} >>> No Trade, close price is out of deviation, wait for completed candle in the next hour".format((price_data[4] - current_candle[4])))
                        logging.info("Waiting for Deviation to fall in acceptable range")
                        log_flag2 = True
                elif abs(price_data[4] - current_candle[4]) <= deviation_delayed_trade:
                    logging.info("<<SHORT>> Deviation = {0} >>> Making a trade".format((price_data[4] - current_candle[4])))
                    log_flag2 = False
                    order_result = market_order(symbol, volume, 'sell')
                    if order_result.retcode == mt5.TRADE_RETCODE_DONE: # check if trading order is successful
                        logging.info("<<SHORT>> Deviation = {0} >>> Made a trade at: {1}".format(abs(price_data[4] - current_candle[4]), time_trade))
                        new_row = pd.DataFrame({'time_records':[time_trade],
                                                'open':[open],
                                                'high':[high],
                                                'low':[low],
                                                'close':[close],
                                                'prediction':[prediction_long],
                                                'ticket':[order_result.order],
                                                'order price':[order_result[4]],
                                                'prediction_s':[prediction_short]})
                        time_records = pd.concat([time_records, new_row], axis=0) # love .append T.T
                        time_records.to_csv('time_records_v2.csv', index = False) # record traded order by timestamp
                        log_flag3 = False
                        #HW RECORD OPEN HIGH LOW CLOSE, PREDICTION TO CS
                    else:
                        "Sending order is not successful"
            if prediction_long == 0 and prediction_short == 0:
                print('')
                new_row = pd.DataFrame({'time_records':[time_trade],
                                                'open':[open],
                                                'high':[high],
                                                'low':[low],
                                                'close':[close],
                                                'prediction':[prediction_long],
                                                'ticket':['none'],
                                                'order price':['none'],
                                                'prediction_s':[prediction_short]})
                time_records = pd.concat([time_records, new_row], axis=0)
                time_records.to_csv('time_records_v2.csv', index = False)
                log_flag3 = False
    else:
        raise ValueError('Failed on Checking market status')
    

    # This will push to git main every "running_count" loop
    if (running_count % 3601) == 0:
        try:
            get_go()
            logging.info("pushed to git")
        except:
            logging.info("cannot push")
    running_count += 1


    time.sleep(0.5)
        








