from trend_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/trend-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=40
inputs_file=f'inputs.{counter}.csv'
start=0
end=1000000
records=['events']
tickers=['EUR_USD']
frequency=['S5']
init_bal=[1000]
init_trade_size=[5000]
grid_pips=[20]
tp_grid_count=[1]
sl_grid_count=[1]
pyr_grid_count=[100, 2]
pyr_change_grid_count=[None]
pyramid_size_factor=[(0.50,)] # using tuple to handle pyramid size change
moves_for_direction=[None]
sizing=['dynamicmax', 'dynamic']
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
        moves_for_direction=moves_for_direction,
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