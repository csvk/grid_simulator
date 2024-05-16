import pandas as pd
import numpy as np
import datetime as dt
from tqdm import tqdm
from tabulate import tabulate
import json
import pickle as pkl


SIZE, ENTRY, TP, SL = 0, 1, 2, 3
EXIT, PIPS = 2, 3

with open("../data/instruments.json", 'r') as f:
    instr = json.load(f)

class Data:
    
    def __init__(self, source):
        assert type(source) == str or type(source) == pd.DataFrame, 'Invalid source'
        if type(source) == str:
            self.df = {
                'raw': pd.read_pickle(source)
            }
        elif type(source) == pd.DataFrame:
            self.df = {
                'raw': source.copy()
            }            

        if 'time' in self.df['raw'].columns:
            self.df['raw']['time'] = [ x.replace(tzinfo=None) for x in self.df['raw']['time']]
        self.datalen = self.df['raw'].shape[0]

    def __repr__(self) -> str:
        repr = str()
        for name, df in self.df.items():
            repr = repr + name + ':\n' + str(pd.concat([df.head(2), df.tail(1)])) + '\n'
        return repr

    def prep_data(self, name: str, start: int, end: int, source: str='raw', cols: list=None):
        '''Create new dataframe with specified list of columns and number of rows as preparation for fast data creation
        '''
        if cols == None:
            cols = self.df[source].columns

        if start == None:
            start = 0
        if end == None:
            end = self.datalen

        assert end > start, f'start={start}, end={end} not valid'

        self.df[name] = self.df[source][cols].iloc[start:end].copy()
        self.df[name].reset_index(drop=True, inplace=True)

    def add_columns(self, name: str, cols: dict):
        '''Add new columns to component dataframes
        '''        
        exist_cols = list(self.df[name].columns)
        for col, _type in cols.items():
            self.df[name][col] = pd.Series(dtype=_type) 

    def prepare_fast_data(self, name: str, start: int, end: int, source: str='raw', cols: list=None, add_cols: dict=None):
        '''Prepare data as an array for fast processing
        fcols = {col1: col1_index, col2: col2_index, .... }     
        fastdf = [array[col1], array[col2], array[col3], .... ]
        Accessed by: self.fdata()
        '''

        self.prep_data(name=name, start=start, end=end, source=source, cols=cols)
        if add_cols:
            self.add_columns(name=name, cols=add_cols)

        self.fcols = dict()
        for i in range(len(self.df[name].columns)):
            self.fcols[self.df[name].columns[i]] = i
        self.fastdf = [self.df[name][col].array for col in self.df[name].columns]
        self.fdatalen = len(self.fastdf[0])

    def fdata(self, column: str=None, index: int=None, rows: int=None):
        if column is None:
            return self.fastdf
        if index is None:
            return self.fastdf[self.fcols[column]]
        else:
            if rows:
                try:
                    return self.fastdf[self.fcols[column]][index:index+rows]
                except:
                    return self.fastdf[self.fcols[column]][index:]
            else:
                return self.fastdf[self.fcols[column]][index]
        
    def update_fdata(self, column: str, index: int=None, value: float=None):
        assert value is not None, 'Value cannot be null'
        if index is None:
            assert len(value) == self.fdatalen
            for i in range(self.fdatalen):
                self.fastdf[self.fcols[column]][i] = value[i]
                print(i, )
        else:
            self.fastdf[self.fcols[column]][index] = value


def read_data(ticker: str, frequency: str):
    our_cols = ['time', 'mid_c', 'bid_c', 'ask_c']
    df = pd.read_pickle(f"../data/{ticker}_{frequency}.pkl")
    return df[our_cols]

def cum_long_position(d: Data, i: int):
    open_longs = d.fdata('open_longs', i).copy() if type(d.fdata('open_longs', i)) == dict else dict()
    cum_long_position = 0
    for _, trade in open_longs.items():
        cum_long_position = cum_long_position + trade[SIZE]
    return cum_long_position

def cum_short_position(d: Data, i: int):
    open_shorts = d.fdata('open_shorts', i).copy() if type(d.fdata('open_shorts', i)) == dict else dict()
    cum_short_position = 0
    for _, trade in open_shorts.items():
        cum_short_position = cum_short_position + trade[SIZE]
    return cum_short_position

