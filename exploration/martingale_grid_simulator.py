from data import Data
from tqdm import tqdm
import pandas as pd
from numpy import isnan
from random import choice


class GridSimulator:

    EVENT_TP, EVENT_SL, EVENT_MC = 'TP', 'SL', 'MC'
    EVENT_BASE_ENTRY, EVENT_CONTRA_ENTRY, EVENT_PYR_ENTRY, EVENT_SPLIT = 'BASE', 'CON', 'PYR', 'SPLIT'
    EVENT_RESET, EVENT_ADJUST = 'RES', 'ADJ'
    EVENT_CASH_IN, EVENT_CASH_OUT =  'CI', 'CO'
    STREAK_CNT, SIZE, ENTRY, TP, SL, TSL = 0, 1, 2, 3, 4, 5
    EXIT, PIPS = 3, 4
    LONG, SHORT = 1, -1
    MC_PERCENT = 0.50

    def __init__(
            self,
            name: str,
            df: pd.DataFrame,
            instruments: str,
            ticker: str,
            trade_price_type: str,
            init_bal: float,
            init_trade_size: int,
            grid_pips: int,
            sizing: str,
            cash_out_factor: float,
            martingale_factor: float,
            # martingale_factor2: float,
            # factor_reset: int,
            pyramiding: bool,
            streak_reset: int,
            streak_reset_percent: float,
            trailing_sl: float):
        
        self.name = name
        self.trade_price_type = trade_price_type
        self.init_bal = init_bal
        self.init_trade_size = init_trade_size
        self.grid_pips = grid_pips
        self.sizing_ratio = init_trade_size / init_bal
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
        self.martingale_factor = martingale_factor
        # self.martingale_factor2 = martingale_factor2
        # self.factor_reset = factor_reset
        self.pyramiding = pyramiding
        self.streak_reset = streak_reset
        self.streak_reset_percent = streak_reset_percent
        self.trailing_sl = trailing_sl

        if trade_price_type == 'mid':
            self.BP, self.SP = 'mid_c', 'mid_c'
        elif trade_price_type == 'bidask':
            self.BP, self.SP = 'ask_c', 'bid_c'

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
            unrealised_pnl=float,
            realised_pnl=float,
            ac_bal=float,
            net_bal=float,
            margin_used=float,
            cash_bal=float,
            gross_bal=float
        )

        self.d.prepare_fast_data(name=name, start=0, end=self.d.datalen, add_cols=add_cols)

    def cum_long_position(self):
        open_longs = self.get_open_longs()
        cum_long_position = 0
        for _, trade in open_longs.items():
            cum_long_position = cum_long_position + trade[self.SIZE]
        return cum_long_position

    def cum_short_position(self):
        open_shorts = self.get_open_shorts()
        cum_short_position = 0
        for _, trade in open_shorts.items():
            cum_short_position = cum_short_position + trade[self.SIZE]
        return cum_short_position

    def unrealised_pnl(self):
        open_longs = self.get_open_longs()
        open_shorts = self.get_open_shorts()
        pnl = 0
        for _, trade in open_longs.items():
            pnl = pnl + trade[self.SIZE] * (self.d.fdata('mid_c', self.i) - trade[self.ENTRY])
        for _, trade in open_shorts.items():
            pnl = pnl + trade[self.SIZE] * (trade[self.ENTRY] - self.d.fdata('mid_c', self.i))
        return round(pnl, 2)
    
    def realised_pnl(self):
        closed_longs, closed_shorts = self.get_closed_longs(), self.get_closed_shorts()
        pnl = 0
        for _, trade in closed_longs.items():
            pnl = pnl + trade[self.SIZE] * (trade[self.EXIT] - trade[self.ENTRY])
        for _, trade in closed_shorts.items():
            pnl = pnl + trade[self.SIZE] * (trade[self.ENTRY] - trade[self.EXIT])
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
        else:
            self.d.update_fdata('cum_long_position', self.i, self.cum_long_position())
            self.d.update_fdata('cum_short_position', self.i, self.cum_short_position())
        
        self.d.update_fdata('unrealised_pnl', self.i, self.unrealised_pnl())
        self.d.update_fdata('realised_pnl', self.i, self.realised_pnl())

    def update_ac_values(self):
        self.d.update_fdata('cum_long_position', self.i, self.cum_long_position())
        self.d.update_fdata('cum_short_position', self.i, self.cum_short_position())
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
    
    # def uncovered_pip_position(self):
    #     uncovered_pip_position = 0 

    #     # sl_event = self.EVENT_SL in self.d.fdata('events', self.i) or self.EVENT_MC in self.d.fdata('events', self.i)
    #     if self.EVENT_SL in self.d.fdata('events', self.i):
    #         if not isnan(self.d.fdata('closed_longs', self.i)):
    #             closed_longs = self.d.fdata('closed_longs', self.i).copy()
    #             stopped_trade = closed_longs[next(iter(closed_longs))]
    #         elif not isnan(self.d.fdata('closed_shorts', self.i)):
    #             closed_shorts = self.d.fdata('closed_shorts', self.i).copy()
    #             stopped_trade = closed_longs[next(iter(closed_shorts))]
    #         uncovered_pip_position = round(-stopped_trade[self.SIZE] * stopped_trade[self.PIPS], 2) # subtraction because of negative sign of stopped trade pips

    #     return uncovered_pip_position
    
    def martingale_trade_size(self):
        events = self.d.fdata('events', self.i).copy() if type(self.d.fdata('events', self.i)) == list else list()
        closed_longs, closed_shorts = self.get_closed_longs(), self.get_closed_shorts()
        if self.EVENT_SL in events:
            if bool(closed_longs):
                stopped_trade = closed_longs[next(iter(closed_longs))]
            elif bool(closed_shorts):
                stopped_trade = closed_shorts[next(iter(closed_shorts))]
            return stopped_trade[self.SIZE] * self.martingale_factor
    
    def streak_counter(self):
        # if self.EVENT_TP in self.d.fdata('events', self.i) or self.EVENT_MC in self.d.fdata('events', self.i):

        if self.entry_type == self.EVENT_BASE_ENTRY:
            self.streak_count = 1

        events = self.d.fdata('events', self.i).copy() if type(self.d.fdata('events', self.i)) == list else list()
        if self.EVENT_SL in events:
            if self.streak_count == self.streak_reset:
                self.streak_count = 1
                self.entry_type = self.EVENT_BASE_ENTRY
            else:
                self.streak_count = self.streak_count + 1
        elif self.EVENT_MC in events:
            self.streak_count = 1
    
    def trade_size(self):
        #         if not isnan(self.d.fdata('closed_longs', self.i)):
        #             closed_long = self.d.fdata('closed_longs', self.i)
        #             streak_counter = closed_long[next(iter(closed_long))][self.STREAK_CTR]
        #         elif not isnan(self.d.fdata('closed_shorts', self.i)):
        #             closed_short = self.d.fdata('closed_shorts', self.i)
        #             streak_counter = closed_short[next(iter(closed_short))][self.STREAK_CTR]

        if self.i == 0:
            self.streak_counter()
            trade_size = self.init_trade_size
            self.pyr_trade_size = max(1, int(trade_size / 3))
        else:
            self.streak_counter()
            
            if self.entry_type == self.EVENT_BASE_ENTRY:
                net_bal, _ = self.current_ac_values()
                trade_size = int(net_bal * self.sizing_ratio) + 1 if self.sizing == 'dynamic' else self.init_trade_size
                self.pyr_trade_size = max(1, int(trade_size / 3))
            elif self.entry_type == self.EVENT_CONTRA_ENTRY:
                trade_size = self.martingale_trade_size()
                self.pyr_trade_size = max(1, int(trade_size / 3))
            elif self.entry_type == self.EVENT_PYR_ENTRY:
                trade_size = self.pyr_trade_size
        return trade_size
    
    # def dynamic_trade_size(self):
    #     net_bal, _ = self.current_ac_values()
    #     return int(net_bal * self.sizing_ratio)   
    
    def update_events(self, event):
        events = self.d.fdata('events', self.i).copy() if type(self.d.fdata('events', self.i)) == list else list()
        events.append(event)
        self.d.update_fdata('events', self.i, events)

    def close_long(self, trade_no: int):
        # Remove from open longs
        open_longs = self.get_open_longs()
        closing_long = open_longs[trade_no]
        del open_longs[trade_no]
        self.d.update_fdata('open_longs', self.i, open_longs)

        # Append to closed longs
        pips = (self.d.fdata('ask_c',  self.i) - closing_long[self.ENTRY]) * pow(10, -self.d.ticker['pipLocation'])
        closed_longs = self.get_closed_longs()
        closed_longs[trade_no] = (closing_long[self.STREAK_CNT], closing_long[self.SIZE], closing_long[self.ENTRY], self.d.fdata('bid_c',  self.i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)

        self.d.update_fdata('closed_longs', self.i, closed_longs)

    def close_short(self, trade_no: int):
        # Remove from open shorts
        open_shorts = self.d.fdata('open_shorts',  self.i).copy()
        closing_short = open_shorts[trade_no]
        del open_shorts[trade_no]
        self.d.update_fdata('open_shorts', self.i, open_shorts)

        # Append to closed shorts
        pips = (closing_short[self.ENTRY] - self.d.fdata('bid_c',  self.i)) * pow(10, -self.d.ticker['pipLocation'])
        closed_shorts = self.get_closed_shorts()
        closed_shorts[trade_no] = (closing_short[self.STREAK_CNT], closing_short[self.SIZE], closing_short[self.ENTRY], self.d.fdata('ask_c',  self.i), round(pips, 1)) # (SIZE, ENTRY, EXIT, PIPS)

        self.d.update_fdata('closed_shorts', self.i, closed_shorts)

    def get_open_longs(self):
        return self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
    
    def get_open_shorts(self):
        return self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
    
    def get_closed_longs(self):
        return self.d.fdata('closed_longs', self.i).copy() if type(self.d.fdata('closed_longs', self.i)) == dict else dict()
    
    def get_closed_shorts(self):
        return self.d.fdata('closed_shorts', self.i).copy() if type(self.d.fdata('closed_shorts', self.i)) == dict else dict()

    def trade_direction(self):
        if self.i == 0: # Random entry on first bar
            return choice([self.LONG, self.SHORT]), self.EVENT_BASE_ENTRY
        events = self.d.fdata('events', self.i).copy() if type(self.d.fdata('events', self.i)) == list else list()
        
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()
        closed_longs, closed_shorts = self.get_closed_longs(), self.get_closed_shorts()

        # Same direction if trailing SL adjusted
        if self.pyramiding:
            if self.EVENT_ADJUST in events: 
                if bool(open_longs):
                    return self.LONG, self.EVENT_PYR_ENTRY
                elif bool(open_shorts):
                    return self.SHORT, self.EVENT_PYR_ENTRY
                
        # No newtrades if there are open trades if pyramiding is False
        if bool(open_longs) and bool(open_shorts): 
            return None, None
        
        if self.EVENT_TP in events: # Same direction if TP
            if bool(closed_longs):
                self.base_trade = None
                return self.LONG, self.EVENT_BASE_ENTRY
            elif bool(closed_shorts):
                self.base_trade = None
                return self.SHORT, self.EVENT_BASE_ENTRY     
        elif self.EVENT_SL in events: # Opposite direction if SL
            if bool(closed_longs):
                return self.SHORT, self.EVENT_CONTRA_ENTRY
            elif bool(closed_shorts):
                return self.LONG, self.EVENT_CONTRA_ENTRY
        elif self.EVENT_MC in events: # Opposite direction if MC
            if bool(closed_longs):
                self.base_trade = None
                return self.SHORT, self.EVENT_BASE_ENTRY
            elif bool(closed_shorts):
                self.base_trade = None
                return self.LONG, self.EVENT_BASE_ENTRY
        else:
            return None, None
    
    def entry(self):
        self.direction, self.entry_type = self.trade_direction()
        if self.direction is None: # No new trade
            return
            
        if self.direction == self.LONG:
            entry = self.d.fdata('ask_c', self.i)
            tp = round(self.d.fdata('ask_c', self.i) + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            sl = round(self.d.fdata('ask_c', self.i) - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            self.next_up_grid, self.next_down_grid = tp, sl
        elif self.direction == self.SHORT:
            entry = self.d.fdata('bid_c', self.i)
            tp = round(self.d.fdata('bid_c', self.i) - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            sl = round(self.d.fdata('bid_c', self.i) + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            self.next_up_grid, self.next_down_grid = sl, tp      

        trade_size = self.trade_size()
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()
        
        if trade_size > 0:
            self.trade_no = self.trade_no + 1     
            if self.direction == self.LONG:
                if self.entry_type == self.EVENT_PYR_ENTRY:
                    base_trade = open_longs[self.base_trade_no]
                    tp = base_trade[self.TP]
                    sl = base_trade[self.SL]
                    tsl = base_trade[self.TSL]
                else:
                    tsl = 0
                open_longs[self.trade_no] = (self.streak_count, trade_size, entry, tp, sl, tsl) # (STREAK_CNT, SIZE, ENTRY, TP, SL, TSL) 
                self.d.update_fdata('open_longs', self.i, open_longs)
            elif self.direction == self.SHORT:
                if self.entry_type == self.EVENT_PYR_ENTRY:
                    base_trade = open_shorts[self.base_trade_no]
                    tp = base_trade[self.TP]
                    sl = base_trade[self.SL]
                    tsl = base_trade[self.TSL]
                else:
                    tsl = 0
                open_shorts[self.trade_no] = (self.streak_count, trade_size, entry, tp, sl, tsl) # (STREAK_CNT, SIZE, ENTRY, TP, SL, TSL) 
                self.d.update_fdata('open_shorts', self.i, open_shorts)
            
            self.base_trade_no = self.trade_no

            self.update_temp_ac_values()
            self.update_events(self.entry_type)
        pass

    def take_profit(self):     
        traded = False
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()

        # Close long positions take profit
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) >= trade[self.TP]:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        for trade_no, trade in open_shorts.items():
            if self.d.fdata(self.BP, self.i) <= trade[self.TP]:
                self.close_short(trade_no)
                traded = True

        if traded:
            # self.new_streak = True
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)
     
    def update_trailing_sl(self):
        adjusted = False
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()

        def split_trade(trade):
            close_trade_size = int(trade[self.SIZE] / 2) + 1
            keep_trade_size = trade[self.SIZE] - close_trade_size
            keep_trade = (trade[self.STREAK_CNT], keep_trade_size, trade[self.ENTRY], next_tp, trade[self.SL], tsl)
            closing_trade = (trade[self.STREAK_CNT], close_trade_size, trade[self.ENTRY], trade[self.TP], trade[self.SL], tsl)
            return keep_trade, closing_trade

        # Update long positions, update TSL
        closing_trade = None
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) >= trade[self.TP]:
                next_tp = round(trade[self.TP] + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade[self.ENTRY] + (trade[self.TP] - trade[self.ENTRY]) / 2, 5) if trade[self.TSL] == 0 else trade[self.TP]               
                # Split base trade to square off 50% and keep open 50%
                if trade_no == self.base_trade_no:
                    keep_trade, closing_trade = split_trade(trade)
                    open_longs[trade_no] = keep_trade
                    self.update_events(self.EVENT_SPLIT)
                else:
                    open_longs[trade_no] = (trade[self.STREAK_CNT], trade[self.SIZE], trade[self.ENTRY], next_tp, trade[self.SL], tsl)
                self.d.update_fdata('open_longs', self.i, open_longs)
                adjusted = True

        if closing_trade is not None:
            open_longs[self.base_trade_no + 0.1] = closing_trade
            self.d.update_fdata('open_longs', self.i, open_longs)

        # Update short positions, update TSL
        closing_trade = None
        for trade_no, trade in open_shorts.items():
            if self.d.fdata(self.BP, self.i) <= trade[self.TP]:
                next_tp = round(trade[self.TP] - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade[self.ENTRY] - (trade[self.ENTRY] - trade[self.TP]) / 2, 5) if trade[self.TSL] == 0 else trade[self.TP]
                # Split base trade to square off 50% and keep open 50%
                if trade_no == self.base_trade_no:
                    keep_trade, closing_trade = split_trade(trade)
                    open_shorts[trade_no] = keep_trade
                    self.update_events(self.EVENT_SPLIT)
                else:
                    open_shorts[trade_no] = (trade[self.STREAK_CNT], trade[self.SIZE], trade[self.ENTRY], next_tp, trade[self.SL], tsl)
                self.d.update_fdata('open_shorts', self.i, open_shorts)
                adjusted = True

        if closing_trade is not None:
            open_shorts[self.base_trade_no + 0.1] = closing_trade
            self.d.update_fdata('open_shorts', self.i, open_shorts)

        if adjusted:
            self.update_events(self.EVENT_ADJUST)  
    
    def take_profit_tsl(self):
        traded = False
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()

        # Close long positions take profit
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) <= trade[self.TSL] and trade[self.TSL] != 0:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        for trade_no, trade in open_shorts.items():
            if self.d.fdata(self.BP, self.i) >= trade[self.TSL] and trade[self.TSL] != 0:
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)
    
    def stop_loss(self):
        traded = False
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()

        # Close long positions stop loss
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) <= trade[self.SL]:
                self.close_long(trade_no)
                traded = True

        # Close short positions stop loss
        for trade_no, trade in open_shorts.items():
            if self.d.fdata(self.BP, self.i) >= trade[self.SL]:
                self.close_short(trade_no)
                traded = True

        if traded:
            # self.new_streak = False
            self.update_temp_ac_values()
            self.update_events(self.EVENT_SL)
    
    def margin_call(self):
        net_bal, margin_used = self.current_ac_values()
        traded = False
        open_longs, open_shorts = self.get_open_longs(), self.get_open_shorts()

        if net_bal < margin_used * self.MC_PERCENT:
            for trade_no, trade in open_longs.items():
                self.close_long(trade_no)
                traded = True

            for trade_no, trade in open_shorts.items():
                self.close_short(trade_no)
                traded = True

        if traded:
            # self.new_streak = True
            self.update_temp_ac_values()
            self.update_events(self.EVENT_MC)
    
    def update_init_values(self):
        self.trade_no = 0
        # self.new_streak = True
        # self.next_up_grid = self.d.fdata(self.BP, 0)
        # self.next_down_grid = self.d.fdata(self.SP, 0)
        if self.cash_out_factor is not None:
            self.d.update_fdata('cash_bal', self.i, 0)
    
    def run_sim(self):
        for i in tqdm(range(self.d.fdatalen), desc=" Simulating... "):
            self.i = i
            # self.calculate_values(init=True)
            if self.i == 0:
                self.update_init_values()
            else:
                self.update_temp_ac_values(init=True)
                if self.trailing_sl:
                    self.update_trailing_sl()
                self.margin_call()
                self.stop_loss()
                if self.trailing_sl:
                    self.take_profit()
                    self.take_profit_tsl()
                else:
                    self.take_profit()
                self.cash_transfer()
            self.entry()
            self.update_ac_values()
