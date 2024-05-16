from data import Data
from tqdm import tqdm
import pandas as pd
from numpy import isnan
from random import choice


class GridSimulator:

    EVENT_TP, EVENT_SL, EVENT_MC, EVENT_ENTRY, EVENT_RESET = 'TP', 'SL', 'MC', 'ENT', 'RES'
    EVENT_CASH_IN, EVENT_CASH_OUT =  'CI', 'CO'
    STREAK_CTR, SIZE, ENTRY, TP, SL, TSL = 0, 1, 2, 3, 4, 5
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
        open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
        cum_long_position = 0
        for _, trade in open_longs.items():
            cum_long_position = cum_long_position + trade[self.SIZE]
        return cum_long_position

    def cum_short_position(self):
        open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
        cum_short_position = 0
        for _, trade in open_shorts.items():
            cum_short_position = cum_short_position + trade[self.SIZE]
        return cum_short_position

    def unrealised_pnl(self):
        open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
        open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
        pnl = 0
        for _, trade in open_longs.items():
            pnl = pnl + trade[self.SIZE] * (self.d.fdata('mid_c', self.i) - trade[self.ENTRY])
        for _, trade in open_shorts.items():
            pnl = pnl + trade[self.SIZE] * (trade[self.ENTRY] - self.d.fdata('mid_c', self.i))
        return round(pnl, 2)
    
    def realised_pnl(self):
        closed_longs = self.d.fdata('closed_longs', self.i).copy() if type(self.d.fdata('closed_longs', self.i)) == dict else dict()
        closed_shorts = self.d.fdata('closed_shorts', self.i).copy() if type(self.d.fdata('closed_shorts', self.i)) == dict else dict()
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
    
    def uncovered_pip_position(self):
        uncovered_pip_position = 0 

        # sl_event = self.EVENT_SL in self.d.fdata('events', self.i) or self.EVENT_MC in self.d.fdata('events', self.i)
        if self.EVENT_SL in self.d.fdata('events', self.i):
            if not isnan(self.d.fdata('closed_longs', self.i)):
                closed_longs = self.d.fdata('closed_longs', self.i).copy()
                stopped_trade = closed_longs[next(iter(closed_longs))]
            elif not isnan(self.d.fdata('closed_shorts', self.i)):
                closed_shorts = self.d.fdata('closed_shorts', self.i).copy()
                stopped_trade = closed_longs[next(iter(closed_shorts))]
            uncovered_pip_position = round(-stopped_trade[self.SIZE] * stopped_trade[self.PIPS], 2) # subtraction because of negative sign of stopped trade pips

        return uncovered_pip_position
    
    def streak_counter(self):
        # if self.EVENT_TP in self.d.fdata('events', self.i) or self.EVENT_MC in self.d.fdata('events', self.i):

        if self.i == 0:
            self.streak_count = 1
        if self.EVENT_SL in self.d.fdata('events', self.i):
            # if not isnan(self.d.fdata('closed_longs', self.i)):
            #     closed_long = self.d.fdata('closed_longs', self.i)
            #     streak_count = closed_long[next(iter(closed_long))][self.STREAK_CTR]
            # elif not isnan(self.d.fdata('closed_shorts', self.i)):
            #     closed_short = self.d.fdata('closed_shorts', self.i)
            #     streak_count = closed_short[next(iter(closed_short))][self.STREAK_CTR]

            if self.streak_count == self.streak_reset:
                self.streak_count = 1
            else:
                self.streak_count = self.streak_count + 1
        elif self.EVENT_MC in self.d.fdata('events', self.i):
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
        else:
            self.streak_counter()
            net_bal, margin_used = self.current_ac_values()
            calc_trade_size = int(net_bal * self.sizing_ratio) + 1 if self.sizing == 'dynamic' else self.init_trade_size
            uncovered_pip_position = self.uncovered_pip_position()
            if uncovered_pip_position > 0:
                if self.factor_reset is None:
                    martingale_factor = self.martingale_factor1
                else:
                    martingale_factor = self.martingale_factor1 if self.streak_count <= self.factor_reset else self.martingale_factor2
                martingale_trade_size = uncovered_pip_position / self.grid_pips * martingale_factor
                required_trade_size = max(calc_trade_size, martingale_trade_size)
                allowed_trade_size = max(0, (net_bal / self.streak_reset_percent - margin_used) / float(self.d.ticker['marginRate']))
                trade_size = int(min(required_trade_size, allowed_trade_size)) + 1
            else:
                trade_size = calc_trade_size
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
        open_longs = self.d.fdata('open_longs',  self.i).copy()
        closing_long = open_longs[trade_no]
        del open_longs[trade_no]
        self.d.update_fdata('open_longs', self.i, open_longs)

        # Append to closed longs
        pips = (self.d.fdata('ask_c',  self.i) - closing_long[self.ENTRY]) * pow(10, -self.d.ticker['pipLocation'])
        closed_longs = self.d.fdata('closed_longs',  self.i).copy() if type(self.d.fdata('closed_longs',  self.i)) == dict else dict()
        closed_longs[trade_no] = (closing_long[self.SIZE], closing_long[self.ENTRY], self.d.fdata('bid_c',  self.i), round(pips, 1), closing_long[self.COVERED]) # (SIZE, ENTRY, EXIT, PIPS, COVERED)

        self.d.update_fdata('closed_longs', self.i, closed_longs)

    def close_short(self, trade_no: int):
        # Remove from open shorts
        open_shorts = self.d.fdata('open_shorts',  self.i).copy()
        closing_short = open_shorts[trade_no]
        del open_shorts[trade_no]
        self.d.update_fdata('open_shorts', self.i, open_shorts)

        # Append to closed shorts
        pips = (closing_short[self.ENTRY] - self.d.fdata('bid_c',  self.i)) * pow(10, -self.d.ticker['pipLocation'])
        closed_shorts = self.d.fdata('closed_shorts',  self.i).copy() if type(self.d.fdata('closed_shorts',  self.i)) == dict else dict()
        closed_shorts[trade_no] = (closing_short[self.SIZE], closing_short[self.ENTRY], self.d.fdata('ask_c',  self.i), round(pips, 1), closing_short[self.COVERED]) # (SIZE, ENTRY, EXIT, PIPS, COVERED)

        self.d.update_fdata('closed_shorts', self.i, closed_shorts)

    def trade_direction(self):
        if self.trailing_sl:
            # check for pyramiding
            pass
        if self.i == 0: # Random entry on first bar
            return choice([self.LONG, self.SHORT])
        if isnan(self.d.fdata('closed_longs', self.i)) and isnan(self.d.fdata('closed_shorts', self.i)): # No trade if previous trade not closed
            return None
        if self.TP in self.fdata('events', self.i): # Same direction if TP
            if not isnan(self.d.fdata('closed_longs', self.i)):
                return self.LONG
            elif not isnan(self.d.fdata('closed_shorts', self.i)):
                return self.SHORT      
        elif self.SL in self.fdata('events', self.i) or self.MC in self.fdata('events', self.i): # Opposite direction if SL
            if not isnan(self.d.fdata('closed_longs', self.i)):
                return self.SHORT
            elif not isnan(self.d.fdata('closed_shorts', self.i)):
                return self.LONG    
    
    def entry(self):
        direction = self.trade_direction()
        if direction is None: # No new trade if previous trade not closed
            # check for pyramiding for trailing_sl
            return
            
        if direction == self.LONG:
            entry = self.d.fdata('ask_c', self.i)
            tp = round(self.d.fdata('ask_c', self.i) + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            sl = round(self.d.fdata('ask_c', self.i) - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            self.next_up_grid, self.next_down_grid = tp, sl
        elif direction == self.SHORT:
            entry = self.d.fdata('bid_c', self.i)
            tp = round(self.d.fdata('bid_c', self.i) - self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            sl = round(self.d.fdata('bid_c', self.i) + self.grid_pips * pow(10, self.d.ticker['pipLocation']), 5)
            self.next_up_grid, self.next_down_grid = sl, tp      

        trade_size = self.trade_size()
        
        if trade_size > 0:
            self.trade_no = self.trade_no + 1
            trade = dict()
            trade[self.trade_no] = [self.streak_count, trade_size, entry, tp, sl] # (STREAK_CTR, SIZE, ENTRY, TP, SL)            

            if direction == self.LONG:
                self.d.update_fdata('open_longs', self.i, trade)
            elif direction == self.SHORT:
                self.d.update_fdata('open_shorts', self.i, trade)
            
            self.update_temp_ac_values()
            self.update_events(self.EVENT_ENTRY)

    def take_profit(self):     
        traded = False
        # Close long positions take profit
        open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) >= trade[self.TP]:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata(self.BP, self.i) <= trade[self.TP]:
                self.close_short(trade_no)
                traded = True

        if traded:
            # self.new_streak = True
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)
    
    def stop_loss(self):
        traded = False
        # Close long positions stop loss
        open_longs = self.d.fdata('open_longs', self.i).copy()
        for trade_no, trade in open_longs.items():
            if self.d.fdata(self.SP, self.i) <= trade[self.SL]:
                self.close_long(trade_no)
                traded = True

        # Close short positions stop loss
        open_shorts = self.d.fdata('open_shorts', self.i).copy()
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
        if net_bal < margin_used * self.MC_PERCENT:
            open_longs = self.d.fdata('open_longs', self.i).copy()
            for trade_no, trade in open_longs.items():
                self.close_long(trade_no)
                traded = True

            open_shorts = self.d.fdata('open_shorts', self.i).copy()
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
                self.margin_call()
                self.stop_loss()
                if self.trailing_sl:
                    self.take_profit_tsl()
                else:
                    self.take_profit()
                self.cash_transfer()
            self.entry()
            self.update_ac_values()