def unrealised_pnl(d: Data, i: int):
    open_longs = d.fdata('open_longs', i).copy() if type(d.fdata('open_longs', i)) == dict else dict()
    open_shorts = d.fdata('open_shorts', i).copy() if type(d.fdata('open_shorts', i)) == dict else dict()
    pnl = 0
    for _, trade in open_longs.items():
        pnl = pnl + trade[SIZE] * (d.fdata('mid_c', i) - trade[ENTRY])
    for _, trade in open_shorts.items():
        pnl = pnl + trade[SIZE] * (trade[ENTRY] - d.fdata('mid_c', i))
    return round(pnl, 2)

def realised_pnl(d: Data, i: int):
    closed_longs = d.fdata('closed_longs', i).copy() if type(d.fdata('closed_longs', i)) == dict else dict()
    closed_shorts = d.fdata('closed_shorts', i).copy() if type(d.fdata('closed_shorts', i)) == dict else dict()
    pnl = 0
    for _, trade in closed_longs.items():
        pnl = pnl + trade[SIZE] * (trade[EXIT] - trade[ENTRY])
    for _, trade in closed_shorts.items():
        pnl = pnl + trade[SIZE] * (trade[ENTRY] - trade[EXIT])
    return round(pnl, 2)

def unrealised_pnl_prev_bar(d: Data, i: int):
    open_longs = d.fdata('open_longs', i-1).copy() if type(d.fdata('open_longs', i-1)) == dict else dict()
    open_shorts = d.fdata('open_shorts', i-1).copy() if type(d.fdata('open_shorts', i-1)) == dict else dict()
    pnl = 0
    for _, trade in open_longs.items():
        pnl = pnl + trade[SIZE] * (d.fdata('mid_c', i) - trade[ENTRY])
    for _, trade in open_shorts.items():
        pnl = pnl + trade[SIZE] * (trade[ENTRY] - d.fdata('mid_c', i))
    return round(pnl, 2)

def current_values(d: Data, i: int, ticker: str):
    _cum_long_position = cum_long_position(d, i)
    _cum_short_position = cum_short_position(d, i)
    _unrealised_pnl = unrealised_pnl(d, i)
    _realised_pnl = realised_pnl(d, i)
    ac_bal = d.fdata('ac_bal', i) if type(d.fdata('ac_bal', i)) == float else d.fdata('ac_bal', i-1)
    ac_bal = ac_bal + _realised_pnl
    margin_used = (_cum_long_position + _cum_short_position) * float(instr[ticker]['marginRate'])
    margin_closeout = ac_bal + _unrealised_pnl
    return margin_used, margin_closeout

def dynamic_trade_size(d: Data, i: int, sizing_ratio: float):
    _net_bal = d.fdata('ac_bal', i-1) + unrealised_pnl(d, i)
    if _net_bal < 0:
        print(i, d.fdata('time', i), _net_bal)
    return int(_net_bal * sizing_ratio)   

def cashin_cashout(d:Data, i: int, init_bal: float, cash_out_factor: float, margin_sl_percent:float):
    TP, SL = 1, 0
    # Cash out / withdraw
    if d.fdata('margin_closeout', i) >= init_bal * cash_out_factor:
        cash_out = d.fdata('margin_closeout', i) - init_bal * cash_out_factor
        d.update_fdata('ac_bal', i, round(d.fdata('ac_bal', i) - cash_out, 2))
        d.update_fdata('margin_closeout', i, d.fdata('margin_closeout', i) - cash_out)
        d.update_fdata('cash_bal', i, round(d.fdata('cash_bal', i-1) + cash_out, 2)) 
    # Deposit money into a/c when stop loss is triggered
    # print(d.fdata('margin_closeout', i), ',', d.fdata('margin_used', i), ',', margin_sl_percent)
    elif d.fdata('trade_type', i) == SL:
        cash_in = min(init_bal * cash_out_factor - d.fdata('margin_closeout', i), d.fdata('cash_bal', i-1))
        d.update_fdata('ac_bal', i, round(d.fdata('ac_bal', i) + cash_in, 2))
        d.update_fdata('margin_closeout', i, d.fdata('margin_closeout', i) + cash_in)
        d.update_fdata('cash_bal', i, round(d.fdata('cash_bal', i-1) + cash_in, 2))
    else:
        d.update_fdata('cash_bal', i, d.fdata('cash_bal', i-1))

