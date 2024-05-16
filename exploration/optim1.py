import sys
sys.path.append("../")
import pandas as pd
import datetime as dt
import math
import plotly.graph_objects as go
from plotting import CandlePlot
from tqdm import tqdm
from tabulate import tabulate
import pickle as pkl
import random
pd.set_option("display.max_columns", None)

class Data:
    
    def __init__(self, path):
        self.df = {
            'raw': pd.read_pickle(path)
        }
        if 'time' in self.df['raw'].columns:
            self.df['raw']['time'] = [ x.replace(tzinfo=None) for x in self.df['raw']['time']]

    def __repr__(self) -> str:
        repr = str()
        for name, df in self.df.items():
            repr = repr + name + ':\n' + str(df.head(3)) + '\n'
        return repr

    def shorten(self, name: str, rows: int, direction: int, source: str='raw', cols: list=None):
        '''Create new dataframe with specified list of columns and number of rows
        direction: 1 if data should be selected from top and -1 if from bottom
        '''
        assert (direction != 1 or direction != -1), 'direction must be 1 (top) or -1 (bottom)'
        
        if cols == None:
            cols = self.df[source].columns
        if direction == 1:
            self.df[name] = self.df[source][cols].iloc[:rows].copy()
        else:
            self.df[name] = self.df[source][cols].iloc[-rows:].copy()
        self.df[name].reset_index(drop=True, inplace=True)

    def add_columns(self, name: str, cols: list):
        '''Add new columns to component dataframes
        '''        
        exist_cols = list(self.df[name].columns)
        cols = exist_cols + cols
        self.df[name] = self.df[name].reindex(columns = cols) 

    def prepare_fast_data(self, name: str):
        '''Prepare data as an array for fast processing
        fcols = {col1: col1_index, col2: col2_index, .... }     
        fdata = [array[col1], array[col2], array[col3], .... ]
        Accessed by: self.fdata[fcols[column_name]] for whole column or
                     self.fdata[fcols[column_name]][row_index] for a specific row item
        '''
        self.fcols = dict()
        for i in range(len(self.df[name].columns)):
            self.fcols[self.df[name].columns[i]] = i
        self.fdata = [self.df[name][col].array for col in self.df[name].columns]


d = Data("D:/OneDrive/Studies/forex_bot/souvik/data/EUR_USD_M5.pkl")

our_cols = ['time', 'bid_o', 'bid_h', 'bid_l', 'bid_c', 'ask_o', 'ask_h', 'ask_l', 'ask_c', 'mid_c']

BUY = 1
SELL = -1
CLOSE = 2
NONE = 0
BASE_TRADESIZE = 1000
MARGIN_RATE = 0.03333333333333
INIT_BAL = 1000

def set_price(i: int, buy_price: float, sell_price: float, reward: float):
    d.fdata[d.fcols['buy_price']][i] = buy_price
    d.fdata[d.fcols['buy_tp_price']][i] = buy_price + reward
    d.fdata[d.fcols['sell_price']][i] = sell_price
    d.fdata[d.fcols['sell_tp_price']][i] = sell_price - reward

def set_position_size(i: int, rr: float, cushion: float, new_streak: bool=False):
    if new_streak == True:
        # print('i', i, 'rr', rr, 'cus', cushion, 'new_streak', new_streak)
        d.fdata[d.fcols['position_size']][i] = BASE_TRADESIZE
        d.fdata[d.fcols['cum_position_size']][i] = BASE_TRADESIZE
    else:
        prev_size = d.fdata[d.fcols['cum_position_size']][i-1]
        # print('i', i, 'prev_size', prev_size, 'rr', rr, 'cus', cushion,'new_streak', new_streak)
        d.fdata[d.fcols['position_size']][i] = math.ceil(prev_size / rr * cushion)
        d.fdata[d.fcols['cum_position_size']][i] = prev_size + d.fdata[d.fcols['position_size']][i]

