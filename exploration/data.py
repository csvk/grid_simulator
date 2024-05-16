import pandas as pd
import json
from tabulate import tabulate


class Data:
    
    def __init__(self, source, ticker: str, cols: list=None, instruments: str=None):
        assert type(source) == str or type(source) == pd.DataFrame, 'Invalid source'
        assert type(instruments) == str, 'Require instruments.json'
        if type(source) == str:
            self.df = {
                'raw': pd.read_pickle(source) if cols == None else pd.read_pickle(source)[cols]
            }
        elif type(source) == pd.DataFrame:
            self.df = {
                'raw': source.copy() if cols == None else source.copy()[cols]
            }            

        if 'time' in self.df['raw'].columns:
            self.df['raw']['time'] = [ x.replace(tzinfo=None) for x in self.df['raw']['time']]
        self.datalen = self.df['raw'].shape[0]

        with open(instruments, 'r') as f:
            self.ticker = json.load(f)[ticker]

    def __repr__(self) -> str:
        repr = str()
        for name, df in self.df.items():
            repr = repr + name + ':\n' + str(pd.concat([df.head(2), df.tail(1)])) + '\n'
        repr = repr + 'ticker:\n' + str(self.ticker)
        return repr
    
    def prep_data(self, name: str, start: int, end: int, source: str='raw', cols: list=None):
        '''Create new dataframe with specified list of columns and number of rows as preparation for fast data creation
        '''
        if cols == None:
            cols = self.df[source].columns

        if start == None:
            start = 0
        if end == None:
            end = self.datalen

        assert end > start, f'start={start}, end={end} not valid'

        self.df[name] = self.df[source][cols].iloc[start:end].copy()
        self.df[name].reset_index(drop=True, inplace=True)

    def add_columns(self, name: str, cols: dict):
        '''Add new columns to component dataframes
        '''        
        exist_cols = list(self.df[name].columns)
        for col, _type in cols.items():
            self.df[name][col] = pd.Series(dtype=_type) 

    def prepare_fast_data(self, name: str, start: int, end: int, source: str='raw', cols: list=None, add_cols: dict=None):
        '''Prepare data as an array for fast processing
        fcols = {col1: col1_index, col2: col2_index, .... }     
        fastdf = [array[col1], array[col2], array[col3], .... ]
        Accessed by: self.fdata()
        '''

        self.prep_data(name=name, start=start, end=end, source=source, cols=cols)
        if add_cols:
            self.add_columns(name=name, cols=add_cols)

        self.fcols = dict()
        for i in range(len(self.df[name].columns)):
            self.fcols[self.df[name].columns[i]] = i
        self.fastdf = [self.df[name][col].array for col in self.df[name].columns]
        self.fdatalen = len(self.fastdf[0])

    def fdata(self, column: str=None, index: int=None, rows: int=None):
        '''Pass rows=-1 if all rows need to be returned
        '''
        if column is None:
            return self.fastdf
        if index is None:
            return self.fastdf[self.fcols[column]]
        else:
            if rows is not None:
                if rows >= 0:
                    rows = min(rows, self.fdatalen - index)
                    return self.fastdf[self.fcols[column]][index:index+rows]
                else:
                    return self.fastdf[self.fcols[column]][index:]
            else:
                return self.fastdf[self.fcols[column]][index]
        
    def update_fdata(self, column: str, index: int=None, value: float=None):
        if index is None:
            assert len(value) == self.fdatalen
            for i in range(self.fdatalen):
                self.fastdf[self.fcols[column]][i] = value[i]
        else:
            self.fastdf[self.fcols[column]][index] = value

    def print_row(self, i: int):
        print(tabulate([[i] + [self.fastdf[self.fcols[col]][i] for col in self.fcols.keys()]], ['index']+ list(self.fcols.keys()), tablefmt='plain'))

