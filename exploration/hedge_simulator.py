from data import Data
from tqdm import trange
import pandas as pd
from random import choice

class GridSimulator:

    EVENT_ENTRY, EVENT_HEDGE_ENTRY, EVENT_PENDING, EVENT_CANCEL_PEND = 'ENT', 'HEDGE', 'PEND', 'PENDC'
    EVENT_TP, EVENT_REDUCE, EVENT_SQUEEZE, EVENT_MC = 'TP', 'RED', 'SQ', 'MC'
    EVENT_ENT_FAIL = 'EFAIL'
    EVENT_UP, EVENT_DOWN = 'UP', 'DN'
    OPEN_KEYS = ('SIZE', 'ENT', 'TP', 'HEDGE')
    PEND_KEYS = ('SIZE', 'ENT')
    CLOSED_KEYS = ('SIZE', 'ENT', 'EXIT', 'PIPS')
    LONG, SHORT = 1, -1
    MC_PERCENT = 0.50

    def __init__(
            self,
            name: str,
            df: pd.DataFrame,
            instruments: str,
            ticker: str,
            init_bal: float,
            init_capacity: int,
            topup_capacity: int,
            max_capacity: int,
            trade_to_capacity_threshold: int,
            distance_factor: int,
            hedge_pips: int,
            tp_pips: int,
            topup_pips: int,
            trailing_hedge_pips: int,
            keep_percent: float):
        
        self.name = name
        self.init_bal = init_bal
        self.init_capacity = init_capacity
        self.topup_capacity = topup_capacity
        self.max_capacity = max_capacity
        self.trade_to_capacity_threshold = trade_to_capacity_threshold
        self.distance_factor = distance_factor
        self.hedge_pips = hedge_pips
        self.tp_pips = tp_pips
        self.topup_pips = topup_pips
        self.trailing_hedge_pips = trailing_hedge_pips
        self.keep_percent = keep_percent

        self.d = Data(
            source=df.copy(),
            ticker=ticker,
            cols=['time', 'mid_c', 'bid_c', 'ask_c', 'atr_c'],
            instruments=instruments
        )

        add_cols = dict(
            trigger=float,
            open_longs=object,
            open_shorts=object,
            pending_longs=object,
            pending_shorts=object,
            closed_longs=object,
            closed_shorts=object,
            events=object,
            cum_long_position=int,
            cum_short_position=int,
            cum_long_pending=int,
            cum_short_pending=int,
            cum_long=int,
            cum_short=int,
            open_long_count=int,
            open_short_count=int,
            closed_long_count=int,
            closed_short_count=int,
            unrealised_pnl=float,
            realised_pnl=float,
            ac_bal=float,
            net_bal=float,
            margin_used=float,
            gross_bal=float
        )

        self.d.prepare_fast_data(name=name, add_cols=add_cols)

    def get_open_longs(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('open_longs', self.OPEN_KEYS, i)
    
    def get_open_shorts(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('open_shorts', self.OPEN_KEYS, i)
    
    def get_pending_longs(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('pending_longs', self.PEND_KEYS, i)
    
    def get_pending_shorts(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('pending_shorts', self.PEND_KEYS, i)
    
    def get_closed_longs(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('closed_longs', self.CLOSED_KEYS, i)
    
    def get_closed_shorts(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('closed_shorts', self.CLOSED_KEYS, i)
    
    def update_open_longs(self, open_longs: dict):
        open_longs_tuple = dict()
        for trade_no, trade in open_longs.items():
            open_longs_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('open_longs', self.i, open_longs_tuple)

    def update_open_shorts(self, open_shorts: dict):
        open_shorts_tuple = dict()
        for trade_no, trade in open_shorts.items():
            open_shorts_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('open_shorts', self.i, open_shorts_tuple)

    def update_pending_longs(self, pending_longs: dict):
        pending_longs_tuple = dict()
        for trade_no, trade in pending_longs.items():
            pending_longs_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('pending_longs', self.i, pending_longs_tuple)

    def update_pending_shorts(self, pending_shorts: dict):
        pending_shorts_tuple = dict()
        for trade_no, trade in pending_shorts.items():
            pending_shorts_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('pending_shorts', self.i, pending_shorts_tuple)

    def update_closed_longs(self, closed_longs: dict):
        closed_longs_tuple = dict()
        for trade_no, trade in closed_longs.items():
            closed_longs_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('closed_longs', self.i, closed_longs_tuple)

    def update_closed_shorts(self, closed_shorts: dict):
        closed_shorts_tuple = dict()
        for trade_no, trade in closed_shorts.items():
            closed_shorts_tuple[trade_no] = tuple(trade.values())
        self.d.update_fdata('closed_shorts', self.i, closed_shorts_tuple)
    
    def cum_long_position(self):
        open_longs = self.get_open_longs()
        cum_long_position = 0
        for _, trade in open_longs.items():
            cum_long_position = cum_long_position + trade['SIZE']
        return cum_long_position

    def cum_short_position(self):
        open_shorts = self.get_open_shorts()
        cum_short_position = 0
        for _, trade in open_shorts.items():
            cum_short_position = cum_short_position + trade['SIZE']
        return cum_short_position

    def cum_long_pending(self):
        pending_longs = self.get_pending_longs()
        cum_long_pending = 0
        for _, trade in pending_longs.items():
            cum_long_pending = cum_long_pending + trade['SIZE']
        return cum_long_pending

    def cum_short_pending(self):
        pending_shorts = self.get_pending_shorts()
        cum_short_pending = 0
        for _, trade in pending_shorts.items():
            cum_short_pending = cum_short_pending + trade['SIZE']
        return cum_short_pending

    def unrealised_pnl(self):
        open_longs = self.get_open_longs()
        open_shorts = self.get_open_shorts()
        pnl = 0
        for _, trade in open_longs.items():
            pnl = pnl + trade['SIZE'] * (self.d.fdata('bid_c', self.i) - trade['ENT'])
        for _, trade in open_shorts.items():
            pnl = pnl + trade['SIZE'] * (trade['ENT'] - self.d.fdata('ask_c', self.i))
        return round(pnl, 2)
    
    def realised_pnl(self):
        closed_longs = self.get_closed_longs()
        closed_shorts = self.get_closed_shorts()
        pnl = 0
        for _, trade in closed_longs.items():
            pnl = pnl + trade['SIZE'] * (trade['EXIT'] - trade['ENT'])
        for _, trade in closed_shorts.items():
            pnl = pnl + trade['SIZE'] * (trade['ENT'] - trade['EXIT'])
        return round(pnl, 2)

    def current_ac_values(self):
        ac_bal = self.d.fdata('ac_bal', self.i-1) + self.d.fdata('realised_pnl', self.i)
        margin_used = (self.d.fdata('cum_long_position', self.i) + 
                       self.d.fdata('cum_short_position', self.i)) * float(self.d.ticker['marginRate'])
        net_bal = ac_bal + self.d.fdata('unrealised_pnl', self.i)
        return ac_bal, net_bal, margin_used      

    def update_temp_ac_values(self, init: bool=False):
        if init:
            self.d.update_fdata('open_longs', self.i, self.d.fdata('open_longs', self.i-1))
            self.d.update_fdata('open_shorts', self.i, self.d.fdata('open_shorts', self.i-1))
            self.d.update_fdata('cum_long_position', self.i, self.d.fdata('cum_long_position', self.i-1))
            self.d.update_fdata('cum_short_position', self.i, self.d.fdata('cum_short_position', self.i-1))
            self.d.update_fdata('open_long_count', self.i, len(self.get_open_longs(self.i-1)))
            self.d.update_fdata('open_short_count', self.i, len(self.get_open_shorts(self.i-1)))
            self.d.update_fdata('closed_long_count', self.i, len(self.get_closed_longs(self.i-1)))
            self.d.update_fdata('closed_short_count', self.i, len(self.get_closed_shorts(self.i-1)))
        else:
            self.d.update_fdata('cum_long_position', self.i, self.cum_long_position())
            self.d.update_fdata('cum_short_position', self.i, self.cum_short_position())
            self.d.update_fdata('open_long_count', self.i, len(self.get_open_longs()))
            self.d.update_fdata('open_short_count', self.i, len(self.get_open_shorts()))
            self.d.update_fdata('closed_long_count', self.i, len(self.get_closed_longs()))
            self.d.update_fdata('closed_short_count', self.i, len(self.get_closed_shorts()))
        
        self.d.update_fdata('unrealised_pnl', self.i, self.unrealised_pnl())
        self.d.update_fdata('realised_pnl', self.i, self.realised_pnl())

    def update_ac_values(self):
        self.d.update_fdata('cum_long_position', self.i, self.cum_long_position())
        self.d.update_fdata('cum_short_position', self.i, self.cum_short_position())
        self.d.update_fdata('open_long_count', self.i, len(self.get_open_longs()))
        self.d.update_fdata('open_short_count', self.i, len(self.get_open_shorts()))
        self.d.update_fdata('closed_long_count', self.i, len(self.get_closed_longs()))
        self.d.update_fdata('closed_short_count', self.i, len(self.get_closed_shorts()))

        self.d.update_fdata('unrealised_pnl', self.i, self.unrealised_pnl())
        self.d.update_fdata('realised_pnl', self.i, self.realised_pnl())
        
        # First candle
        if self.i == 0:               
            self.d.update_fdata('ac_bal', self.i, self.init_bal)
        # Subsequent candles
        else:
            ac_bal = self.d.fdata('ac_bal', self.i-1)
            self.d.update_fdata('ac_bal', self.i, round(ac_bal + self.d.fdata('realised_pnl', self.i), 2))

        self.d.update_fdata('net_bal', self.i, round(self.d.fdata('ac_bal', self.i) + self.d.fdata('unrealised_pnl', self.i), 2))
        self.d.update_fdata('margin_used', self.i, \
                            round((self.d.fdata('cum_long_position', self.i) + 
                                   self.d.fdata('cum_short_position', self.i)) * float(self.d.ticker['marginRate']), 2))
        
        self.d.update_fdata('gross_bal', self.i, self.d.fdata('ac_bal', self.i))
           
    def calc_trade_size(self):
        return 10
    
    def update_events(self, event):
        events = self.d.fdata('events', self.i) if type(self.d.fdata('events', self.i)) == list else list()
        if event not in events:
            events.append(event)
            self.d.update_fdata('events', self.i, events)

    def close_long(self, trade_no: int):
        # Remove from open longs
        open_longs = self.get_open_longs()
        closing_long = open_longs[trade_no]
        del open_longs[trade_no]
        self.update_open_longs(open_longs)

        # Append to closed longs
        pips = round((self.d.fdata('bid_c',  self.i) - closing_long['ENT']) * pow(10, -self.d.ticker['pipLocation']), 1)
        closed_longs = self.get_closed_longs()
        # closed_longs[trade_no] = (closing_long['SIZE'], closing_long['ENT'], self.d.fdata('bid_c',  self.i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)
        closed_longs[trade_no] = dict(
            SIZE=closing_long['SIZE'],
            # TRIG=closing_long['TRIG'],
            ENT=closing_long['ENT'],
            EXIT=self.d.fdata('bid_c',  self.i),
            PIPS=pips
        )
        self.update_closed_longs(closed_longs) 

    def close_short(self, trade_no: int):
        # Remove from open shorts
        open_shorts = self.get_open_shorts()
        closing_short = open_shorts[trade_no]
        del open_shorts[trade_no]
        self.update_open_shorts(open_shorts)

        # Append to closed shorts
        pips = round((closing_short['ENT'] - self.d.fdata('ask_c',  self.i)) * pow(10, -self.d.ticker['pipLocation']), 1)
        closed_shorts = self.get_closed_shorts()
        closed_shorts[trade_no] = dict(
            SIZE=closing_short['SIZE'],
            # TRIG=closing_short['TRIG'],
            ENT=closing_short['ENT'],
            EXIT=self.d.fdata('ask_c',  self.i),
            PIPS=pips
        )
        self.update_closed_shorts(closed_shorts)
    
    def entry(self):
        traded = False
        if True:
            open_longs = self.get_open_longs()
            open_shorts = self.get_open_shorts()

            trade_size = self.calc_trade_size() if len(open_longs) + len(open_shorts) == 0 else 0
            
            dir = choice((self.LONG, self.SHORT))

            if trade_size > 0:
                self.trade_no = self.trade_no + 1
                
                tp_pips = self.d.fdata('atr_c', self.i) * self.tp_pips
                hedge_pips = self.d.fdata('atr_c', self.i) * self.hedge_pips

                if dir == self.LONG:
                    self.trigger = self.d.fdata('ask_c', self.i)
                    
                    long_tp = round(self.trigger + tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    long_hedge = round(self.trigger - hedge_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    open_longs[self.trade_no] = dict(
                        SIZE=trade_size,
                        ENT=self.d.fdata('ask_c', self.i),
                        TP=long_tp,
                        HEDGE=long_hedge
                    )
                    self.update_open_longs(open_longs)
                    traded = True

                if dir == self.SHORT:
                    self.trigger = self.d.fdata('bid_c', self.i)
                    short_tp = round(self.trigger - tp_pips * pow(10, self.d.ticker['pipLocation']), 5)  
                    short_hedge = round(self.trigger + hedge_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    open_shorts[self.trade_no] = dict(
                        SIZE=trade_size,
                        ENT=self.d.fdata('bid_c', self.i),
                        TP=short_tp,
                        SL=short_hedge
                    )
                    self.update_open_shorts(open_shorts)
                    traded = True
            
                if traded:
                    self.update_temp_ac_values()
                    self.update_events(self.EVENT_ENTRY)              
    
    def take_profit(self):     
        traded = False
        # Close long positions take profit
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('bid_c', self.i) >= trade['TP']:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('ask_c', self.i) <= trade['TP']:
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)   
    
    def reduce(self):
        pass

    def margin_call(self):
        _, net_bal, margin_used = self.current_ac_values()
        traded = False
        if net_bal < margin_used * self.MC_PERCENT:
            open_longs = self.get_open_longs()
            for trade_no, trade in open_longs.items():
                self.close_long(trade_no)
                traded = True

            open_shorts = self.get_open_shorts()
            for trade_no, trade in open_shorts.items():
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_MC)               

    def update_init_values(self):
        self.trade_no = 0
        self.next_up_grid = self.d.fdata('mid_c', 0)
        self.next_down_grid = self.d.fdata('mid_c', 0)
        self.max_gross_bal = self.init_bal
    
    def run_sim(self):
        self.i = 0
        t = trange(self.d.fdatalen, desc='Simulating...', leave=True)
        for i in t:
            self.i = i
            if i == 0:
                t.set_description('Simulating...')
            else:
                t.set_description(f'DtTm: {self.d.fdata("time", self.i-1)}, GrossBal: {self.d.fdata("gross_bal", self.i-1)}, OpenPnL: {self.d.fdata("unrealised_pnl", self.i-1)}, MarginUsed: {self.d.fdata("margin_used", self.i-1)}')
            t.refresh() 

            if self.i == 0:
                self.update_init_values()
            else:
                self.update_temp_ac_values(init=True)
                self.margin_call()
                self.take_profit()
                self.reduce()
                self.entry()
            self.update_ac_values()