def set_ac_bal(i: int, prev_signal: int, reverse: bool):
    if reverse == True: # Stop loss
        sell_at = 'ask_l'
        buy_at = 'bid_h'
    else: # Take profit
        sell_at = 'ask_h'
        buy_at = 'bid_l'

    if prev_signal == BUY:
        d.fdata[d.fcols['realised_pl']][i] = (d.fdata[d.fcols[sell_at]][i] - d.fdata[d.fcols['buy_price']][i-1]) * \
            d.fdata[d.fcols['position_size']][i-1]
    elif prev_signal == SELL:
        d.fdata[d.fcols['realised_pl']][i] = (d.fdata[d.fcols['sell_price']][i-1] - d.fdata[d.fcols[buy_at]][i]) * \
            d.fdata[d.fcols['position_size']][i-1]
    d.fdata[d.fcols['ac_bal']][i] = d.fdata[d.fcols['ac_bal']][i-1] + d.fdata[d.fcols['realised_pl']][i]
               

def make_trade(i: int, signal: int, risk: float, rr: float, cushion: float, new_streak=False, reverse=True) -> int:
    # print(i, 'open_position')
    if reverse:
        prev_signal = BUY if signal == SELL else SELL
    else:
        prev_signal = BUY if signal == BUY else SELL
    d.fdata[d.fcols['signal']][i] = signal
    set_position_size(i=i, rr=rr, cushion=cushion, new_streak=new_streak)

    if new_streak == True:
        d.fdata[d.fcols['trade_no']][i] = 1
        if i == 0:
            d.fdata[d.fcols['streak_no']][i] = 1
            d.fdata[d.fcols['ac_bal']][i] = INIT_BAL
        else:
            d.fdata[d.fcols['streak_no']][i] = d.fdata[d.fcols['streak_no']][i-1] + 1
            set_ac_bal(i, prev_signal, reverse)
        d.fdata[d.fcols['realised_pl']][i] = 0 # Overwrite value for new streak

    else:
        d.fdata[d.fcols['trade_no']][i] = d.fdata[d.fcols['trade_no']][i-1] + 1
        d.fdata[d.fcols['streak_no']][i] = d.fdata[d.fcols['streak_no']][i-1]
        set_ac_bal(i, prev_signal, reverse)

    if signal == BUY:
        buy_price = d.fdata[d.fcols['bid_h']][i]
        sell_price = buy_price - risk
        set_price(i, buy_price, sell_price, risk * rr)
        d.fdata[d.fcols['unrealised_pl']][i] = \
            (d.fdata[d.fcols['mid_c']][i] - d.fdata[d.fcols['buy_price']][i]) * d.fdata[d.fcols['position_size']][i]
    elif signal == SELL:
        sell_price = d.fdata[d.fcols['ask_l']][i]
        buy_price = sell_price + risk
        set_price(i, buy_price, sell_price, risk * rr)
        d.fdata[d.fcols['unrealised_pl']][i] = \
            (d.fdata[d.fcols['sell_price']][i] - d.fdata[d.fcols['mid_c']][i]) * d.fdata[d.fcols['position_size']][i]

    d.fdata[d.fcols['margin_used']][i] = d.fdata[d.fcols['position_size']][i] * MARGIN_RATE
    d.fdata[d.fcols['margin_closeout']][i] = d.fdata[d.fcols['ac_bal']][i] + d.fdata[d.fcols['unrealised_pl']][i]

    # print(i, d.df['analysis'].iloc[i])
    # print(d.fdata[d.fcols['realised_pl']][i])
    return signal

def open_new_streak(i: int, signal: int, risk: float, rr: float, cushion: float, reverse: bool=False) -> int:
    return make_trade(i=i, signal=signal, risk=risk, rr=rr, cushion=cushion, new_streak=True, reverse=reverse)

def reverse_position(i: int, position: int, risk: float, rr: float, cushion: float) -> int:
    signal = BUY if position == SELL else SELL
    return make_trade(i=i, signal=signal, risk=risk, rr=rr, cushion=cushion, new_streak=False)
    
