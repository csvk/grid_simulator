from grid_simulator import GridSimulator
from tabulate import tabulate
import pandas as pd

class GridOptimizer:

    def __init__(
            self,
            checkpoint: int,
            counter: int,
            start: int,
            end: int,
            records: list,
            tickers: list,
            frequency: list,
            init_bal: list,
            init_trade_size: list,
            grid_pips: list,
            sl_grid_count: list,
            stop_loss_type: list,
            margin_sl_percent: list,
            sizing: list,
            cash_out_factor: list,
            cover_stopped_loss: list,
            cover_sl_ratio: list,
            # martigale_sizing: list,
            max_unrealised_pnl:list,
            trailing_sl: list,
            data_path: str,
            instruments: str,
            out_path: str,
            inputs_file: str,
            dummyrun: bool):
        
        self.dummyrun = dummyrun
        self.checkpoint = checkpoint
        self.counter = counter
        self.start = start
        self.end = end
        self.records = records
        self.tickers = tickers
        self.frequency = frequency
        self.init_bal = init_bal
        self.init_trade_size = init_trade_size
        self.grid_pips = grid_pips
        self.sl_grid_count = sl_grid_count
        self.stop_loss_type = stop_loss_type
        self.margin_sl_percent = margin_sl_percent
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
        self.cover_stopped_loss = cover_stopped_loss
        self.cover_sl_ratio = cover_sl_ratio
        # self.martigale_sizing = martigale_sizing
        self.max_unrealised_pnl = max_unrealised_pnl
        self.trailing_sl= trailing_sl
        self.data_path = data_path
        self.instruments = instruments
        self.out_path = out_path
        self.inputs_file = inputs_file
        self.inputs_list = list()
    
    def __repr__(self) -> str:
        return str(
            dict(
                checkpoint = self.checkpoint,
                counter = self.counter,
                start = self.start,
                end = self.end,
                tickers = self.tickers,
                frequency = self.frequency,
                init_bal = self.init_bal,
                init_trade_size = self.init_trade_size,
                grid_pips = self.grid_pips,
                sl_grid_count = self.sl_grid_count,
                stop_loss_type = self.stop_loss_type,
                margin_sl_percent = self.margin_sl_percent,
                sizing = self.sizing,
                cash_out_factor = self.cash_out_factor,
                cover_stopped_loss = self.cover_stopped_loss,
                cover_sl_ratio = self.cover_sl_ratio,
                max_unrealised_pnl = self.max_unrealised_pnl,
                trailing_sl = self.trailing_sl,
                data_path = self.data_path,
                instruments = self.instruments,
                out_path = self.out_path,
                inputs_file = self.inputs_file  
            )
        )

    def read_data(self, ticker: str, frequency: str):
        df = pd.read_pickle(f"{self.data_path}{ticker}_{frequency}.pkl")
        return df
    
    def save_files(self, inputs_df, ticker, frequency):
        result = self.sim.d.df[self.sim.name].copy()
        if 'events' in self.records:
            result[~result.events.isnull()].to_csv(f'{self.out_path}{self.sim.name}-events.csv', index=False)
        if 'all' in self.records:
            result.to_csv(f'{self.out_path}{self.sim.name}-all.csv', index=False)
        inputs_df.to_csv(f'{self.out_path}{ticker}-{frequency}-' + self.inputs_file, index=False)

    def process_sim(self, 
                    df: pd.DataFrame,
                    ticker: str,
                    frequency: str,
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
        
        sim_name = f'{ticker}-{frequency}-{self.counter}'

        self.sim = GridSimulator(
            name=sim_name,
            df=df,
            instruments=self.instruments,
            ticker=ticker,
            init_bal=init_bal,
            init_trade_size=init_trade_size,
            grid_pips=grid_pips,
            sl_grid_count=sl_grid_count,
            stop_loss_type=stop_loss_type,
            margin_sl_percent=margin_sl_percent,
            sizing=sizing,
            cash_out_factor=cash_out_factor,
            cover_stopped_loss=cover_stopped_loss,
            cover_sl_ratio=cover_sl_ratio,
            # martingale_sizing=martingale_sizing,
            max_unrealised_pnl=max_unrealised_pnl,
            trailing_sl=trailing_sl
        )

        # inputs = [sim_name, init_trade_size, grid_pips, stop_loss_type, sl_grid_count, grid_pips * sl_grid_count, margin_sl_percent, sizing, cash_out_factor, cover_stopped_loss, None]
        # print(tabulate([inputs], header, tablefmt='plain'))

        def inputs_list():
            gross_bal = self.sim.d.df[self.sim.name].iloc[-1]['gross_bal']
            # covered_sl_martingale = 'martingale' if martingale_sizing else 'covered_sl' if cover_stopped_loss else None
            header = ['sim_name', 'init_trade_size', 'grid_pips', 'stop_loss_type', 'sl_grid_count', 'stoploss_pips', 'margin_sl_percent', 'sizing', 'cash_out_factor', 'covered_sl', 'cover_sl_ratio', 'max_unrealised_pnl', 'trailing_sl', 'gross_bal']
            inputs = [sim_name, init_trade_size, grid_pips, stop_loss_type, sl_grid_count, grid_pips * sl_grid_count, margin_sl_percent, sizing, cash_out_factor, cover_stopped_loss, cover_sl_ratio, max_unrealised_pnl, trailing_sl, gross_bal]
            print(tabulate([inputs], header, tablefmt='plain'))
            self.inputs_list.append(inputs)
            return pd.DataFrame(self.inputs_list, columns=header)

        try:
            # header = ['sim_name', 'init_trade_size', 'grid_pips', 'stop_loss_type', 'sl_grid_count', 'stoploss_pips', 'margin_sl_percent', 'sizing', 'cash_out_factor', 'cover_stopped_loss', 'ac_bal']
            self.sim.run_sim()
            # self.inputs_list[-1][-1] = ac_bal
            # inputs_df.iloc[-1, -1] = ac_bal
            self.save_files(inputs_list(), ticker, frequency)
        except Exception as e:
            self.save_files(inputs_list(), ticker, frequency)
            raise e


    def run_optimizer(self):
        for tk in self.tickers:
            for f in self.frequency:
                df = self.read_data(tk, f).iloc[self.start:self.end]
                for ib in self.init_bal:
                    for t in self.init_trade_size:
                        for s in self.sizing:
                            for g in self.grid_pips:
                                for c in self.cash_out_factor:
                                    for sl in self.stop_loss_type:
                                        for mslp in self.margin_sl_percent:
                                            for slgc in self.sl_grid_count:
                                                for csl in self.cover_stopped_loss:
                                                    for cslr in self.cover_sl_ratio:
                                                        for pnl in self.max_unrealised_pnl:
                                                            # for ms in self.martigale_sizing:
                                                            for tsl in self.trailing_sl:
                                                                if self.counter >= self.checkpoint:
                                                                    # if not (ms and csl):
                                                                    if not self.dummyrun:
                                                                        self.process_sim(
                                                                            df=df,
                                                                            ticker=tk,
                                                                            frequency=f,
                                                                            init_bal=ib,
                                                                            init_trade_size=t,
                                                                            grid_pips=g,
                                                                            sl_grid_count=slgc,
                                                                            stop_loss_type=sl,
                                                                            margin_sl_percent=mslp,
                                                                            sizing=s,
                                                                            cash_out_factor=c,
                                                                            cover_stopped_loss=csl,
                                                                            cover_sl_ratio=cslr,
                                                                            # martingale_sizing=ms,
                                                                            max_unrealised_pnl=pnl,
                                                                            trailing_sl=tsl
                                                                        )  
                                                                self.counter =  self.counter + 1
        if self.dummyrun:
            print(f'{self.counter-1} dummies run successfully')
