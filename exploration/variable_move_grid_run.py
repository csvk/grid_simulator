from variable_move_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/variable-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=140
inputs_file=f'inputs.{counter}.csv'
start=None
end=None
records=['events']
tickers=['EUR_USD']
frequency=['M5']
init_bal=[5000]
init_trade_size=[1000]
grid_pips=[20]
tp_grid_count=[2, 3]
sl_grid_count=[20, 30]
moves_for_weightage=[5, 10]
notrade_margin_percent=[None]
notrade_count=[None]
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
        moves_for_weightage=moves_for_weightage,
        notrade_margin_percent=notrade_margin_percent,
        notrade_count=notrade_count,
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