def no_signal_update_values(i: int, position: int):
    # print(i, 'no_signal_update_values')
    d.fdata[d.fcols['signal']][i] = NONE
    d.fdata[d.fcols['trade_no']][i] = d.fdata[d.fcols['trade_no']][i-1]
    d.fdata[d.fcols['streak_no']][i] = d.fdata[d.fcols['streak_no']][i-1]
    d.fdata[d.fcols['position_size']][i] = d.fdata[d.fcols['position_size']][i-1]
    d.fdata[d.fcols['cum_position_size']][i] = d.fdata[d.fcols['cum_position_size']][i-1]
    d.fdata[d.fcols['buy_price']][i] = d.fdata[d.fcols['buy_price']][i-1]
    d.fdata[d.fcols['buy_tp_price']][i] = d.fdata[d.fcols['buy_tp_price']][i-1]
    d.fdata[d.fcols['sell_price']][i] = d.fdata[d.fcols['sell_price']][i-1]
    d.fdata[d.fcols['sell_tp_price']][i] = d.fdata[d.fcols['sell_tp_price']][i-1]
    d.fdata[d.fcols['realised_pl']][i] = d.fdata[d.fcols['realised_pl']][i-1]
    d.fdata[d.fcols['ac_bal']][i] = d.fdata[d.fcols['ac_bal']][i-1]
    d.fdata[d.fcols['margin_used']][i] = d.fdata[d.fcols['margin_used']][i-1]

    if position == BUY:
        d.fdata[d.fcols['unrealised_pl']][i] = \
            (d.fdata[d.fcols['mid_c']][i] - d.fdata[d.fcols['buy_price']][i]) * d.fdata[d.fcols['position_size']][i]
    elif position == SELL:
        d.fdata[d.fcols['unrealised_pl']][i] = \
            (d.fdata[d.fcols['sell_price']][i] - d.fdata[d.fcols['mid_c']][i]) * d.fdata[d.fcols['position_size']][i]
    
    d.fdata[d.fcols['margin_closeout']][i] = d.fdata[d.fcols['ac_bal']][i] + d.fdata[d.fcols['unrealised_pl']][i]    
    # print(i, d.df['analysis'].iloc[i])

def run_sim(sim_name: str, init_signal: int, cushion: float, rr: float, risk: float, margin_closeout: bool, streak_trade_limit: int ) -> pd.DataFrame:
    INIT_SIGNAL = init_signal
    CUSHION = cushion
    RR = rr
    RISK = risk
    MARGIN_CLOSEOUT = margin_closeout
    STREAK_TRADE_LIMIT = streak_trade_limit

    d.shorten(name=sim_name, rows=max, direction=1, cols=our_cols)
    d.add_columns(name=sim_name, cols=['signal', 'streak_no', 'trade_no', 'position_size', 'cum_position_size', 'buy_price', 'sell_price', 'buy_tp_price', 'sell_tp_price', 'unrealised_pl', 'realised_pl', 'ac_bal', 'margin_used', 'margin_closeout', ])
    d.prepare_fast_data(sim_name)

    candles = d.fdata[0].shape[0]
    position = NONE
    for i in tqdm(range(candles), desc=" Simulating... "):       
        # First candle
        if i == 0:
            # print(i, position, 'before call')
            # print(i, '#### First candle')
            position = open_new_streak(i=i, signal=INIT_SIGNAL,  risk=RISK, rr=RR, cushion=CUSHION)
        
        # Subsequent candles
        else:
            # Reduce trade size to avoid large loss or Margin closeout
            # if d.fdata[d.fcols['margin_closeout']][i-1] < d.fdata[d.fcols['margin_used']][i-1]: 
            if ((position == BUY and d.fdata[d.fcols['ask_l']][i] <= d.fdata[d.fcols['sell_price']][i-1]) or \
                (position == SELL and d.fdata[d.fcols['bid_h']][i] >= d.fdata[d.fcols['buy_price']][i-1])) and \
                d.fdata[d.fcols['trade_no']][i-1] == STREAK_TRADE_LIMIT and MARGIN_CLOSEOUT == True:
                # print(i, '#### Margin closeout')
                signal = SELL if position == BUY  else BUY
                position = open_new_streak(i=i, signal=signal, risk=RISK, rr=RR, cushion=CUSHION, reverse=True)
            
            # Reverse trade on hitting Stop Loss
            ## From Buy to Sell  
            elif position == BUY and d.fdata[d.fcols['ask_l']][i] <= d.fdata[d.fcols['sell_price']][i-1]:
                # position = SELL
                # print(i, position, 'before call')
                # print(i, '#### Reverse Buy to Sell')
                position = reverse_position(i=i, position=position, risk=RISK, rr=RR, cushion=CUSHION)

            ## From Sell to Buy 
            elif position == SELL and d.fdata[d.fcols['bid_h']][i] >= d.fdata[d.fcols['buy_price']][i-1]:
                # position = BUY
                # print(i, position, 'before call')
                # print(i, '#### Reverse Sell to Buy')
                position = reverse_position(i=i, position=position, risk=RISK, rr=RR, cushion=CUSHION)

            # Take profit and initiate new trade in same direction on hitting Take Profit
            ## Take Profit on long position
            elif position == BUY and d.fdata[d.fcols['ask_h']][i] >= d.fdata[d.fcols['buy_tp_price']][i-1]:
                # print(i, '#### TP Long')
                position = open_new_streak(i=i, signal=position, risk=RISK, rr=RR, cushion=CUSHION)
                
            ## Take Profit on short position
            elif position == SELL and d.fdata[d.fcols['bid_l']][i] <= d.fdata[d.fcols['sell_tp_price']][i-1]:
                # print(i, '#### TP Short')
                position = open_new_streak(i=i, signal=position, risk=RISK, rr=RR, cushion=CUSHION)     
                    
            # New trade
            
            # Update values when there is no signal
            else:
                # print(i, 'None', 'before call')
                # print(i, '#### No signal')
                no_signal_update_values(i=i, position=position)   

    return dict(
        sim_name = sim_name,
        init_signal = INIT_SIGNAL,
        cushion = CUSHION,
        risk = RISK,
        rr = RR,
        margin_closeout = MARGIN_CLOSEOUT,
        streak_limit = STREAK_TRADE_LIMIT,
        results = d.df[sim_name]
    )

