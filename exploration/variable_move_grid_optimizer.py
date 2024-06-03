from variable_move_grid_simulator import GridSimulator
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
            tp_grid_count: list,
            sl_grid_count: list,
            moves_for_weightage: list,
            notrade_margin_percent: list,
            notrade_count: list,
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
        self.tp_grid_count = tp_grid_count
        self.sl_grid_count = sl_grid_count
        self.moves_for_weightage = moves_for_weightage
        self.notrade_margin_percent = notrade_margin_percent
        self.notrade_count = notrade_count
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
                tp_grid_count = self.tp_grid_count,
                sl_grid_count = self.sl_grid_count,
                moves_for_weightage = self.moves_for_weightage,
                notrade_margin_percent = self.notrade_margin_percent,
                notrade_count = self.notrade_count,
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
    
    def to_dict(self, data):
        if type(data) == str:
            data = eval(data)
        elif type(data) == dict:
            data = data
        else:
            data = dict()
        return data
    
    def trade_no_only(self, result: pd.DataFrame):
        trade_nos = lambda x: tuple(self.to_dict(x).keys())
        result.open_longs = result.open_longs.apply(trade_nos)
        result.open_shorts = result.open_shorts.apply(trade_nos)
        result.closed_longs = result.closed_longs.apply(trade_nos)
        result.closed_shorts = result.closed_shorts.apply(trade_nos)
        return result
    
    def save_files(self, inputs_df, ticker, frequency):
        result = self.sim.d.df[self.sim.name].copy()
        if 'events' in self.records:
            result[~result.events.isnull()].to_csv(f'{self.out_path}{self.sim.name}-events.csv', index=False)
            result = self.trade_no_only(result)
            result[~result.events.isnull()].to_csv(f'{self.out_path}{self.sim.name}-events.less-details.csv', index=False)
            
        if 'all' in self.records:
            result.to_csv(f'{self.out_path}{self.sim.name}-all.csv', index=False)
            result = self.trade_no_only(result)
            result.to_csv(f'{self.out_path}{self.sim.name}-all.less-details.csv', index=False)
            
        inputs_df.to_csv(f'{self.out_path}{ticker}-{frequency}-' + self.inputs_file, index=False)

    def process_sim(self, 
                    df: pd.DataFrame,
                    ticker: str,
                    frequency: str,
                    init_bal: float,
                    init_trade_size: int,
                    grid_pips: int,
                    tp_grid_count: int,
                    sl_grid_count: int,
                    moves_for_weightage: int,
                    notrade_margin_percent: float,
                    notrade_count: int,
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
            tp_grid_count=tp_grid_count,
            sl_grid_count=sl_grid_count,
            moves_for_weightage=moves_for_weightage,
            notrade_margin_percent=notrade_margin_percent,
            notrade_count=notrade_count,
            sizing=sizing,
            cash_out_factor=cash_out_factor,
            trailing_sl=trailing_sl
        )

        def inputs_list():
            gross_bal = self.sim.d.df[self.sim.name].iloc[-1]['gross_bal']
            start, end = self.sim.d.df[self.sim.name].iloc[0]['time'], self.sim.d.df[self.sim.name].iloc[-1]['time']
            header = ['sim_name', 'start', 'end', 'init_bal', 'init_trade_size', 'grid_pips', 'tp_grid_count', 'sl_grid_count', 'moves_for_weightage', 'notrade_margin_percent', 'notrade_count', 'sizing', 'cash_out_factor', 'trailing_sl', 'gross_bal']
            inputs = [sim_name, start, end, init_bal, init_trade_size, grid_pips, tp_grid_count, sl_grid_count, moves_for_weightage, notrade_margin_percent, notrade_count, sizing, cash_out_factor, trailing_sl, gross_bal]
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
                                            for tpgc in self.tp_grid_count:
                                                for slgc in self.sl_grid_count:
                                                    for mw in self.moves_for_weightage:
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
                                                                        tp_grid_count=tpgc,
                                                                        sl_grid_count=slgc,
                                                                        moves_for_weightage=mw,
                                                                        notrade_margin_percent=ntsp,
                                                                        notrade_count=ntc,
                                                                        sizing=s,
                                                                        cash_out_factor=c,
                                                                        trailing_sl=tsl
                                                                    )  
                                                            self.counter =  self.counter + 1
        if self.dummyrun:
            print(f'{self.counter-1} dummies run successfully')