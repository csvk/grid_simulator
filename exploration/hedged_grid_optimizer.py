from hedged_grid_simulator import GridSimulator
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
            notrade_margin_percent: list,
            notrade_count: list,
            notrade_type: list,
            sizing: list,
            cash_out_factor: list,
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
        self.notrade_margin_percent = notrade_margin_percent
        self.notrade_count = notrade_count
        self.notrade_type = notrade_type
        self.sizing = sizing
        self.cash_out_factor = cash_out_factor
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
                notrade_margin_percent = self.notrade_margin_percent,
                notrade_count = self.notrade_count,
                notrade_type = self.notrade_type,
                sizing = self.sizing,
                cash_out_factor = self.cash_out_factor,
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
                    notrade_margin_percent: float,
                    notrade_count: int,
                    notrade_type: str,
                    sizing: str,
                    cash_out_factor: float,
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
            notrade_margin_percent=notrade_margin_percent,
            notrade_count=notrade_count,
            notrade_type=notrade_type,
            sizing=sizing,
            cash_out_factor=cash_out_factor,
            trailing_sl=trailing_sl
        )

        def inputs_list():
            gross_bal = self.sim.d.df[self.sim.name].iloc[-1]['gross_bal']
            start, end = self.sim.d.df[self.sim.name].iloc[0]['time'], self.sim.d.df[self.sim.name].iloc[-1]['time']
            header = ['sim_name', 'start', 'end', 'init_bal', 'init_trade_size', 'grid_pips', 'sl_grid_count', 'stoploss_pips', 'notrade_margin_percent', 'notrade_count', 'notrade_type', 'sizing', 'cash_out_factor', 'trailing_sl', 'gross_bal']
            inputs = [sim_name, start, end, init_bal, init_trade_size, grid_pips, sl_grid_count, grid_pips * sl_grid_count, notrade_margin_percent, notrade_count, notrade_type, sizing, cash_out_factor, trailing_sl, gross_bal]
            print(tabulate([inputs], header, tablefmt='plain'))
            self.inputs_list.append(inputs)
            return pd.DataFrame(self.inputs_list, columns=header)

        try:
            self.sim.run_sim()

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
                                    for ntsp in self.notrade_margin_percent:
                                        for ntc in self.notrade_count:
                                            for ntt in self.notrade_type:
                                                for slgc in self.sl_grid_count:
                                                    for tsl in self.trailing_sl:
                                                        if self.counter >= self.checkpoint:
                                                            if not self.dummyrun:
                                                                self.process_sim(
                                                                    df=df,
                                                                    ticker=tk,
                                                                    frequency=f,
                                                                    init_bal=ib,
                                                                    init_trade_size=t,
                                                                    grid_pips=g,
                                                                    sl_grid_count=slgc,
                                                                    notrade_margin_percent=ntsp,
                                                                    notrade_count=ntc,
                                                                    notrade_type=ntt,
                                                                    sizing=s,
                                                                    cash_out_factor=c,
                                                                    trailing_sl=tsl
                                                                )  
                                                        self.counter =  self.counter + 1
        if self.dummyrun:
            print(f'{self.counter-1} dummies run successfully')