def process_sim(counter: int, init_signal: int, cushion: float, rr: float, risk: float, margin_closeout: bool, streak_trade_limit: int, inputs_list: list, inputs_file: str):
    sim_name = f'sim_{counter}'
    header = ['sim_name', 'init_signal', 'cushion', 'risk', 'rr', 'margin_closeout', 'streak_limit']
    inputs = [sim_name, init_signal, cushion, risk, rr, margin_closeout, streak_trade_limit]
    print(tabulate([inputs], header, tablefmt='plain'))
    result= run_sim(
        sim_name=sim_name,
        init_signal=init_signal,
        cushion=cushion,
        rr=rr,
        risk=risk,
        margin_closeout=margin_closeout,
        streak_trade_limit=streak_trade_limit
    )
    # print('Saving files...')
    with open(f'D:/Trading/forex_bot/outputs/{sim_name}.pkl', 'wb') as file:
        pkl.dump(result, file)

    inputs_list.append(inputs)
    header = ['sim_name', 'init_signal', 'cushion', 'risk', 'rr', 'margin_closeout', 'streak_limit']
    inputs_df = pd.DataFrame(inputs_list, columns=header)
    inputs_df.to_pickle('D:/Trading/forex_bot/outputs/' + inputs_file)
    
    counter =  counter + 1
    return inputs


cushion = [1.5, 2.0, 2.5, 3.0, 4.0]
rr = [1.5, 2, 3]
risk = [0.0010, 0.0020, 0.0030, 0.0040]
margin_closeout = [True]
streak_trade_limit = [1, 2, 3]
INPUTS_FILE = 'inputs1.pkl'

counter = 1
inputs_list = list()
# for i_s in init_signal:
for c in cushion:
    for r_r in rr:
        for r in risk:
            for m_c in margin_closeout:
                if m_c == True:
                    for lim in streak_trade_limit:
                        # if counter > 163:
                        inputs = process_sim(
                            counter=counter,
                            init_signal=random.choice([BUY, SELL]),
                            cushion=c,
                            rr=r_r,
                            risk=r,
                            margin_closeout=m_c,
                            streak_trade_limit=lim,
                            inputs_list=inputs_list,
                            inputs_file=INPUTS_FILE
                        )  
                        counter =  counter + 1
                else:
                    # if counter > 163:
                    inputs = process_sim(
                            counter=counter,
                            init_signal=random.choice([BUY, SELL]),
                            cushion=c,
                            rr=r_r,
                            risk=r,
                            margin_closeout=m_c,
                            streak_trade_limit=0,
                            inputs_list=inputs_list
                        )
                    counter =  counter + 1