def calc_ac_values(d: Data, i: int, ticker: str, init_bal: float, cash_out_factor: float, margin_sl_percent: float):
    d.update_fdata('cum_long_position', i, cum_long_position(d, i))
    d.update_fdata('cum_short_position', i, cum_short_position(d, i))
    d.update_fdata('unrealised_pnl', i, unrealised_pnl(d, i))
    d.update_fdata('realised_pnl', i, realised_pnl(d, i))
    # First candle
    if i == 0:               
        d.update_fdata('ac_bal', i, init_bal)
        if cash_out_factor is not None:
            d.update_fdata('cash_bal', i, 0)
    # Subsequent candles
    else:
        d.update_fdata('ac_bal', i, round(d.fdata('ac_bal', i-1) + d.fdata('realised_pnl', i), 2))
    d.update_fdata('margin_used', i, \
                round((d.fdata('cum_long_position', i) + d.fdata('cum_short_position', i)) * float(instr[ticker]['marginRate']), 2))
    d.update_fdata('margin_closeout', i, round(d.fdata('ac_bal', i) + d.fdata('unrealised_pnl', i), 2))

    if i > 0:
        if cash_out_factor is not None:
            cashin_cashout(d, i, init_bal, cash_out_factor, margin_sl_percent)

def open_trades(d: Data, i: int, ticker: str, tp_pips: int, sl_pips: int, init_trade_size: int, sizing: str, 
                sizing_ratio: float, trade_no: int, next_up_grid: float, next_down_grid: float, init_bal: float, 
                cash_out_factor: float, margin_sl_percent: float):
    NT, TP, SL, MC = 1, 1, 0, -1

    if i == 0 or (d.fdata('mid_c', i) >= next_up_grid or d.fdata('mid_c', i) <= next_down_grid):
        trade_no = trade_no + 1 

        long_tp = d.fdata('mid_c', i) + tp_pips * pow(10, instr[ticker]['pipLocation'])
        short_tp = d.fdata('mid_c', i) - tp_pips * pow(10, instr[ticker]['pipLocation'])

        long_sl = d.fdata('mid_c', i) - sl_pips * pow(10, instr[ticker]['pipLocation'])
        short_sl = d.fdata('mid_c', i) + sl_pips * pow(10, instr[ticker]['pipLocation'])

        if i == 0:
            open_longs, open_shorts = dict(), dict()
            trade_size = init_trade_size
        else:
            open_longs = d.fdata('open_longs', i).copy() if type(d.fdata('open_longs', i)) == dict else d.fdata('open_longs', i-1).copy() 
            open_shorts = d.fdata('open_shorts', i).copy() if type(d.fdata('open_shorts', i)) == dict else d.fdata('open_shorts', i-1).copy() 
            # Temporary data population for dynamic trade size calculation
            d.update_fdata('open_longs', i, open_longs)
            d.update_fdata('open_shorts', i, open_shorts)
            trade_size = init_trade_size if sizing == 'static' else dynamic_trade_size(d, i, sizing_ratio)

        open_longs[trade_no] = (trade_size, d.fdata('ask_c', i), long_tp, long_sl) # (SIZE, ENTRY, TP, SL)
        d.update_fdata('open_longs', i, open_longs)
        open_shorts[trade_no] = (trade_size, d.fdata('bid_c', i), short_tp, short_sl) # (SIZE, ENTRY, TP, SL)
        d.update_fdata('open_shorts', i, open_shorts)

        # Do not update if stop loss / margin call was triggered on this bar
        if d.fdata('trade_type', i) != SL and d.fdata('trade_type', i) != MC:
            d.update_fdata('trade_type', i, NT)           
        
    else: # Cascade open positions from prev candle to current candle
        trade_no = trade_no
        long_tp, short_tp = next_up_grid, next_down_grid
        d.update_fdata('open_longs', i, d.fdata('open_longs', i-1).copy())
        d.update_fdata('open_shorts', i, d.fdata('open_shorts', i-1).copy())

    calc_ac_values(d, i, ticker, init_bal, cash_out_factor, margin_sl_percent)    

    return trade_no, long_tp, short_tp # equals next_up_grid, next_down_grid for next grid level trades

