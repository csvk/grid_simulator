from hedge_simulator import GridSimulator
from tabulate import tabulate
import pandas as pd
from talib import ATR

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
            init_capacity: list,
            topup_capacity: list,
            max_capacity: list,
            trade_to_capacity_threshold: list,
            distance_factor: list,
            atr_length: list,
            hedge_pips: list,
            tp_pips: list,
            topup_pips: list,
            trailing_hedge_pips: list,
            keep_percent: list,
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
        self.init_capacity = init_capacity
        self.topup_capacity = topup_capacity
        self.max_capacity = max_capacity
        self.trade_to_capacity_threshold = trade_to_capacity_threshold
        self.distance_factor = distance_factor
        self.atr_length = atr_length
        self.hedge_pips = hedge_pips
        self.tp_pips = tp_pips
        self.topup_pips = topup_pips
        self.trailing_hedge_pips = trailing_hedge_pips
        self.keep_percent = keep_percent
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
                init_capacity = self.init_capacity,
                topup_capacity = self.topup_capacity,
                max_capacity = self.max_capacity,
                trade_to_capacity_threshold = self.trade_to_capacity_threshold,
                distance_factor = self.distance_factor,
                atr_length = self.atr_length,
                hedge_pips = self.hedge_pips,
                tp_pips = self.tp_pips,
                topup_pips = self.topup_pips,
                trailing_hedge_pips = self.trailing_hedge_pips,
                keep_percent = self.keep_percent,
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
                    init_capacity: int,
                    topup_capacity: int,
                    max_capacity: int,
                    trade_to_capacity_threshold: int,
                    distance_factor: str,
                    atr_length: int,
                    hedge_pips: int,
                    tp_pips: int,
                    topup_pips: int,
                    trailing_hedge_pips: int,
                    keep_percent: float):
        
        sim_name = f'{ticker}-{frequency}-{self.counter}'

        self.sim = GridSimulator(
            name=sim_name,
            df=df,
            instruments=self.instruments,
            ticker=ticker,
            init_bal=init_bal,
            init_capacity=init_capacity,
            topup_capacity=topup_capacity,
            max_capacity=max_capacity,
            trade_to_capacity_threshold=trade_to_capacity_threshold,
            distance_factor=distance_factor,
            hedge_pips=hedge_pips,
            tp_pips=tp_pips,
            topup_pips=topup_pips,
            trailing_hedge_pips=trailing_hedge_pips,
            keep_percent=keep_percent
        )

        def inputs_list():
            gross_bal = self.sim.d.df[self.sim.name].iloc[-1]['gross_bal']
            start, end = self.sim.d.df[self.sim.name].iloc[0]['time'], self.sim.d.df[self.sim.name].iloc[-1]['time']
            header = ['sim_name', 'start', 'end', 'init_bal', 'init_capacity', 'topup_capacity', 'max_capacity', 'trade_to_capacity_threshold', 'atr_length', 'hedge_pips', 'tp_pips', 'topup_pips', 'keep_percent', 'gross_bal']
            inputs = [sim_name, start, end, init_bal, init_capacity, topup_capacity, max_capacity, trade_to_capacity_threshold, atr_length, hedge_pips, tp_pips, topup_pips, keep_percent, gross_bal]
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
                for atrl in self.atr_length:
                    df['atr_c'] = ATR(df.mid_h.values, df.mid_l.values, df.mid_c.values, timeperiod=atrl)
                    df2 = df.dropna()
                    for ib in self.init_bal:
                        for its in self.init_capacity:
                            for tts in self.topup_capacity:
                                for mps in self.max_capacity:
                                    for t2c in self.trade_to_capacity_threshold:
                                            for df in self.distance_factor:
                                                for hp in self.hedge_pips:
                                                    for tpp in self.tp_pips:
                                                        for topp in self.topup_pips:
                                                            for thp in self.trailing_hedge_pips:
                                                                for kp in self.keep_percent:
                                                                    if self.counter >= self.checkpoint:
                                                                        if not self.dummyrun:
                                                                            self.process_sim(
                                                                                df=df2,
                                                                                ticker=tk,
                                                                                frequency=f,
                                                                                init_bal=ib,
                                                                                init_capacity=its,
                                                                                topup_capacity=tts,
                                                                                max_capacity=mps,
                                                                                trade_to_capacity_threshold=t2c,
                                                                                distance_factor=df,
                                                                                atr_length=atrl,
                                                                                hedge_pips=hp,
                                                                                tp_pips=tpp,
                                                                                topup_pips=topp,
                                                                                trailing_hedge_pips=thp,
                                                                                keep_percent=kp
                                                                            )  
                                                                    self.counter =  self.counter + 1
        if self.dummyrun:
            print(f'{self.counter-1} dummies run successfully')

    def execute(self):
        self.run_optimizer()
