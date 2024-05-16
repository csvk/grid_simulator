import sys
sys.path.append("../")
from hedgeoptim import process_sim, Data
import random

INPUTS_FILE = 'inputs1.pkl'
BUY = 1
SELL = -1
CLOSE = 2
NONE = 0

d = Data("D:/OneDrive/Studies/forex_bot/souvik/data/EUR_USD_M5.pkl")

cushion = [1.5, 2.0, 2.5, 3.0, 4.0]
rr = [1.5, 2, 3]
risk = [0.0010, 0.0020, 0.0030, 0.0040]
streak_trade_limit = [1, 2, 3]

counter = 1
inputs_list = list()
for c in cushion:
    for r_r in rr:
        for r in risk:
            for lim in streak_trade_limit:
                # if counter > 163:
                inputs = process_sim(
                    d=d,
                    counter=counter,
                    init_signal=random.choice([BUY, SELL]),
                    cushion=c,
                    rr=r_r,
                    risk=r,
                    streak_trade_limit=lim,
                    inputs_list=inputs_list,
                    inputs_file=INPUTS_FILE
                )  
                counter =  counter + 1