def close_long(d: Data, i: int, ticker: str, trade_no: int, sl_type: int):
    TP, SL, MC = 1, 0, -1
    # Remove from open longs
    open_longs = d.fdata('open_longs', i).copy()
    closing_long = open_longs[trade_no]
    del open_longs[trade_no]
    d.update_fdata('open_longs', i, open_longs)

    # Append to closed longs
    pips = (d.fdata('ask_c', i) - closing_long[ENTRY]) * pow(10, -instr[ticker]['pipLocation'])
    closed_longs = d.fdata('closed_longs', i).copy() if type(d.fdata('closed_longs', i)) == dict else dict()
    closed_longs[trade_no] = (closing_long[SIZE], closing_long[ENTRY], d.fdata('bid_c', i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)

    d.update_fdata('closed_longs', i, closed_longs)
    d.update_fdata('trade_type', i, sl_type)

def close_short(d: Data, i: int, ticker: str, trade_no: int, sl_type: int):
    TP, SL, MC = 1, 0, -1
    # Remove from open shorts
    open_shorts = d.fdata('open_shorts', i).copy()
    closing_short = open_shorts[trade_no]
    del open_shorts[trade_no]
    d.update_fdata('open_shorts', i, open_shorts)

    # Append to closed shorts
    pips = (closing_short[ENTRY] - d.fdata('bid_c', i)) * pow(10, -instr[ticker]['pipLocation'])
    closed_shorts = d.fdata('closed_shorts', i).copy() if type(d.fdata('closed_shorts', i)) == dict else dict()
    closed_shorts[trade_no] = (closing_short[SIZE], closing_short[ENTRY], d.fdata('ask_c', i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)

    d.update_fdata('closed_shorts', i, closed_shorts)
    d.update_fdata('trade_type', i, sl_type)

def take_profit(d: Data, i: int, ticker: str, init_bal: float, cash_out_factor: float, margin_sl_percent: float):  
    NT, TP, SL, MC = 1, 1, 0, -1
    trade = False          
    # Close long positions take profit
    open_longs = d.fdata('open_longs', i).copy() if type(d.fdata('open_longs', i)) == dict else dict()
    for trade_no, trade in open_longs.items():
        if d.fdata('mid_c', i) >= trade[TP]:
            close_long(d, i, ticker, trade_no)
            trade = True

    # Close short positions take profit
    open_shorts = d.fdata('open_shorts', i).copy() if type(d.fdata('open_shorts', i)) == dict else dict()
    for trade_no, trade in open_shorts.items():
        if d.fdata('mid_c', i) <= trade[TP]:
            close_short(d, i, ticker, trade_no)
            trade = True

    # Do not update if stop loss / margin call was triggered on this bar
    if d.fdata('trade_type', i) != SL and d.fdata('trade_type', i) != MC:
        if trade == True:
            d.update_fdata('trade_type', i, TP)   

    calc_ac_values(d, i, ticker, init_bal, cash_out_factor, margin_sl_percent)    

def margin_stop_loss_oldest(d: Data, i: int, ticker: str, margin_sl_percent: float=0.5):
    margin_used, margin_closeout = current_values(d, i)
    # Margin call is triggered when margin closeout is less than 50% of margin used.
    # Here stop loss is triggered if it falls below margin_sl_percent
    if margin_closeout < margin_used * margin_sl_percent:
        reduced_margin = margin_closeout / margin_sl_percent
        while reduced_margin < margin_used:
            longs = list(d.fdata('open_longs', i).keys())
            shorts = list(d.fdata('open_shorts', i).keys())
            oldest_long = longs[0] if len(longs) > 0 else None
            oldest_short = shorts[0] if len(shorts) > 0 else None
            if oldest_long == None and oldest_short == None:
                break
            elif oldest_long == None:
                close_short(d, i, ticker, oldest_short, sl=True)
                margin_used, _ = current_values(d, i, ticker)
            elif oldest_short == None:
                close_long(d, i, ticker, oldest_long, sl=True)
                margin_used, _ = current_values(d, i, ticker)
            else:
                if oldest_long <= oldest_short:
                    close_long(d, i, ticker, oldest_long, sl=True)
                    margin_used, _ = current_values(d, i, ticker)
                else:
                    close_short(d, i, ticker, oldest_short, sl=True)
                    margin_used, _ = current_values(d, i, ticker)

def margin_stop_loss_farthest(d: Data, i: int, ticker: str, margin_sl_percent: float):
    margin_used, margin_closeout = current_values(d, i)
    # Margin call is triggered when margin closeout is less than 50% of margin used.
    # Here stop loss is triggered if it falls below margin_sl_percent
    price = d.fdata('mid_c', i)
    if margin_closeout < margin_used * margin_sl_percent:
        reduced_margin = margin_closeout / margin_sl_percent
        while reduced_margin < margin_used:
            farthest_long_price, farthest_short_price = price, price
            farthest_long, farthest_short = None, None
            for long, trade in d.fdata('open_longs', i).items():
                if trade[ENTRY] > farthest_long_price:
                    farthest_long_price = trade[ENTRY]
                    farthest_long = long
            for short, trade in d.fdata('open_shorts', i).items():
                if trade[ENTRY] < farthest_short_price:
                    farthest_short_price = trade[ENTRY]
                    farthest_short = short
            if farthest_long == None and farthest_short == None:
                break
            elif farthest_long == None:
                close_short(d, i, ticker, farthest_short, sl=True)
                margin_used, _ = current_values(d, i, ticker)
            elif farthest_short == None:
                close_long(d, i, ticker, farthest_long, sl=True)
                margin_used, _ = current_values(d, i, ticker)
            else:
                if farthest_long_price - price > price - farthest_short_price:
                    close_long(d, i, farthest_long, sl_type=True)
                    margin_used, _ = current_values(d, i, ticker)
                else:
                    close_short(d, i, ticker, farthest_short, sl=True)
                    margin_used, _ = current_values(d, i, ticker)

def margin_stop_loss_oldest_1(d: Data, i: int, ticker: str, margin_sl_percent: float=0.5):
    margin_used, margin_closeout = current_values(d, i)
    # Margin call is triggered when margin closeout is less than 50% of margin used.
    # Here stop loss is triggered if it falls below margin_sl_percent
    if margin_closeout < margin_used * margin_sl_percent:
        longs = list(d.fdata('open_longs', i).keys())
        shorts = list(d.fdata('open_shorts', i).keys())
        oldest_long = longs[0] if len(longs) > 0 else None
        oldest_short = shorts[0] if len(shorts) > 0 else None
        if oldest_long == None and oldest_short == None:
            pass
        elif oldest_long == None:
            close_short(d, i, ticker, oldest_short, sl=True)
            margin_used, _ = current_values(d, i, ticker)
        elif oldest_short == None:
            close_long(d, i, ticker, oldest_long, sl=True)
            margin_used, _ = current_values(d, i)
        else:
            if oldest_long <= oldest_short:
                close_long(d, i, ticker, oldest_long, sl=True)
                margin_used, _ = current_values(d, i)
            else:
                close_short(d, i, ticker, oldest_short, sl=True)
                margin_used, _ = current_values(d, i, ticker)

def margin_stop_loss_farthest_1(d: Data, i: int, ticker: str, margin_sl_percent: float):
    margin_used, margin_closeout = current_values(d, i)
    # Margin call is triggered when margin closeout is less than 50% of margin used.
    # Here stop loss is triggered if it falls below margin_sl_percent
    price = d.fdata('mid_c', i)
    if margin_closeout < margin_used * margin_sl_percent:
        farthest_long_price, farthest_short_price = price, price
        farthest_long, farthest_short = None, None
        for long, trade in d.fdata('open_longs', i).items():
            if trade[ENTRY] > farthest_long_price:
                farthest_long_price = trade[ENTRY]
                farthest_long = long
        for short, trade in d.fdata('open_shorts', i).items():
            if trade[ENTRY] < farthest_short_price:
                farthest_short_price = trade[ENTRY]
                farthest_short = short
        if farthest_long == None and farthest_short == None:
            pass
        elif farthest_long == None:
            close_short(d, i, ticker, farthest_short, sl=True)
            margin_used, _ = current_values(d, i, ticker)
        elif farthest_short == None:
            close_long(d, i, farthest_long, sl=True)
            margin_used, _ = current_values(d, i, ticker)
        else:
            if farthest_long_price - price > price - farthest_short_price:
                close_long(d, i, farthest_long, sl=True)
                margin_used, _ = current_values(d, i, ticker)
            else:
                close_short(d, i, farthest_short, sl=True)
                margin_used, _ = current_values(d, i, ticker)

def stop_loss_grid_count(d: Data, i: int, ticker: str):
    open_longs = d.fdata('open_longs', i).copy()
    for trade_no, trade in open_longs.items():
        if d.fdata('mid_c', i) <= trade[SL]:
            close_long(d, i, ticker, trade_no, sl=True)

    open_shorts = d.fdata('open_shorts', i).copy()
    for trade_no, trade in open_shorts.items():
        if d.fdata('mid_c', i) >= trade[SL]:
            close_short(d, i, ticker, trade_no, sl=True)

def margin_stop_loss_grid_count(d: Data, i: int, ticker: str, margin_sl_percent: float=0.5):
    margin_used, margin_closeout = current_values(d, i, ticker)
    # Margin call is triggered when margin closeout is less than 50% of margin used.
    # Here stop loss is triggered if it falls below margin_sl_percent
    if margin_closeout < margin_used * margin_sl_percent:
        stop_loss_grid_count(d, i, ticker)

def run_stop_loss(d: Data, i: int, ticker: str, stop_loss: str, init_bal: float, cash_out_factor: float, margin_sl_percent: float):
    if stop_loss == 'grid_count':
        stop_loss_grid_count(d, i, ticker)
    elif stop_loss == 'margin_grid_count':
        margin_stop_loss_grid_count(d, i, ticker, margin_sl_percent)
    elif stop_loss == 'margin_closeout_oldest':
        margin_stop_loss_oldest(d, i, ticker, margin_sl_percent)
    elif stop_loss == 'margin_closeout_farthest':
        margin_stop_loss_farthest(d, i, ticker, margin_sl_percent)
    elif stop_loss == 'margin_closeout_oldest_1':
        margin_stop_loss_oldest_1(d, i, ticker, margin_sl_percent)
    elif stop_loss == 'margin_closeout_farthest_1':
        margin_stop_loss_farthest_1(d, i, ticker, margin_sl_percent)

    # Update account values
    calc_ac_values(d, i, ticker, init_bal, cash_out_factor, margin_sl_percent)

def margin_call(d: Data, i: int, ticker: str, stop_loss: str, init_bal: float, cash_out_factor: float, margin_sl_percent: float):
    TP, SL, MC = 1, 0, -1
    calc_ac_values(d, i, ticker, init_bal, cash_out_factor, margin_sl_percent)
    if d.fdata('margin_closeout', 1) < d.fdata('margin_used', i) * 0.5:
        open_longs = d.fdata('open_longs', i).copy()
        for trade_no, trade in open_longs.items():
            close_long(d, i, ticker, trade_no, sl_type=MC)

        open_shorts = d.fdata('open_shorts', i).copy()
        for trade_no, trade in open_shorts.items():
            close_short(d, i, ticker, trade_no, sl_type=MC)

        # Update account values
        calc_ac_values(d, i, ticker, init_bal, cash_out_factor, margin_sl_percent)

def run_sim(d: Data, ticker: str, sim_name: str, start: int, end: int, init_bal: int, init_trade_size: int, grid_pips: int, 
            sl_grid_count: int, stop_loss: str, margin_sl_percent: float, sizing: str, cash_out_factor: float) -> pd.DataFrame:
    tp_pips = grid_pips
    sl_pips = grid_pips * sl_grid_count
    sizing_ratio = init_trade_size / init_bal
    
    add_cols = dict(
        open_longs=object,
        open_shorts=object,
        closed_longs=object,
        closed_shorts=object,
        trade_type=int, # (1 = ENTRY or TP, 0 = SL (ENTRY & TP can also happen when SL is triggered but SL indicator is set))
        cum_long_position=int,
        cum_short_position=int,
        unrealised_pnl=float,
        realised_pnl=float,
        ac_bal=float,
        margin_used=float,
        margin_closeout=float,
        cash_bal=float
    )
    d.prepare_fast_data(name=sim_name, start=start, end=end, add_cols=add_cols)

    trade_no = 0
    next_up_grid, next_down_grid = None, None
    for i in tqdm(range(d.fdatalen), desc=" Simulating... "):
        if i > 0:
            # Take profit
            take_profit(d=d, 
                        i=i, 
                        ticker=ticker, 
                        init_bal=init_bal,
                        cash_out_factor=cash_out_factor,
                        margin_sl_percent=margin_sl_percent)

            # Stop loss
            run_stop_loss(d=d,
                          i=i,
                          ticker=ticker,
                          stop_loss=stop_loss,
                          init_bal=init_bal,
                          cash_out_factor=cash_out_factor,
                          margin_sl_percent=margin_sl_percent)   
            
            margin_call(d=d,
                i=i,
                ticker=ticker,
                stop_loss=stop_loss,
                init_bal=init_bal,
                cash_out_factor=cash_out_factor,
                margin_sl_percent=margin_sl_percent)   
            
        # Open new trades            
        trade_no, next_up_grid, next_down_grid = open_trades(d=d, 
                                                    i=i,
                                                    ticker=ticker,
                                                    tp_pips=tp_pips,
                                                    sl_pips=sl_pips, 
                                                    init_trade_size=init_trade_size, 
                                                    sizing=sizing,
                                                    sizing_ratio=sizing_ratio,
                                                    trade_no=trade_no,
                                                    next_up_grid=next_up_grid,
                                                    next_down_grid=next_down_grid,
                                                    init_bal=init_bal,
                                                    cash_out_factor=cash_out_factor,
                                                    margin_sl_percent=margin_sl_percent)


            

    result = d.df[sim_name].copy()
    result = result[(result['trade_type'] == 1) | (result['trade_type'] == 0)]
    del d.df[sim_name]

    return dict(
        sim_name = sim_name,
        init_trade_size=init_trade_size,
        grid_pips=grid_pips,
        sl_grid_count=sl_grid_count,
        stop_loss=stop_loss,
        margin_sl_percent=margin_sl_percent,
        sizing=sizing,
        cash_out_factor=cash_out_factor,
        result = result
    )

def process_sim(d: Data, ticker: str, frequency: str, counter: int, start: int, end:int, init_bal: int, init_trade_size: int, 
                grid_pips: int, sl_grid_count: int, stop_loss: str, margin_sl_percent: float, sizing: str, cash_out_factor: float,
                inputs_list: list, inputs_file: str):
    sim_name = f'{ticker}-{frequency}-{counter}'
    header = ['sim_name', 'init_trade_size', 'grid_pips', 'stop_loss', 'sl_grid_count', 'stoploss_pips', 'margin_sl_percent', 'sizing', 'cash_out_factor']
    inputs = [sim_name, init_trade_size, grid_pips, stop_loss, sl_grid_count, grid_pips * sl_grid_count, margin_sl_percent, sizing, cash_out_factor]
    print(tabulate([inputs], header, tablefmt='plain'))
    result= run_sim(
        d=d,
        ticker=ticker,
        sim_name=sim_name,
        start=start,
        end=end,
        init_bal=init_bal,
        init_trade_size=init_trade_size,
        grid_pips=grid_pips,
        sl_grid_count=sl_grid_count,
        stop_loss=stop_loss,
        margin_sl_percent=margin_sl_percent,
        sizing=sizing,
        cash_out_factor=cash_out_factor
    )
    result['result'].to_csv(f'D:/Trading/ml4t-data/grid/{sim_name}.csv', index=False)

    inputs_list.append(inputs)
    inputs_df = pd.DataFrame(inputs_list, columns=header)
    inputs_df.to_csv(f'D:/Trading/ml4t-data/grid/{ticker}-{frequency}-' + inputs_file, index=False)
    
    # counter =  counter + 1
    return inputs

def run_optimizer(
        checkpoint: int,
        counter: int,
        start: int,
        end: int,
        tickers: list,
        frequency: list,
        init_bal: list,
        init_trade_size: list,
        grid_pips: list,
        sl_grid_count: list,
        stop_loss: list,
        margin_sl_percent: list,
        sizing: list,
        cash_out_factor: list,
        INPUTS_FILE: str):
    
    inputs_list = list()
    for tk in tickers:
        for f in frequency:
            df = read_data(tk, f)
            for ib in init_bal:
                for t in init_trade_size:
                    for s in sizing:
                        for g in grid_pips:
                            for c in cash_out_factor:
                                for sl in stop_loss:
                                    for mslp in margin_sl_percent:
                                        for slgc in sl_grid_count:
                                            if counter >= checkpoint:
                                                process_sim(
                                                    d=Data(df),
                                                    ticker=tk,
                                                    frequency=f,
                                                    counter=counter,
                                                    start=start,
                                                    end=end,
                                                    init_bal=ib,
                                                    init_trade_size=t,
                                                    grid_pips=g,
                                                    sl_grid_count=slgc,
                                                    stop_loss=sl,
                                                    margin_sl_percent=mslp,
                                                    sizing=s,
                                                    cash_out_factor=c,
                                                    inputs_list=inputs_list,
                                                    inputs_file=INPUTS_FILE
                                                )  
                                            counter =  counter + 1
                                