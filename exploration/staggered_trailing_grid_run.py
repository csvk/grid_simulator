from staggered_trailing_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/staggered-trailing-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=147
inputs_file=f'inputs.{counter}.csv'
start=0  
end=4000
records=['events']
tickers=['EUR_USD']
frequency=['M5']
init_bal=[1000]
init_trade_size=[100]
grid_pips=[10]
sl_grid_count=[4] # only even numbers in this strategy
notrade_margin_percent=[None]
notrade_count=[None]
notrade_type=['all', 'new', 'cover']
sizing=['static', 'dynamic']
cash_out_factor=[None]
trailing_sl = [False]


if __name__ == '__main__':
    optim = GridOptimizer(
        checkpoint=checkpoint,
        counter=counter,
        start=start,
        end=end,
        records=records,
        tickers=tickers,
        frequency=frequency,
        init_bal=init_bal,      
        init_trade_size=init_trade_size,
        grid_pips=grid_pips,
        sl_grid_count=sl_grid_count,
        notrade_margin_percent=notrade_margin_percent,
        notrade_count=notrade_count,
        notrade_type=notrade_type,
        sizing=sizing,
        cash_out_factor=cash_out_factor,
        trailing_sl=trailing_sl,
        data_path=data_path,
        instruments=instruments,
        out_path=out_path,
        inputs_file=inputs_file,
        dummyrun=dummyrun
    )

    print(optim)

    optim.run_optimizer()