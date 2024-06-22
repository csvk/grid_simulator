from stepped_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/stepped-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=40
inputs_file=f'inputs.{counter}.csv'
start=0
end=20000
records=['events']
tickers=['EUR_USD']
frequency=['M5']
init_bal=[1000]
init_trade_size=[100]
grid_pips=[20]
tp_grid_count=[2] 
sl_grid_count=[10]
cov_grid_count=[1000]
sizing=['dynamic', 'static']
cash_out_factor=[None]
trailing_sl = [True]

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
        tp_grid_count=tp_grid_count,
        sl_grid_count=sl_grid_count,
        cov_grid_count=cov_grid_count,
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