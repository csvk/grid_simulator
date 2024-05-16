from martingale_grid_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/martingale-grid/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=1300
start=0  
end=500000
records=['events']
tickers=['EUR_USD']
frequency=['S5']
init_bal=[5000]
init_trade_size=[10]
grid_pips=[10, 20, 30]
sizing=['static', 'dynamic']
cash_out_factor=[None]
martingale_factor = [3.0] # [2.0]
# martingale_factor2 = [2.0]
# factor_reset=[None, 5]
pyramiding = [True] # [False]
streak_reset=[5] # [5, 10]
streak_reset_percent = [0.50]
trade_price_type = ['bidask', 'mid']
trailing_sl = [True] # [False]
inputs_file='inputs.2b.csv'


if __name__ == '__main__':
    optim = GridOptimizer(
        checkpoint=checkpoint,
        counter=counter,
        start=start,
        end=end,
        records=records,
        tickers=tickers,
        frequency=frequency,
        trade_price_type=trade_price_type,
        init_bal=init_bal,      
        init_trade_size=init_trade_size,
        grid_pips=grid_pips,
        sizing=sizing,
        cash_out_factor=cash_out_factor,
        martingale_factor=martingale_factor,
        # martingale_factor2=martingale_factor2,
        # factor_reset=factor_reset,
        pyramiding=pyramiding,
        streak_reset=streak_reset,
        streak_reset_percent=streak_reset_percent,
        trailing_sl=trailing_sl,
        data_path=data_path,
        instruments=instruments,
        out_path=out_path,
        inputs_file=inputs_file,
        dummyrun=dummyrun
    )

    print(optim)

    optim.run_optimizer()