from hedge_optimizer import GridOptimizer

data_path = '../data/'
out_path = 'D:/Trading/ml4t-data/hedge/'
instruments = "../data/instruments.json"

dummyrun = False
checkpoint=0
counter=1
inputs_file=f'inputs.{counter}.csv'
start=0
end=10000
records=['events']
tickers=['GBP_JPY']
frequency=['M5']
init_bal=[1000]
init_capacity=[7500]
topup_capacity=[2500]
max_capacity=[15000]
trade_to_capacity_threshold=[2500]
distance_factor=['fixed'] # 'atr' & 'fixed'
atr_length=[14]
hedge_pips=[20]
tp_pips=[30]
topup_pips=[90]
trailing_hedge_pips=[10]
keep_percent=[0.20]

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
        init_capacity=init_capacity,
        topup_capacity=topup_capacity,
        max_capacity=max_capacity,
        trade_to_capacity_threshold=trade_to_capacity_threshold,
        distance_factor=distance_factor,
        atr_length=atr_length,
        hedge_pips=hedge_pips,
        tp_pips=tp_pips,
        topup_pips=topup_pips,
        trailing_hedge_pips=trailing_hedge_pips,
        keep_percent=keep_percent,
        data_path=data_path,
        instruments=instruments,
        out_path=out_path,
        inputs_file=inputs_file,
        dummyrun=dummyrun
    )

    print(optim)

    optim.execute()