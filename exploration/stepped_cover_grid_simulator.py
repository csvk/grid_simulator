from data import Data
from tqdm import tqdm
import pandas as pd
from numpy import isnan


class GridSimulator:

    EVENT_TP, EVENT_SL, EVENT_MC, EVENT_ENTRY, EVENT_COVER, EVENT_ADJUST = 'TP', 'SL', 'MC', 'ENT', 'COV', 'ADJ'
    EVENT_CASH_IN, EVENT_CASH_OUT =  'CI', 'CO'
    SIZE, ENTRY, TP, SL, COVERED, TSL = 0, 1, 2, 3, 4, 5
    EXIT, PIPS = 2, 3
    LONG, SHORT = 1, -1
    ORIG_TRADE, COVERED_TRADE = 0, 1
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
            stop_loss_type: str,
            margin_sl_percent: float,
            sizing: str,
            cash_out_factor: float,
            cover_stopped_loss: str,
            cover_sl_ratio: float,
            # martingale_sizing: bool,
            max_unrealised_pnl: float,
            trailing_sl: float):
        
        self.name = name
        self.init_bal = init_bal
        self.init_trade_size = init_trade_size
        self.tp_pips = grid_pips
        self.sl_pips = grid_pips * sl_grid_count
        self.sizing_ratio = init_trade_size / init_bal
        self.stop_loss_type = stop_loss_type
        self.margin_sl_percent = margin_sl_percent
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
        self.cover_stopped_loss = cover_stopped_loss
        self.cover_sl_ratio = cover_sl_ratio
        # self.martingale_sizing = martingale_sizing,
        self.max_unrealised_pnl = max_unrealised_pnl
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
            unrealised_pnl=float,
            realised_pnl=float,
            ac_bal=float,
            net_bal=float,
            margin_used=float,
            uncovered_pip_position=float,
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
            self.d.update_fdata('uncovered_pip_position', self.i, self.d.fdata('uncovered_pip_position', self.i-1))
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
    
    def trade_size(self):
        cov_trade_size = 0
        if self.i == 0:
            trade_size = self.init_trade_size
        else:
            net_bal, margin_used = self.current_ac_values()
            calc_trade_size = int(net_bal * self.sizing_ratio) + 1 if self.sizing == 'dynamic' else self.init_trade_size
            uncovered_pip_position = 0 if isnan(self.d.fdata('uncovered_pip_position', self.i)) \
                else self.d.fdata('uncovered_pip_position', self.i)
            if self.cover_stopped_loss is not None and uncovered_pip_position > 0:
                sl_cover_trade_size = uncovered_pip_position / self.tp_pips * self.cover_sl_ratio
                required_trade_size = max(calc_trade_size, sl_cover_trade_size)
                allowed_trade_size = max(0, (net_bal / self.margin_sl_percent - margin_used) / (2 * float(self.d.ticker['marginRate'])))
                trade_size = int(min(required_trade_size, allowed_trade_size)) + 1
            else:
                trade_size = calc_trade_size
        return trade_size, cov_trade_size
    
    def trade_size(self):
        cov_trade_size = 0
        if self.i == 0:
            trade_size = self.init_trade_size
        else:
            net_bal, margin_used = self.current_ac_values()
            trade_size = int(net_bal * self.sizing_ratio) if self.sizing == 'dynamic' else self.init_trade_size
            uncovered_pip_position = 0 if isnan(self.d.fdata('uncovered_pip_position', self.i)) \
                else self.d.fdata('uncovered_pip_position', self.i)
            if self.cover_stopped_loss is not None and uncovered_pip_position > 0:
                sl_cover_trade_size = uncovered_pip_position / self.tp_pips * self.cover_sl_ratio
                required_trade_size = max(trade_size, sl_cover_trade_size)
                if self.cover_stopped_loss == '2-way':
                    allowed_trade_size = max(0, (net_bal / self.margin_sl_percent - margin_used) / (2 * float(self.d.ticker['marginRate'])))
                elif self.cover_stopped_loss == '1-way':
                    allowed_trade_size = max(0, (net_bal / self.margin_sl_percent - margin_used) / float(self.d.ticker['marginRate']) - trade_size)
                cov_trade_size = int(min(required_trade_size, allowed_trade_size))
            # else:
            #     trade_size = calc_trade_size
        return trade_size, cov_trade_size
    
    # def dynamic_trade_size(self):
    #     net_bal, _ = self.current_ac_values()
    #     return int(net_bal * self.sizing_ratio)   
    
    def update_events(self, event):
        events = self.d.fdata('events', self.i).copy() if type(self.d.fdata('events', self.i)) == list else list()
        if event not in events:
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

    def update_uncovered_pip_position(self, trade_no, event: int):
        uncovered_pip_position = 0 if isnan(self.d.fdata('uncovered_pip_position', self.i)) \
            else self.d.fdata('uncovered_pip_position', self.i)
        # if uncovered_pip_position == 0 and event == self.EVENT_COVER:
        #     return
        if event == self.EVENT_SL or event == self.EVENT_MC: # Add on stop loss
            if type(self.d.fdata('closed_longs', self.i)) == dict and \
                trade_no in self.d.fdata('closed_longs', self.i):
                stopped_trade = self.d.fdata('closed_longs', self.i)[trade_no]
            else:
                stopped_trade = self.d.fdata('closed_shorts', self.i)[trade_no]
            # self.sl_pip_position = self.sl_pip_position - stopped_trade[self.SIZE] * stopped_trade[self.PIPS]
            if stopped_trade[self.PIPS] < 0 and stopped_trade[self.COVERED] == self.COVERED_TRADE:
                self.d.update_fdata('uncovered_pip_position', self.i, 
                                    round(uncovered_pip_position - 
                                          stopped_trade[self.SIZE] * stopped_trade[self.PIPS], 2)) # subtraction because of negative sign of stopped trade pips
        elif event == self.EVENT_COVER: # Reduce on entry
            if self.cover_stopped_loss == '2-way':
                covered_pip_position = self.d.fdata('open_longs', self.i)[trade_no][self.SIZE] * self.tp_pips * 2
            elif self.cover_stopped_loss == '1-way':
                if self.cover_sl_direction == self.LONG:
                    covered_pip_position = self.d.fdata('open_longs', self.i)[trade_no][self.SIZE] * self.tp_pips
                elif self.cover_sl_direction == self.SHORT:
                    covered_pip_position = self.d.fdata('open_shorts', self.i)[trade_no][self.SIZE] * self.tp_pips
            uncovered_pip_position = max(0, uncovered_pip_position - covered_pip_position)
            self.d.update_fdata('uncovered_pip_position', self.i, round(uncovered_pip_position, 2) if uncovered_pip_position > 0 else None)

    def entry(self):
        next_grid = self.d.fdata('mid_c', self.i) >= self.next_up_grid or self.d.fdata('mid_c', self.i) <= self.next_down_grid
        if next_grid or self.d.fdata('uncovered_pip_position', self.i) > 0:
            long_tp = round(self.d.fdata('mid_c', self.i) + self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
            short_tp = round(self.d.fdata('mid_c', self.i) - self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)

            if next_grid:
                self.next_up_grid = long_tp
                self.next_down_grid = short_tp

            # long_ssl = round(self.d.fdata('mid_c', self.i) - self.sl_pips / 2 * pow(10, self.d.ticker['pipLocation']), 5)
            # short_ssl = round(self.d.fdata('mid_c', self.i) + self.sl_pips / 2 * pow(10, self.d.ticker['pipLocation']), 5)

            # if self.i == 0:
            #     trade_size = self.init_trade_size
            # else:
            #     trade_size = self.dynamic_trade_size() if self.sizing == 'dynamic' else self.init_trade_size

            trade_size, cov_trade_size = self.trade_size()
            open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
            open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
            
            # required_margin = round(trade_size * float(self.d.ticker['marginRate']) * 2, 2)
            # net_bal, margin_used = self.current_ac_values()
            # if self.i == 0 or (self.i > 0 and net_bal >= (required_margin + margin_used) * self.MC_PERCENT):
            if trade_size > 0:
                self.trade_no = self.trade_no + 1
                # if self.stop_loss_type == 'grid_count_max_unrealised_pnl':
                #     open_longs[self.trade_no] = (trade_size, self.d.fdata('ask_c', self.i), self.next_up_grid, long_sl, long_ssl) # (SIZE, ENTRY, TP, SL, SSL)
                #     open_shorts[self.trade_no] = (trade_size, self.d.fdata('bid_c', self.i), self.next_down_grid, short_sl, short_ssl) # (SIZE, ENTRY, TP, SL,SSL)
                # else:
                covered_long, covered_short = self.ORIG_TRADE, self.ORIG_TRADE
                long_sl = round(self.d.fdata('mid_c', self.i) - self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                short_sl = round(self.d.fdata('mid_c', self.i) + self.sl_pips * pow(10, self.d.ticker['pipLocation']), 5)
                if self.cover_stopped_loss is None or cov_trade_size == 0:
                    long_size, short_size = trade_size, trade_size
                elif self.cover_stopped_loss == '2-way':
                    long_size, short_size = cov_trade_size, cov_trade_size
                    covered_long, covered_short = self.COVERED_TRADE, self.COVERED_TRADE
                    long_sl = round(self.d.fdata('mid_c', self.i) - self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    short_sl = round(self.d.fdata('mid_c', self.i) + self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                elif self.cover_stopped_loss == '1-way':
                    if self.cover_sl_direction == self.LONG:
                        long_size, short_size = cov_trade_size, trade_size
                        covered_long = self.COVERED_TRADE
                        long_sl = round(self.d.fdata('mid_c', self.i) - self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                    elif self.cover_sl_direction == self.SHORT:
                        long_size, short_size = trade_size, cov_trade_size
                        covered_short = self.COVERED_TRADE
                        short_sl = round(self.d.fdata('mid_c', self.i) + self.tp_pips * pow(10,     self.d.ticker['pipLocation']), 5)
                
                open_longs[self.trade_no] = (long_size, self.d.fdata('ask_c', self.i), long_tp, long_sl, covered_long, 0) # (SIZE, ENTRY, TP, SL, COVERED, TSL)
                open_shorts[self.trade_no] = (short_size, self.d.fdata('bid_c', self.i), short_tp, short_sl, covered_short, 0) # (SIZE, ENTRY, TP, SL, COVERED, TSL)
                self.d.update_fdata('open_longs', self.i, open_longs)
                self.d.update_fdata('open_shorts', self.i, open_shorts)
                
                self.update_temp_ac_values()
                # self.update_events(self.EVENT_ENTRY)
                if self.cover_stopped_loss is not None and cov_trade_size > 0:
                    self.update_events(self.EVENT_COVER)
                    self.update_uncovered_pip_position(self.trade_no, self.EVENT_COVER)
                else:
                    self.update_events(self.EVENT_ENTRY)
                # self.update_ac_values()

    def take_profit(self):     
        traded = False
        # Close long positions take profit
        open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade[self.TP]:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade[self.TP]:
                self.close_short(trade_no)
                traded = True

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_TP)
            # self.update_ac_values()    

    def stop_loss_grid_count(self):
        traded = False
        # Close long positions stop loss
        open_longs = self.d.fdata('open_longs', self.i).copy()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) <= trade[self.SL]:
                self.close_long(trade_no)
                if self.cover_stopped_loss is not None:
                    self.cover_sl_direction = self.SHORT
                    self.update_uncovered_pip_position(trade_no, self.EVENT_SL)
                traded = True

        # Close short positions stop loss
        open_shorts = self.d.fdata('open_shorts', self.i).copy()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) >= trade[self.SL]:
                self.close_short(trade_no)
                if self.cover_stopped_loss is not None:
                    self.cover_sl_direction = self.LONG
                    self.update_uncovered_pip_position(trade_no, self.EVENT_SL)
                traded = True

        return traded

    def stop_loss_grid_count_on_margin(self, net_bal: float, margin_used: float):
        traded = False
        if net_bal < margin_used * self.margin_sl_percent:
            traded = self.stop_loss_grid_count()
        return traded

    def stop_loss_oldest_on_margin(self, net_bal: float, margin_used: float):
        traded = False
        if net_bal < margin_used * self.margin_sl_percent:
            longs = list(self.d.fdata('open_longs', self.i).keys())
            shorts = list(self.d.fdata('open_shorts', self.i).keys())
            oldest_long = longs[0] if len(longs) > 0 else None
            oldest_short = shorts[0] if len(shorts) > 0 else None
            if oldest_long == None and oldest_short == None:
                pass
            else:
                if oldest_long == None:
                    self.close_short(oldest_short)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.LONG
                        self.update_uncovered_pip_position(oldest_short, self.EVENT_SL)
                elif oldest_short == None:
                    self.close_long(oldest_long)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.SHORT
                        self.update_uncovered_pip_position(oldest_long, self.EVENT_SL)
                else:
                    if oldest_long <= oldest_short:
                        self.close_long(oldest_long)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.SHORT
                            self.update_uncovered_pip_position(oldest_long, self.EVENT_SL)
                    else:
                        self.close_short(oldest_short)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.LONG
                            self.update_uncovered_pip_position(oldest_short, self.EVENT_SL)
                traded = True
        return traded

    def stop_loss_farthest_on_margin(self, net_bal: float, margin_used: float):
        traded = False
        price = self.d.fdata('mid_c', self.i)
        if net_bal < margin_used * self.margin_sl_percent:
            farthest_long_price, farthest_short_price = price, price
            farthest_long, farthest_short = None, None
            for long, trade in self.d.fdata('open_longs', self.i).items():
                if trade[self.ENTRY] > farthest_long_price:
                    farthest_long_price = trade[self.ENTRY]
                    farthest_long = long
            for short, trade in self.d.fdata('open_shorts', self.i).items():
                if trade[self.ENTRY] < farthest_short_price:
                    farthest_short_price = trade[self.ENTRY]
                    farthest_short = short
            if farthest_long == None and farthest_short == None:
                pass
            else:
                if farthest_long == None:
                    self.close_short(farthest_short)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.LONG
                        self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                elif farthest_short == None:
                    self.close_long(farthest_long)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.SHORT
                        self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                else:
                    if farthest_long_price - price > price - farthest_short_price:
                        self.close_long(farthest_long)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.SHORT
                            self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                    else:
                        self.close_short(farthest_short)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.LONG
                            self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                traded = True
        return traded
    
    def stop_loss_max_unrealised_pnl(self, net_bal):
        traded = False
        price = self.d.fdata('mid_c', self.i)
        while net_bal * self.max_unrealised_pnl < -self.d.fdata('unrealised_pnl', self.i):
            farthest_long_price, farthest_short_price = price, price
            farthest_long, farthest_short = None, None
            for long, trade in self.d.fdata('open_longs', self.i).items():
                if trade[self.ENTRY] > farthest_long_price:
                    farthest_long_price = trade[self.ENTRY]
                    farthest_long = long
            for short, trade in self.d.fdata('open_shorts', self.i).items():
                if trade[self.ENTRY] < farthest_short_price:
                    farthest_short_price = trade[self.ENTRY]
                    farthest_short = short
            if farthest_long == None and farthest_short == None:
                pass
            else:
                if farthest_long == None:
                    self.close_short(farthest_short)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.LONG
                        self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                elif farthest_short == None:
                    self.close_long(farthest_long)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.SHORT
                        self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                else:
                    if farthest_long_price - price > price - farthest_short_price:
                        self.close_long(farthest_long)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.SHORT
                            self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                    else:
                        self.close_short(farthest_short)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.LONG
                            self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                self.update_temp_ac_values()
                net_bal, _ = self.current_ac_values()
                traded = True

        return traded
    
    def stop_loss_max_unrealised_pnl_farthest(self, net_bal):
        traded = False
        price = self.d.fdata('mid_c', self.i)
        if net_bal * self.max_unrealised_pnl < -self.d.fdata('unrealised_pnl', self.i):
            farthest_long_price, farthest_short_price = price, price
            farthest_long, farthest_short = None, None
            for long, trade in self.d.fdata('open_longs', self.i).items():
                if trade[self.ENTRY] > farthest_long_price:
                    farthest_long_price = trade[self.ENTRY]
                    farthest_long = long
            for short, trade in self.d.fdata('open_shorts', self.i).items():
                if trade[self.ENTRY] < farthest_short_price:
                    farthest_short_price = trade[self.ENTRY]
                    farthest_short = short
            if farthest_long == None and farthest_short == None:
                pass
            else:
                if farthest_long == None:
                    self.close_short(farthest_short)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.LONG
                        self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                elif farthest_short == None:
                    self.close_long(farthest_long)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.SHORT
                        self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                else:
                    if farthest_long_price - price > price - farthest_short_price:
                        self.close_long(farthest_long)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.LONG
                            self.update_uncovered_pip_position(farthest_long, self.EVENT_SL)
                    else:
                        self.close_short(farthest_short)
                        if self.cover_stopped_loss is not None:
                            self.cover_sl_direction = self.SHORT
                            self.update_uncovered_pip_position(farthest_short, self.EVENT_SL)
                traded = True

        return traded
    
    def stop_loss_grid_count_max_unrealised_pnl(self, net_bal):
        # traded = self.stop_loss_grid_count()

        traded = False
        if net_bal * self.max_unrealised_pnl < -self.d.fdata('unrealised_pnl', self.i):
            # Close long positions stop loss
            open_longs = self.d.fdata('open_longs', self.i).copy()
            for trade_no, trade in open_longs.items():
                if self.d.fdata('mid_c', self.i) <= trade[self.SL]:
                    self.close_long(trade_no)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.SHORT
                        self.update_uncovered_pip_position(trade_no, self.EVENT_SL)
                    traded = True

            # Close short positions stop loss
            open_shorts = self.d.fdata('open_shorts', self.i).copy()
            for trade_no, trade in open_shorts.items():
                if self.d.fdata('mid_c', self.i) >= trade[self.SL]:
                    self.close_short(trade_no)
                    if self.cover_stopped_loss is not None:
                        self.cover_sl_direction = self.LONG
                        self.update_uncovered_pip_position(trade_no, self.EVENT_SL)
                    traded = True

        return traded
    
    def stop_loss(self):
        net_bal, margin_used = self.current_ac_values()
        traded = False
        if self.stop_loss_type == 'grid_count':
            traded = self.stop_loss_grid_count()
        elif self.stop_loss_type == 'grid_count_on_margin':
            traded = self.stop_loss_grid_count_on_margin(net_bal, margin_used)
        elif self.stop_loss_type == 'oldest_on_margin':
            traded = self.stop_loss_oldest_on_margin(net_bal, margin_used)
        elif self.stop_loss_type == 'farthest_on_margin':
            traded = self.stop_loss_farthest_on_margin(net_bal, margin_used)
        elif self.stop_loss_type == 'max_unrealised_pnl':
            traded = self.stop_loss_max_unrealised_pnl(net_bal)
        elif self.stop_loss_type == 'max_unrealised_pnl_farthest':
            traded = self.stop_loss_max_unrealised_pnl_farthest(net_bal)
        elif self.stop_loss_type == 'grid_count_max_unrealised_pnl':
            traded = self.stop_loss_grid_count_max_unrealised_pnl(net_bal)

        if traded:
            self.update_temp_ac_values()
            self.update_events(self.EVENT_SL)
            # self.update_ac_values()

    def cum_sl_pips(self):
        closed_longs = self.d.fdata('closed_longs', self.i).copy()
        cum_sl_longs = 0
        for trade_no, trade in closed_longs.items():
            if trade[self.PIPS] < 0:
                cum_sl_longs = cum_sl_longs + trade[self.PIPS]
        closed_shorts = self.d.fdata('closed_shorts', self.i).copy()
        cum_sl_shorts = 0
        for trade_no, trade in closed_shorts.items():
            if trade[self.PIPS] < 0:
                cum_sl_shorts = cum_sl_shorts + trade[self.PIPS]
        return cum_sl_longs, cum_sl_shorts
    
    def margin_call(self):
        net_bal, margin_used = self.current_ac_values()
        # cum_position = self.d.fdata('cum_long_position', self.i) + self.d.fdata('cum_short_position', self.i)
        traded = False
        if net_bal < margin_used * self.MC_PERCENT:
            open_longs = self.d.fdata('open_longs', self.i).copy()
            for trade_no, trade in open_longs.items():
                self.close_long(trade_no)
                if self.cover_stopped_loss is not None:
                    self.update_uncovered_pip_position(trade_no, self.EVENT_MC)
                traded = True

            open_shorts = self.d.fdata('open_shorts', self.i).copy()
            for trade_no, trade in open_shorts.items():
                self.close_short(trade_no)
                if self.cover_stopped_loss is not None:
                    self.update_uncovered_pip_position(trade_no, self.EVENT_MC)
                traded = True

        if traded:
            if self.cover_stopped_loss is not None:
                if len(open_longs) > len(open_shorts):
                    self.cover_sl_direction = self.SHORT
                elif len(open_longs) < len(open_shorts):
                    self.cover_sl_direction = self.LONG
                else:
                    cum_sl_longs, cum_sl_shorts = self.cum_sl_pips()
                    self.cover_sl_direction = self.LONG if cum_sl_shorts < cum_sl_longs else self.SHORT

            self.update_temp_ac_values()
            self.update_events(self.EVENT_MC)
            # self.update_ac_values()

    def update_trailing_sl(self):
        adjusted = False
        # Update long positions, update TSL
        open_longs = self.d.fdata('open_longs', self.i).copy() if type(self.d.fdata('open_longs', self.i)) == dict else dict()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) >= trade[self.TP]:
                next_tp = round(trade[self.TP] + self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade[self.ENTRY] + (trade[self.TP] - trade[self.ENTRY]) / 2, 5) if trade[self.TSL] == 0 else trade[self.TP]               
                open_longs[trade_no] = (trade[self.SIZE], trade[self.ENTRY], next_tp, trade[self.SL], trade[self.COVERED], tsl)
                self.d.update_fdata('open_longs', self.i, open_longs)
                adjusted = True

        # Update short positions, update TSL
        open_shorts = self.d.fdata('open_shorts', self.i).copy() if type(self.d.fdata('open_shorts', self.i)) == dict else dict()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) <= trade[self.TP]:
                next_tp = round(trade[self.TP] - self.tp_pips * pow(10, self.d.ticker['pipLocation']), 5)
                tsl = round(trade[self.ENTRY] - (trade[self.ENTRY] - trade[self.TP]) / 2, 5) if trade[self.TSL] == 0 else trade[self.TP]
                open_shorts[trade_no] = (trade[self.SIZE], trade[self.ENTRY], next_tp, trade[self.SL], trade[self.COVERED], tsl)
                self.d.update_fdata('open_shorts', self.i, open_shorts)
                adjusted = True

        if adjusted:
            self.update_events(self.EVENT_ADJUST)  

    def take_profit_tsl(self):
        traded = False
        # Close long positions take profit
        open_longs = self.d.fdata('open_longs', self.i).copy()
        for trade_no, trade in open_longs.items():
            if self.d.fdata('mid_c', self.i) <= trade[self.TSL] and trade[self.TSL] != 0:
                self.close_long(trade_no)
                traded = True

        # Close short positions take profit
        open_shorts = self.d.fdata('open_shorts', self.i).copy()
        for trade_no, trade in open_shorts.items():
            if self.d.fdata('mid_c', self.i) >= trade[self.TSL] and trade[self.TSL] != 0:
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
        self.cover_sl_direction = None
    
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
                    self.take_profit_tsl()
                else:
                    self.take_profit()
                self.cash_transfer()
            self.entry()
            self.update_ac_values()
            # print(i, self.d.df[self.name].iloc[self.i])
            # print(self.d.print_row(self.i))

        # return self.d.df[self.name].copy()
