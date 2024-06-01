from data import Data
from tqdm import tqdm
import pandas as pd

class GridSimulator:

    EVENT_TP, EVENT_SL, EVENT_MC, EVENT_ENTRY, EVENT_COVER,  = 'TP', 'SL', 'MC', 'ENT', 'COV'
    EVENT_TSL_ADJUST, EVENT_PAR_UNLINK, EVENT_COV_UNLINK = 'TSLADJ', 'PARUNL', 'COVUNL'
    EVENT_ENT_FAIL, EVENT_COV_FAIL = 'EFAIL', 'CFAIL'
    EVENT_CASH_IN, EVENT_CASH_OUT =  'CI', 'CO'
    OPEN_KEYS = ('SIZE', 'TRIG', 'ENT', 'TP', 'SL', 'TSL', 'PAR', 'COVS')
    CLOSED_KEYS = ('SIZE', 'TRIG', 'ENT', 'PAR', 'COVS', 'EXIT', 'PIPS')
    # SIZE, ENTRY, TRIGGER, TP, SL, TSL, CSL, COVS, REM_COVS = 0, 1, 2, 3, 4, 5, 6, 7, 8
    # EXIT, PIPS = 2, 3
    LONG, SHORT = 1, -1
    NEW, COVER = 0 , 1
    MC_PERCENT = 0.50

    def __init__(
            self,
            name: str,
            df: pd.DataFrame,
            instruments: str,
            ticker: str,
            init_bal: float,
            init_trade_size: int,
            grid_pips: int,
            sl_grid_count: int,
            notrade_margin_percent: float,
            notrade_count: tuple,
            tp_factor: str,
            sizing: str,
            cash_out_factor: float,
            trailing_sl: float):
        
        self.name = name
        self.init_bal = init_bal
        self.init_trade_size = init_trade_size
        self.grid_pips = grid_pips
        self.sl_grid_count = sl_grid_count
        self.sl_pips = grid_pips * sl_grid_count
        self.total_covers = self.sl_grid_count #- 1
        self.sizing_ratio = init_trade_size / init_bal
        self.notrade_margin_percent = notrade_margin_percent
        self.notrade_count = notrade_count
        self.tp_factor = tp_factor
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
        self.trailing_sl = trailing_sl

        self.d = Data(
            source=df.copy(),
            ticker=ticker,
            cols=['time', 'mid_c', 'bid_c', 'ask_c'],
            instruments=instruments
        )

        add_cols = dict(
            open_longs=object,
            open_shorts=object,
            closed_longs=object,
            closed_shorts=object,
            events=object,
            cum_long_position=int,
            cum_short_position=int,
            open_long_count=int,
            open_short_count=int,
            closed_long_count=int,
            closed_short_count=int,
            unrealised_pnl=float,
            realised_pnl=float,
            ac_bal=float,
            net_bal=float,
            margin_used=float,
            # uncovered_trades=object,
            cash_bal=float,
            gross_bal=float
        )

        # self.d.prepare_fast_data(name=name, start=0, end=self.d.datalen, add_cols=add_cols)
        self.d.prepare_fast_data(name=name, add_cols=add_cols)

    def get_open_longs(self, i: int=None):
        i = self.i if i is None else i
        # open_longs = self.d.fdata('open_longs', i) if type(self.d.fdata('open_longs', i)) == dict else dict()
        # open_longs = dict()
        # for trade_no, trade in open_longs_list.items():
        #     open_longs[trade_no] = dict(
        #                 SIZE=trade[0],
        #                 TRIG=trade[1],
        #                 ENT=trade[2],
        #                 TP=trade[3],
        #                 SL=trade[4],
        #                 TSL=trade[5],
        #                 PAR=trade[6],
        #                 COVS=trade[7]
        #             )
        # return open_longs
        return self.d.to_dict_of_dicts('open_longs', self.OPEN_KEYS, i)
    
    def get_open_shorts(self, i: int=None):
        i = self.i if i is None else i
        # open_shorts_list = self.d.fdata('open_shorts', i) if type(self.d.fdata('open_shorts', i)) == dict else dict()
        # open_shorts = dict()
        # for trade_no, trade in open_shorts_list.items():
        #     open_shorts[trade_no] = dict(
        #                 SIZE=trade[0],
        #                 TRIG=trade[1],
        #                 ENT=trade[2],
        #                 TP=trade[3],
        #                 SL=trade[4],
        #                 TSL=trade[5],
        #                 PAR=trade[6],
        #                 COVS=trade[7]
        #             )
        # return open_shorts
        return self.d.to_dict_of_dicts('open_shorts', self.OPEN_KEYS, i)
    
    def get_closed_longs(self, i: int=None):
        i = self.i if i is None else i
        # closed_longs_tuple = self.d.fdata('closed_longs', i) if type(self.d.fdata('closed_longs', i)) == dict else dict()
        # closed_longs = dict()
        # for trade_no, trade in closed_longs_tuple.items():
        #     closed_longs[trade_no] = dict(
        #                 SIZE=trade[0],
        #                 TRIG=trade[1],
        #                 ENT=trade[2],
        #                 PAR=trade[3],
        #                 COVS=trade[4],
        #                 EXIT=trade[5],
        #                 PIPS=trade[6]
        #             )
        # return closed_longs    
        return self.d.to_dict_of_dicts('closed_longs', self.CLOSED_KEYS, i)
    
    def get_closed_shorts(self, i: int=None):
        i = self.i if i is None else i
        # closed_shorts_tuple = self.d.fdata('closed_shorts', i) if type(self.d.fdata('closed_shorts', i)) == dict else dict()
        # closed_shorts = dict()
        # for trade_no, trade in closed_shorts_tuple.items():
        #     closed_shorts[trade_no] = dict(
        #                 SIZE=trade[0],
        #                 TRIG=trade[1],
        #                 ENT=trade[2],
        #                 PAR=trade[3],
        #                 COVS=trade[4],
        #                 EXIT=trade[5],
        #                 PIPS=trade[6]
        #             )
        # return closed_shorts  
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

    def unrealised_pnl(self):
        open_longs = self.get_open_longs()
        open_shorts = self.get_open_shorts()
        pnl = 0
        for _, trade in open_longs.items():
            pnl = pnl + trade['SIZE'] * (self.d.fdata('mid_c', self.i) - trade['ENT'])
        for _, trade in open_shorts.items():
            pnl = pnl + trade['SIZE'] * (trade['ENT'] - self.d.fdata('mid_c', self.i))
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
    
    def cash_transfer(self):
        net_bal, _ = self.current_ac_values()
        if self.cash_out_factor is not None:
            self.d.update_fdata('cash_bal', self.i, self.d.fdata('cash_bal', self.i-1))
            cash_out_threshold = self.init_bal * self.cash_out_factor
            events = self.d.fdata('events', self.i) if type(self.d.fdata('events', self.i)) == list else list()
            stop_loss = self.EVENT_SL in events or self.EVENT_MC in events
            # Cash out / withdraw
            if net_bal > cash_out_threshold:
                cash_out = net_bal - cash_out_threshold
                self.d.update_fdata('ac_bal', self.i, round(self.d.fdata('ac_bal', self.i-1) - cash_out, 2))
                self.d.update_fdata('cash_bal', self.i, round(self.d.fdata('cash_bal', self.i) + cash_out, 2))
                # self.update_temp_ac_values()
                self.update_events(self.EVENT_CASH_OUT)
                return cash_out
            # Deposit money into a/c when net_bal < cash_out_threshold
            elif stop_loss and net_bal < cash_out_threshold:
                cash_in = min(cash_out_threshold - net_bal, self.d.fdata('cash_bal', self.i))
                if cash_in > 0:
                    self.d.update_fdata('ac_bal', self.i, round(self.d.fdata('ac_bal', self.i-1) + cash_in, 2))
                    self.d.update_fdata('cash_bal', self.i, round(self.d.fdata('cash_bal', self.i) - cash_in, 2))
                    # self.update_temp_ac_values()
                    self.update_events(self.EVENT_CASH_IN)    
                    return cash_in  

    def current_ac_values(self):
        ac_bal = self.d.fdata('ac_bal', self.i-1) + self.d.fdata('realised_pnl', self.i)
        margin_used = (self.d.fdata('cum_long_position', self.i) + 
                       self.d.fdata('cum_short_position', self.i)) * float(self.d.ticker['marginRate'])
        net_bal = ac_bal + self.d.fdata('unrealised_pnl', self.i)
        return net_bal, margin_used      

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
            # self.d.update_fdata('uncovered_trades', self.i, self.d.fdata('uncovered_trades', self.i-1))
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
            events = self.d.fdata('events', self.i) if type(self.d.fdata('events', self.i)) == list else list()
            cash_transfer = self.EVENT_CASH_IN in events or self.EVENT_CASH_OUT in events
            ac_bal = self.d.fdata('ac_bal', self.i) if cash_transfer else self.d.fdata('ac_bal', self.i-1)
            self.d.update_fdata('ac_bal', self.i, round(ac_bal + self.d.fdata('realised_pnl', self.i), 2))

        self.d.update_fdata('net_bal', self.i, round(self.d.fdata('ac_bal', self.i) + self.d.fdata('unrealised_pnl', self.i), 2))
        self.d.update_fdata('margin_used', self.i, \
                            round((self.d.fdata('cum_long_position', self.i) + 
                                   self.d.fdata('cum_short_position', self.i)) * float(self.d.ticker['marginRate']), 2))
        
        if self.cash_out_factor is not None:
            self.d.update_fdata('gross_bal', self.i, round(self.d.fdata('ac_bal', self.i) + self.d.fdata('cash_bal', self.i), 2))
        else:
            self.d.update_fdata('gross_bal', self.i, self.d.fdata('ac_bal', self.i))
           
    def calc_trade_size(self):
        if self.i == 0:
            trade_size = self.init_trade_size
        else:
            net_bal, margin_used = self.current_ac_values()
            trade_size = int(net_bal * self.sizing_ratio) if self.sizing == 'dynamic' else self.init_trade_size
            if self.notrade_margin_percent is not None and self.notrade_count[self.NEW] is not None:
                allowed_trade_size = max(0, (net_bal / self.notrade_margin_percent - margin_used) / (2 * float(self.d.ticker['marginRate'])))
                trade_size = int(min(trade_size, allowed_trade_size))
            if self.notrade_count[self.NEW] is not None and self.notrade_count[self.NEW] < self.d.fdata('open_long_count', self.i) + self.d.fdata('open_short_count', self.i):
                trade_size = 0
        return trade_size
    
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
        pips = round((self.d.fdata('ask_c',  self.i) - closing_long['ENT']) * pow(10, -self.d.ticker['pipLocation']), 1)
        closed_longs = self.get_closed_longs()
        # closed_longs[trade_no] = (closing_long['SIZE'], closing_long['ENT'], self.d.fdata('bid_c',  self.i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)
        closed_longs[trade_no] = dict(
            SIZE=closing_long['SIZE'],
            TRIG=closing_long['TRIG'],
            ENT=closing_long['ENT'],
            PAR=closing_long['PAR'],
            COVS=closing_long['COVS'],
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
        pips = round((closing_short['ENT'] - self.d.fdata('bid_c',  self.i)) * pow(10, -self.d.ticker['pipLocation']), 1)
        closed_shorts = self.get_closed_shorts()
        # closed_shorts[trade_no] = (closing_short['SIZE'], closing_short['ENT'], self.d.fdata('ask_c',  self.i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)
        closed_shorts[trade_no] = dict(
            SIZE=closing_short['SIZE'],
            TRIG=closing_short['TRIG'],
            ENT=closing_short['ENT'],
            PAR=closing_short['PAR'],
            COVS=closing_short['COVS'],
            EXIT=self.d.fdata('ask_c',  self.i),
            PIPS=pips
        )
        self.update_closed_shorts(closed_shorts)

    def cover_triggers(self, trigger_price: float, parent: int):
        covers = dict()
        csl_pips = self.grid_pips
        cover_grid_count = 1
        for _ in range(self.total_covers):
            csl_pips = self.grid_pips * cover_grid_count
            if parent == self.LONG:
                # long_csl = round(self.d.fdata('mid_c', self.i) - csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                long_csl = round(trigger_price - csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                covers[long_csl] = 0
            elif parent == self.SHORT:
                # short_csl = round(self.d.fdata('mid_c', self.i) + csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                short_csl = round(trigger_price + csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                covers[short_csl] = 0
            cover_grid_count = cover_grid_count + 1
        return covers
    
    def entry(self):
        up_grid = self.d.fdata('mid_c', self.i) >= self.next_up_grid 
        down_grid = self.d.fdata('mid_c', self.i) <= self.next_down_grid
        if up_grid or down_grid:
            # long_tp = round(self.d.fdata('mid_c', self.i) + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            # short_tp = round(self.d.fdata('mid_c', self.i) - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)         

            trigger = self.next_up_grid if up_grid else self.next_down_grid
            long_tp = round(trigger + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            short_tp = round(trigger - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)  

            trade_size = self.calc_trade_size()
            open_longs = self.get_open_longs()
            open_shorts = self.get_open_shorts()
            
            if trade_size == 0:
                self.update_events(self.EVENT_ENT_FAIL)
            else:
                self.trade_no = self.trade_no + 1

                # long_sl = round(self.d.fdata('mid_c', self.i) - self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                # short_sl = round(self.d.fdata('mid_c', self.i) + self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                long_sl = round(trigger - self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                short_sl = round(trigger + self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                
                # long_covers = self.cover_triggers(self.next_up_grid, self.LONG)
                # short_covers = self.cover_triggers(self.next_down_grid, self.LONG)
                # long_csl = round(self.d.fdata('mid_c', self.i) - csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                # short_csl = round(self.d.fdata('mid_c', self.i) + csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                open_longs[self.trade_no] = dict(
                    SIZE=trade_size,
                    TRIG=trigger,
                    ENT=self.d.fdata('ask_c', self.i),
                    TP=long_tp,
                    SL=long_sl,
                    # CSL=long_csl,
                    TSL=0,
                    PAR=0,
                    COVS=self.cover_triggers(trigger, self.LONG)
                    # REM_COVS=self.total_covers
                )
                # (trade_size, self.d.fdata('ask_c', self.i), self.next_up_grid, long_tp, long_sl, 0, long_csl, list(), self.total_covers) # (SIZE, ENTRY, TP, SL, TSL, CSL, COVS, REM_COVS)
                # open_shorts[self.trade_no] = (trade_size, self.d.fdata('bid_c', self.i), self.next_down_grid, short_tp, short_sl, 0, short_csl, list(), self.total_covers) # (SIZE, ENTRY, TP, SL, TSL, CSL, COVS, REM_COVS)
                open_shorts[self.trade_no] = dict(
                    SIZE=trade_size,
                    TRIG=trigger,
                    ENT=self.d.fdata('bid_c', self.i),
                    TP=short_tp,
                    SL=short_sl,
                    # CSL=short_csl,
                    TSL=0,
                    PAR=0,
                    COVS=self.cover_triggers(trigger, self.SHORT)
                    # REM_COVS=self.total_covers
                )
                self.update_open_longs(open_longs)
                self.update_open_shorts(open_shorts)
                
                self.update_temp_ac_values()
                self.update_events(self.EVENT_ENTRY)
            
            self.next_up_grid = long_tp
            self.next_down_grid = short_tp  

    def cover_entry(self):
        open_longs = self.get_open_longs()
        open_shorts = self.get_open_shorts()

        # csl_pips = self.grid_pips * (self.sl_grid_count / 2 - 1)

        # Long cover entries
        # long_covers = dict()
        # tot_long_cover_trade_size = 0
        for trade_no, trade in open_shorts.items():
            for csl, cov_trade_no in trade['COVS'].items():
                if self.d.fdata('mid_c', self.i-1) < csl and self.d.fdata('mid_c', self.i) >= csl and cov_trade_no == 0:
                    trade_size = self.calc_trade_size()
                    if self.notrade_margin_percent is not None and self.notrade_count[self.COVER] is not None:
                        net_bal, margin_used = self.current_ac_values()
                        # required_margin = tot_long_cover_trade_size * float(self.d.ticker['marginRate'])
                        # allowed_trade_size = max(0, (net_bal / self.notrade_margin_percent - (margin_used + required_margin)) / float(self.d.ticker['marginRate']))
                        allowed_trade_size = max(0, (net_bal / self.notrade_margin_percent - margin_used) / float(self.d.ticker['marginRate']))
                    else:
                        allowed_trade_size = 0
                    if self.notrade_margin_percent is not None and allowed_trade_size < trade['SIZE']:
                        self.update_events(self.EVENT_COV_FAIL)
                    elif self.notrade_count[self.COVER] is not None and self.notrade_count[self.COVER] < self.d.fdata('open_long_count', self.i) + self.d.fdata('open_short_count', self.i):
                        self.update_events(self.EVENT_COV_FAIL)
                    else:
                        self.trade_no = self.trade_no + 1
                        # long_tp = trade['SL']
                        long_tp = round(csl + self.tp_factor * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5) 
                        # long_sl = round(self.d.fdata('mid_c', self.i) - self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # long_sl = round(trade['ENT'] - trade['REM_COVS'] * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        long_sl = round(csl - self.tp_factor * self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # long_csl = round(self.d.fdata('mid_c', self.i) - csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # long_csl = round(csl - csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # open_longs[self.trade_no] = (trade['SIZE'], self.d.fdata('ask_c', self.i), trade['CSL'], long_tp, long_sl, 0, long_csl, list(), self.total_covers) # (SIZE, ENTRY, TP, SL, TSL, CSL, COVS, REM_COVS)
                        open_longs[self.trade_no] = dict(
                            SIZE= 2*trade_size, #trade['SIZE'],
                            TRIG=csl,
                            ENT=self.d.fdata('ask_c', self.i),
                            TP=long_tp,
                            SL=long_sl,
                            # CSL=long_csl,
                            TSL=0,
                            PAR=trade_no,
                            COVS=self.cover_triggers(csl, self.LONG)
                            # REM_COVS=self.total_covers
                        )
                        self.update_open_longs(open_longs)
                        
                        self.update_temp_ac_values()
                        self.update_events(self.EVENT_COVER)

                        # Update open short position: Update cover trade
                        open_shorts[trade_no]['COVS'][csl] = self.trade_no
                        self.update_open_shorts(open_shorts)

        # Short cover entries
        for trade_no, trade in open_longs.items():
            for csl, cov_trade_no in trade['COVS'].items():
                trade_size = self.calc_trade_size()
                if self.d.fdata('mid_c', self.i-1) > csl and self.d.fdata('mid_c', self.i) <= csl and cov_trade_no == 0:
                    if self.notrade_margin_percent is not None and self.notrade_count[self.COVER] is not None:
                        net_bal, margin_used = self.current_ac_values()
                        allowed_trade_size = max(0, (net_bal / self.notrade_margin_percent - margin_used) / float(self.d.ticker['marginRate']))
                    else:
                        allowed_trade_size = 0
                    if self.notrade_margin_percent is not None and allowed_trade_size < trade['SIZE']:
                        self.update_events(self.EVENT_COV_FAIL)
                    elif self.notrade_count[self.COVER] is not None and self.notrade_count[self.COVER] < self.d.fdata('open_long_count', self.i) + self.d.fdata('open_short_count', self.i):
                        self.update_events(self.EVENT_COV_FAIL)
                    else:
                        self.trade_no = self.trade_no + 1
                        # short_tp = trade['SL']
                        short_tp = round(csl - self.tp_factor * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5) 
                        # short_sl = round(self.d.fdata('mid_c', self.i) + self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # short_sl = round(trade['ENT'] + trade['REM_COVS'] * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        short_sl = round(csl + self.tp_factor * self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # short_csl = round(self.d.fdata('mid_c', self.i) + csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # short_csl = round(trade['CSL'] + csl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                        # open_shorts[self.trade_no] = (trade['SIZE'], self.d.fdata('bid_c', self.i), trade['CSL'], short_tp, short_sl, 0, short_csl, list(), self.total_covers) # (SIZE, ENTRY, TP, SL, TSL, CSL, COVS, REM_COVS)
                        open_shorts[self.trade_no] = dict(
                            SIZE=2*trade_size, # trade['SIZE'],
                            TRIG=csl,
                            ENT=self.d.fdata('bid_c', self.i),
                            TP=short_tp,
                            SL=short_sl,
                            # CSL=short_csl,
                            TSL=0,
                            PAR=trade_no,
                            COVS=self.cover_triggers(csl, self.SHORT)
                            # REM_COVS=self.total_covers
                        )
                        self.update_open_shorts(open_shorts)
                        
                        self.update_temp_ac_values()
                        self.update_events(self.EVENT_COVER)

                        # Update open long position: Update cover trade
                        open_longs[trade_no]['COVS'][csl] = self.trade_no
                        self.update_open_longs(open_longs)

    def unlink_parent(self, closed_trade: dict, direction: int):
        adjusted = False
        if direction == self.LONG:
            open_longs = self.get_open_longs()
            for _, trade_no in closed_trade['COVS'].items():
                if trade_no > 0:
                    long_tp = round(open_longs[trade_no]['TRIG'] + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    open_longs[trade_no]['TP'] = long_tp
                    open_longs[trade_no]['PAR'] = 0
                    self.update_open_longs(open_longs)
                    adjusted - True
        else:
            open_shorts = self.get_open_shorts()
            for _, trade_no in closed_trade['COVS'].items():
                if trade_no > 0:
                    short_tp = round(open_shorts[trade_no]['TRIG'] - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5) 
                    open_shorts[trade_no]['TP'] = short_tp
                    open_shorts[trade_no]['PAR'] = 0
                    self.update_open_shorts(open_shorts)
                    adjusted = True
        
        if adjusted:
            # self.update_temp_ac_values()
            self.update_events(self.EVENT_PAR_UNLINK)
    
    def unlink_cover(self, closed_trade_no: int, parent_trade_no: int, direction: int):
        adjusted = False
        # Unlink closed cover in parent
        if direction == self.LONG:
            open_longs = self.get_open_longs()
            # for parent_trade_no, parent_trade in open_longs.items():
            for csl, cover_trade_no in open_longs[parent_trade_no]['COVS'].items():
                if cover_trade_no == closed_trade_no:
                    open_longs[parent_trade_no]['COVS'][csl] = 0
                    self.update_open_longs(open_longs)
                    adjusted - True
        else:
            open_shorts = self.get_open_shorts()
            # for parent_trade_no, parent_trade in open_shorts.items():
            for csl, cover_trade_no in open_shorts[parent_trade_no]['COVS'].items():
                if cover_trade_no == closed_trade_no:
                    open_shorts[parent_trade_no]['COVS'][csl] = 0
                    self.update_open_shorts(open_shorts)
                    adjusted - True
        
        if adjusted:
            # self.update_temp_ac_values()
            self.update_events(self.EVENT_COV_UNLINK)
    
    def take_profit(self):     
        traded = False
        # Close long positions take profit
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade['TP']:
                self.close_long(trade_no)
                self.unlink_parent(trade, self.SHORT)
                if trade['PAR'] != 0:
                    self.unlink_cover(trade_no, trade['PAR'], self.SHORT)
                traded = True

        # Close short positions take profit
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade['TP']:
                self.close_short(trade_no)
                self.unlink_parent(trade, self.LONG)
                if trade['PAR'] != 0:
                    self.unlink_cover(trade_no, trade['PAR'], self.LONG)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)   

    def stop_loss_grid_count(self):
        traded = False
        # Close long positions stop loss
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) <= trade['SL']:
                self.close_long(trade_no)
                # self.cover_sl_direction = self.SHORT
                # self.update_uncovered_trades(trade_no, self.EVENT_SL)
                self.unlink_parent(trade, self.SHORT)
                if trade['PAR'] != 0:
                    self.unlink_cover(trade_no, trade['PAR'], self.SHORT)
                traded = True

        # Close short positions stop loss
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) >= trade['SL']:
                self.close_short(trade_no)
                # self.cover_sl_direction = self.LONG
                # self.update_uncovered_trades(trade_no, self.EVENT_SL)
                self.unlink_parent(trade, self.LONG)
                if trade['PAR'] != 0:
                    self.unlink_cover(trade_no, trade['PAR'], self.LONG)
                traded = True

        return traded
    
    def stop_loss(self):
        traded = self.stop_loss_grid_count()

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_SL)

    # def cum_sl_pips(self):
    #     closed_longs = deepcopy(self.d.fdata('closed_longs', self.i))
    #     cum_sl_longs = 0
    #     for trade_no, trade in closed_longs.items():
    #         if trade['PIPS'] < 0:
    #             cum_sl_longs = cum_sl_longs + trade['PIPS']
    #     closed_shorts = deepcopy(self.d.fdata('closed_shorts', self.i))
    #     cum_sl_shorts = 0
    #     for trade_no, trade in closed_shorts.items():
    #         if trade['PIPS'] < 0:
    #             cum_sl_shorts = cum_sl_shorts + trade['PIPS']
    #     return cum_sl_longs, cum_sl_shorts
    
    def margin_call(self):
        net_bal, margin_used = self.current_ac_values()
        # cum_position = self.d.fdata('cum_long_position', self.i) + self.d.fdata('cum_short_position', self.i)
        traded = False
        if net_bal < margin_used * self.MC_PERCENT:
            open_longs = self.get_open_longs()
            for trade_no, trade in open_longs.items():
                self.close_long(trade_no)
                # self.update_uncovered_trades(trade_no, self.EVENT_MC)
                traded = True

            open_shorts = self.get_open_shorts()
            for trade_no, trade in open_shorts.items():
                self.close_short(trade_no)
                # self.update_uncovered_trades(trade_no, self.EVENT_MC)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_MC)

            # # if len(open_longs) > len(open_shorts):
            # if self.d.fdata('long_count', self.i) > self.d.fdata('short_count', self.i)
            #     self.cover_sl_direction = self.SHORT
            # # elif len(open_longs) < len(open_shorts):
            # elif self.d.fdata('long_count', self.i) < self.d.fdata('short_count', self.i)
            #     self.cover_sl_direction = self.LONG
            # else:
            #     cum_sl_longs, cum_sl_shorts = self.cum_sl_pips()
            #     self.cover_sl_direction = self.LONG if cum_sl_shorts < cum_sl_longs else self.SHORT
  
            # self.update_ac_values()

    def update_trailing_sl(self):
        adjusted = False
        # Update long positions, update next_tp, TSL
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade['TP']:
                next_tp = round(trade['TP'] + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade['ENT'] + (trade['TP'] - trade['ENT']) / 2, 5) if trade['TSL'] == 0 else trade['TP']               
                # open_longs[trade_no] = (trade['SIZE'], trade['ENT'], next_tp, trade['SL'], trade[self.COVERED], tsl)
                open_longs[trade_no]['TP'] = next_tp
                open_longs[trade_no]['TSL'] = tsl
                adjusted = True
        self.update_open_longs(open_longs)

        # Update short positions, update TSL
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade['TP']:
                next_tp = round(trade['TP'] - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade['ENT'] - (trade['ENT'] - trade['TP']) / 2, 5) if trade['TSL'] == 0 else trade['TP']
                # open_shorts[trade_no] = (trade['SIZE'], trade['ENT'], next_tp, trade['SL'], trade[self.COVERED], tsl)
                open_shorts[trade_no]['TP'] = next_tp
                open_shorts[trade_no]['TSL'] = tsl
                adjusted = True
        self.update_open_shorts(open_shorts)

        if adjusted:
            self.update_events(self.EVENT_TSL_ADJUST)  

    def take_profit_tsl(self):
        traded = False
        # Close long positions take profit
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) <= trade['TSL'] and trade['TSL'] != 0:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) >= trade['TSL'] and trade['TSL'] != 0:
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)
    
    def update_init_values(self):
        self.trade_no = 0
        self.next_up_grid = self.d.fdata('mid_c', 0)
        self.next_down_grid = self.d.fdata('mid_c', 0)
        if self.cash_out_factor is not None:
            self.d.update_fdata('cash_bal', self.i, 0)
        # self.cover_sl_direction = None
    
    def run_sim(self):
        for i in tqdm(range(self.d.fdatalen), desc=" Simulating... "):
            self.i = i
            if self.i == 0:
                self.update_init_values()
            else:
                self.update_temp_ac_values(init=True)
                self.margin_call()
                # self.cash_transfer()
                # up_grid = self.d.fdata('mid_c', self.i) >= self.next_up_grid 
                # down_grid = self.d.fdata('mid_c', self.i) <= self.next_down_grid
                # if up_grid or down_grid:
                if self.trailing_sl:
                    self.update_trailing_sl()
                self.cover_entry()
                self.stop_loss()
                if self.trailing_sl:
                    self.take_profit_tsl()
                else:
                    self.take_profit()
                self.cash_transfer()
                # self.cover_entry()
                self.entry()
            self.update_ac_values()
