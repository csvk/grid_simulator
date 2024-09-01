from parallel_martingale_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/parallel-martigale-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=115
inputs_file=f'inputs.{counter}.csv'
start=None
end=None
records=['events']
tickers=['EUR_USD']
frequency=['M5']
init_bal=[1000]
init_trade_size=[1000]
grid_pips=[20]
tp_grid_count=[2]
sl_grid_count=[2]
pyr_grid_count=[1000]
pyr_change_grid_count=[None]
pyramid_size_factor=[(0.50,)] # using tuple to handle pyramid size change
martingale_count=[30]
martingale_depth=[5]
martingale_cushion=[1.10]
sizing=['dynamicmax']
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
        pyr_grid_count=pyr_grid_count,
        pyr_change_grid_count=pyr_change_grid_count,
        pyramid_size_factor=pyramid_size_factor,
        martingale_count=martingale_count,
        martingale_depth=martingale_depth,
        martingale_cushion=martingale_cushion,
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

    optim.execute()