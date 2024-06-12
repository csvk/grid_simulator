from data import Data
from tqdm import trange
import pandas as pd
from collections import deque

class GridSimulator:

    EVENT_TP, EVENT_SL, EVENT_MC, EVENT_ENTRY, EVENT_TSL_ADJUST, EVENT_ENT_FAIL  = 'TP', 'SL', 'MC', 'ENT', 'TSLADJ', 'EFAIL'
    EVENT_CASH_IN, EVENT_CASH_OUT =  'CI', 'CO'
    EVENT_UP, EVENT_DOWN = 'UP', 'DN'
    OPEN_KEYS = ('SIZE', 'TRIG', 'ENT', 'TP', 'SL', 'TSL')
    CLOSED_KEYS = ('SIZE', 'TRIG', 'ENT', 'EXIT', 'PIPS')
    LONG, SHORT = 1, -1
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
            tp_grid_count: int,
            sl_grid_count: int,
            max_unrealised_pnl: float,
            max_trades_per_grid: int,
            max_trades_per_side: int,
            moves_for_weightage: int,
            sizing: str,
            cash_out_factor: float,
            trailing_sl: float,
            grid_reset: bool):
        
        self.name = name
        self.init_bal = init_bal
        self.init_trade_size = init_trade_size
        self.grid_pips = grid_pips
        self.tp_grid_count = tp_grid_count
        self.tp_pips = grid_pips * tp_grid_count
        self.sl_grid_count = sl_grid_count
        self.sl_pips = grid_pips * sl_grid_count
        self.grid_reset_pips = grid_pips * sl_grid_count / 2
        self.max_unrealised_pnl = max_unrealised_pnl
        self.max_trades_per_grid= max_trades_per_grid
        self.max_trades_per_side = max_trades_per_side
        self.moves_for_weightage = moves_for_weightage
        self.sizing_ratio = init_trade_size / init_bal
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
        self.trailing_sl = trailing_sl
        self.grid_reset = grid_reset

        self.d = Data(
            source=df.copy(),
            ticker=ticker,
            cols=['time', 'mid_c', 'bid_c', 'ask_c'],
            instruments=instruments
        )

        add_cols = dict(
            trigger=float,
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
            moves_hist=object,
            up_moves_ratio=object,
            down_moves_ratio=object,
            grid_trades_long=object,
            grid_trades_short=object,
            unrealised_pnl=float,
            realised_pnl=float,
            ac_bal=float,
            net_bal=float,
            margin_used=float,
            cash_bal=float,
            gross_bal=float
        )

        self.d.prepare_fast_data(name=name, add_cols=add_cols)

    def get_open_longs(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('open_longs', self.OPEN_KEYS, i)
    
    def get_open_shorts(self, i: int=None):
        i = self.i if i is None else i
        return self.d.to_dict_of_dicts('open_shorts', self.OPEN_KEYS, i)
    
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
        _, net_bal, _ = self.current_ac_values()
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
                self.update_events(self.EVENT_CASH_OUT)
                return cash_out
            # Deposit money into a/c when net_bal < cash_out_threshold
            elif stop_loss and net_bal < cash_out_threshold:
                cash_in = min(cash_out_threshold - net_bal, self.d.fdata('cash_bal', self.i))
                if cash_in > 0:
                    self.d.update_fdata('ac_bal', self.i, round(self.d.fdata('ac_bal', self.i-1) + cash_in, 2))
                    self.d.update_fdata('cash_bal', self.i, round(self.d.fdata('cash_bal', self.i) - cash_in, 2))
                    self.update_events(self.EVENT_CASH_IN)    
                    return cash_in  

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
            self.d.update_fdata('moves_hist', self.i, self.d.fdata('moves_hist', self.i-1))
            self.d.update_fdata('up_moves_ratio', self.i, self.d.fdata('up_moves_ratio', self.i-1))
            self.d.update_fdata('down_moves_ratio', self.i, self.d.fdata('down_moves_ratio', self.i-1))
            self.d.update_fdata('grid_trades_long', self.i, self.d.fdata('grid_trades_long', self.i-1))
            self.d.update_fdata('grid_trades_short', self.i, self.d.fdata('grid_trades_short', self.i-1))
        else:
            self.d.update_fdata('cum_long_position', self.i, self.cum_long_position())
            self.d.update_fdata('cum_short_position', self.i, self.cum_short_position())
            self.d.update_fdata('open_long_count', self.i, len(self.get_open_longs()))
            self.d.update_fdata('open_short_count', self.i, len(self.get_open_shorts()))
            self.d.update_fdata('closed_long_count', self.i, len(self.get_closed_longs()))
            self.d.update_fdata('closed_short_count', self.i, len(self.get_closed_shorts()))
            moves = self.d.fdata('moves_hist', self.i)
            up_moves, down_moves = moves.count(self.EVENT_UP), moves.count(self.EVENT_DOWN)
            self.d.update_fdata(f'up_moves_ratio', self.i, round(up_moves / len(moves), 2))
            self.d.update_fdata(f'down_moves_ratio', self.i, round(down_moves / len(moves), 2))
        
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
            _, net_bal, _ = self.current_ac_values()
            trade_size = int(net_bal * self.sizing_ratio) if self.sizing == 'dynamic' else self.init_trade_size
            
            if self.moves_for_weightage is None:
                long_trade_size, short_trade_size = trade_size, trade_size
            else:
                long_trade_size, short_trade_size = self.weighted_trade_size(trade_size)

        return long_trade_size, short_trade_size
    
    def weighted_trade_size(self, trade_size: int):
        long_trade_size, short_trade_size = trade_size, trade_size
        if len(self.d.fdata('moves_hist', self.i)) == self.moves_for_weightage:
            long_trade_size = int(trade_size * 2 * self.d.fdata('up_moves_ratio', self.i))
            short_trade_size = int(trade_size * 2 * self.d.fdata('down_moves_ratio', self.i))
        return long_trade_size, short_trade_size
    
    def update_events(self, event):
        events = self.d.fdata('events', self.i) if type(self.d.fdata('events', self.i)) == list else list()
        if event not in events:
            events.append(event)
            self.d.update_fdata('events', self.i, events)

    def update_moves_hist(self):
        if self.up_grid or self.down_grid:
            move = self.EVENT_UP if self.up_grid else self.EVENT_DOWN
            moves_hist = deque(maxlen=self.moves_for_weightage)
            moves_hist.extend(self.d.fdata('moves_hist', self.i))
            moves_hist.append(move)
            self.d.update_fdata('moves_hist', self.i, tuple(moves_hist))

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
            EXIT=self.d.fdata('bid_c',  self.i),
            PIPS=pips
        )
        self.update_closed_longs(closed_longs)
        # self.update_hist(pips, self.LONG)

        if self.max_trades_per_grid is not None:
            grid_trades_long = self.d.fdata('grid_trades_long', self.i) \
                if type(self.d.fdata('grid_trades_long', self.i)) == dict else dict()
            if grid_trades_long[closing_long['TRIG']] > 1:
                grid_trades_long[closing_long['TRIG']] = grid_trades_long[closing_long['TRIG']] - 1
            else:
                del grid_trades_long[closing_long['TRIG']]
            self.d.update_fdata('grid_trades_long', self.i, grid_trades_long)
        

    def close_short(self, trade_no: int):
        # Remove from open shorts
        open_shorts = self.get_open_shorts()
        closing_short = open_shorts[trade_no]
        del open_shorts[trade_no]
        self.update_open_shorts(open_shorts)

        # Append to closed shorts
        pips = round((closing_short['ENT'] - self.d.fdata('bid_c',  self.i)) * pow(10, -self.d.ticker['pipLocation']), 1)
        closed_shorts = self.get_closed_shorts()
        closed_shorts[trade_no] = dict(
            SIZE=closing_short['SIZE'],
            TRIG=closing_short['TRIG'],
            ENT=closing_short['ENT'],
            EXIT=self.d.fdata('ask_c',  self.i),
            PIPS=pips
        )
        self.update_closed_shorts(closed_shorts)
        # self.update_hist(pips, self.SHORT)

        if self.max_trades_per_grid is not None:
            grid_trades_short = self.d.fdata('grid_trades_short', self.i) \
                if type(self.d.fdata('grid_trades_short', self.i)) == dict else dict()
            if grid_trades_short[closing_short['TRIG']] > 1:
                grid_trades_short[closing_short['TRIG']] = grid_trades_short[closing_short['TRIG']] - 1
            else:
                del grid_trades_short[closing_short['TRIG']]
            self.d.update_fdata('grid_trades_short', self.i, grid_trades_short)

    def entry(self):
        # up_grid = self.d.fdata('mid_c', self.i) >= self.next_up_grid 
        # down_grid = self.d.fdata('mid_c', self.i) <= self.next_down_grid
        traded = False
        if self.up_grid or self.down_grid:
            # self.trigger = self.next_up_grid if self.up_grid else self.next_down_grid
            long_tp = round(self.trigger + self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
            short_tp = round(self.trigger - self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)  

            long_trade_size, short_trade_size = self.calc_trade_size()
            open_longs = self.get_open_longs()
            open_shorts = self.get_open_shorts()

            if self.max_trades_per_grid is not None:
                grid_trades_long = self.d.fdata('grid_trades_long', self.i) \
                    if type(self.d.fdata('grid_trades_long', self.i)) == dict else dict()
                grid_trades_short = self.d.fdata('grid_trades_short', self.i) \
                    if type(self.d.fdata('grid_trades_short', self.i)) == dict else dict()
            
            if long_trade_size + short_trade_size == 0:
                self.update_events(self.EVENT_ENT_FAIL)
            else:
                self.trade_no = self.trade_no + 1

                long_sl = round(self.trigger - self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                short_sl = round(self.trigger + self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)

                if long_trade_size > 0:
                    if self.max_trades_per_grid is not None:
                        if self.trigger not in grid_trades_long:
                            grid_trades_long[self.trigger] = 1
                            trade = True
                        elif grid_trades_long[self.trigger] < self.max_trades_per_grid:
                            grid_trades_long[self.trigger] = grid_trades_long[self.trigger] + 1
                            trade = True
                        else:
                            trade = False
                    else:
                        trade = True

                    if trade:
                        open_longs[self.trade_no] = dict(
                            SIZE=long_trade_size,
                            TRIG=self.trigger,
                            ENT=self.d.fdata('ask_c', self.i),
                            TP=long_tp,
                            SL=long_sl,
                            TSL=0
                        )
                        self.update_open_longs(open_longs)
                        if self.max_trades_per_grid is not None:
                            self.d.update_fdata('grid_trades_long', self.i, grid_trades_long)
                        traded = True
                    else:
                        self.update_events(self.EVENT_ENT_FAIL)

                if short_trade_size > 0:
                    if self.max_trades_per_grid is not None:
                        if self.trigger not in grid_trades_short:
                            grid_trades_short[self.trigger] = 1
                            trade = True
                        elif grid_trades_short[self.trigger] < self.max_trades_per_grid:
                            grid_trades_short[self.trigger] = grid_trades_short[self.trigger] + 1
                            trade = True
                        else:
                            trade = False
                    else:
                        trade = True

                    if trade:
                        open_shorts[self.trade_no] = dict(
                            SIZE=short_trade_size,
                            TRIG=self.trigger,
                            ENT=self.d.fdata('bid_c', self.i),
                            TP=short_tp,
                            SL=short_sl,
                            TSL=0
                        )
                        self.update_open_shorts(open_shorts)
                        if self.max_trades_per_grid is not None:
                            self.d.update_fdata('grid_trades_short', self.i, grid_trades_short)
                        traded = True
                    else:
                        self.update_events(self.EVENT_ENT_FAIL)
            
                if traded:
                    self.update_temp_ac_values()
                    self.update_events(self.EVENT_ENTRY)
            
            # self.next_up_grid = round(self.trigger + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            # self.next_down_grid = round(self.trigger - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)  
    
    def take_profit(self):     
        traded = False
        # Close long positions take profit
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade['TP']:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade['TP']:
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)   

    def stop_loss_grid_count(self):
        # Close long positions stop loss
        long_stopped = False
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) <= trade['SL']:
                self.close_long(trade_no)
                long_stopped = True

        # Close short positions stop loss
        short_stopped = False
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) >= trade['SL']:
                self.close_short(trade_no)
                short_stopped = True

        if self.grid_reset and (long_stopped or short_stopped):
            long_sl_entry = round(self.trigger + self.grid_reset_pips * pow(10, self.d.ticker['pipLocation']), 5)
            short_sl_entry = round(self.trigger - self.grid_reset_pips * pow(10, self.d.ticker['pipLocation']), 5)

            # Close long positions grid reset
            if long_stopped:
                open_longs = self.get_open_longs()
                for trade_no, trade in open_longs.items():
                    if trade['ENT'] >= long_sl_entry:
                        self.close_long(trade_no)

            # Close short positions grid reset
            if short_stopped:
                open_shorts = self.get_open_shorts()
                for trade_no, trade in open_shorts.items():
                    if trade['ENT'] <= short_sl_entry:
                        self.close_short(trade_no)
        
        return long_stopped or short_stopped
    
    def stop_loss_max_unrealised_pnl(self):
        traded = False
        price = self.d.fdata('mid_c', self.i)
        ac_bal, _, _ = self.current_ac_values()
        while ac_bal * self.max_unrealised_pnl < -self.d.fdata('unrealised_pnl', self.i):
            farthest_long_price, farthest_short_price = price, price
            farthest_long, farthest_short = None, None
            open_longs = self.get_open_longs(self.i)
            for long, trade in open_longs.items():
                if trade['ENT'] > farthest_long_price:
                    farthest_long_price = trade['ENT']
                    farthest_long = long
            open_shorts = self.get_open_shorts(self.i)
            for short, trade in open_shorts.items():
                if trade['ENT'] < farthest_short_price:
                    farthest_short_price = trade['ENT']
                    farthest_short = short
            if farthest_long == None and farthest_short == None:
                pass
            else:
                if farthest_long == None:
                    self.close_short(farthest_short)
                elif farthest_short == None:
                    self.close_long(farthest_long)
                else:
                    if farthest_long_price - price > price - farthest_short_price:
                        self.close_long(farthest_long)
                    else:
                        self.close_short(farthest_short)
                self.update_temp_ac_values()
                ac_bal, _, _ = self.current_ac_values()
                traded = True

        return traded
    
    def stop_loss_max_trades(self):
        traded = False
        price = self.d.fdata('mid_c', self.i)

        while self.d.fdata('open_long_count', self.i) >= self.max_trades_per_side:
            farthest_long_price = price
            farthest_long = None
            open_longs = self.get_open_longs(self.i)
            for long, trade in open_longs.items():
                if trade['ENT'] > farthest_long_price:
                    farthest_long_price = trade['ENT']
                    farthest_long = long

            if farthest_long is None:
                break
            else:
                self.close_long(farthest_long)
                self.update_temp_ac_values()
                traded = True

        while self.d.fdata('open_short_count', self.i) >= self.max_trades_per_side:
            farthest_short_price = price
            farthest_short = None
            open_shorts = self.get_open_shorts(self.i)
            for short, trade in open_shorts.items():
                if trade['ENT'] < farthest_short_price:
                    farthest_short_price = trade['ENT']
                    farthest_short = short

            if farthest_short is None:
                break
            else:
                self.close_short(farthest_short)
                self.update_temp_ac_values()
                traded = True

        return traded    
    
    def stop_loss(self):
        if self.max_unrealised_pnl is not None:
            traded = self.stop_loss_max_unrealised_pnl()
        else:
            traded = self.stop_loss_grid_count()
        
        if self.max_trades_per_side is not None:
            traded = self.stop_loss_max_trades()

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_SL)
    
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

    def update_trailing_sl(self):
        adjusted = False
        # Update long positions, update next_tp, TSL
        open_longs = self.get_open_longs()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade['TP']:
                # next_tp = round(trade['TP'] + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                next_tp = self.next_up_grid
                # tsl = round(trade['ENT'] + (trade['TP'] - trade['ENT']) / 2, 5) if trade['TSL'] == 0 else trade['TP']  
                tsl = round(next_tp - self.grid_pips * 2 * pow(10, self.d.ticker['pipLocation']), 5)             
                open_longs[trade_no]['TP'] = next_tp
                open_longs[trade_no]['TSL'] = tsl
                adjusted = True
        self.update_open_longs(open_longs)

        # Update short positions, update TSL
        open_shorts = self.get_open_shorts()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade['TP']:
                # next_tp = round(trade['TP'] - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                next_tp = self.next_down_grid
                # tsl = round(trade['ENT'] - (trade['ENT'] - trade['TP']) / 2, 5) if trade['TSL'] == 0 else trade['TP']
                tsl = round(next_tp + self.grid_pips * 2 * pow(10, self.d.ticker['pipLocation']), 5)    
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
        self.d.update_fdata('moves_hist', self.i, tuple())
        if self.cash_out_factor is not None:
            self.d.update_fdata('cash_bal', self.i, 0)

    def next_grid(self):
        self.up_grid = self.d.fdata('mid_c', self.i) >= self.next_up_grid 
        self.down_grid = self.d.fdata('mid_c', self.i) <= self.next_down_grid        
        if self.up_grid:
            self.update_events(self.EVENT_UP)
        if self.down_grid:
            self.update_events(self.EVENT_DOWN)

        if self.up_grid or self.down_grid:
            up_pips = round((self.d.fdata('mid_c',  self.i) - self.next_up_grid) * pow(10, -self.d.ticker['pipLocation']), 1)
            down_pips = round((self.next_down_grid - self.d.fdata('mid_c',  self.i)) * pow(10, -self.d.ticker['pipLocation']), 1)
            up_grids = int(up_pips / self.grid_pips) if self.i > 1 else 0
            down_grids = int(down_pips / self.grid_pips) if self.i > 1 else 0
            if self.up_grid:
                self.trigger = round(self.next_up_grid + up_grids * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            else:
                self.trigger = round(self.next_down_grid - down_grids * self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            # self.trigger = self.next_up_grid if self.up_grid else self.next_down_grid
            self.next_up_grid = round(self.trigger + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            self.next_down_grid = round(self.trigger - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)

            self.d.update_fdata('trigger', self.i, self.trigger)
        
        self.update_moves_hist()
    
    def run_sim(self):
        self.i = 0
        t = trange(self.d.fdatalen, desc='Simulating...', leave=True)
        # for i in tqdm(range(self.d.fdatalen), desc=f" Simulating... {self.i}"):
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
                self.next_grid()
                self.margin_call()
                if self.up_grid or self.down_grid:
                    if self.trailing_sl:
                        self.update_trailing_sl()
                    self.stop_loss()
                    if self.trailing_sl:
                        self.take_profit_tsl()
                    else:
                        self.take_profit()
                    self.entry()
                self.cash_transfer()
            self.update_ac_values()
            # print(f'Gross balance: {self.d.fdata("gross_bal", self.i)}, Margin used: {self.d.fdata("margin_used", self.i)}', end='\r')
