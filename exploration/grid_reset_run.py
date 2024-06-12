from grid_reset_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/grid-reset/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=70
inputs_file=f'inputs.{counter}.csv'
start=None
end=None
records=['events']
tickers=['EUR_USD']
frequency=['M5']
init_bal=[5000]
init_trade_size=[2000]
grid_pips=[20]
tp_grid_count=[2]
sl_grid_count=[10]
max_unrealised_pnl=[None]
max_trades_per_grid=[None]
max_trades_per_side=[None]
moves_for_weightage=[None]
sizing=['dynamic', 'static']
cash_out_factor=[None]
trailing_sl = [True]
grid_reset=[True]

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
        max_unrealised_pnl=max_unrealised_pnl,
        max_trades_per_grid=max_trades_per_grid,
        max_trades_per_side=max_trades_per_side,
        moves_for_weightage=moves_for_weightage,
        sizing=sizing,
        cash_out_factor=cash_out_factor,
        trailing_sl=trailing_sl,
        grid_reset=grid_reset,
        data_path=data_path,
        instruments=instruments,
        out_path=out_path,
        inputs_file=inputs_file,
        dummyrun=dummyrun
    )

    print(optim)

    optim.run_optimizer()