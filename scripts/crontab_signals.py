from scripts.Exchange import Exchange
from bot.models import *
from bot.model_kline import *
from user.models import UserProfile
import scripts.functions as fn
from scripts.indicators import supertrend
from datetime import datetime

from scripts.app_log import app_log as Log


def run():
    exch = Exchange(type='info',exchange='bnc',prms=None)
    klines = {}
    trends = {}
    limit = 200

    symbols = ['BTCUSDT','ETHUSDT','BNBUSDT']
    intervals = ['0m30','1h01','1h04','2d01']
    print(datetime.now().strftime("%Y-%m-%d %H:%M"))
    for symbol in symbols:
        print(f'{symbol.rjust(10)}', end=' -> ')
        for interval_id in intervals:
            if not symbol in klines:
                klines[symbol] = {}
                trends[symbol] = {}

            bnc_interval = fn.get_intervals(interval_id,'binance')
            df = exch.get_klines(symbol=symbol,interval_id=interval_id,limit=limit)
            df = supertrend(df)
            klines[symbol][bnc_interval] = df
            last = df.iloc[-1]
            trend = 'Neutro'
            if last['st_trend'] > 0:
                trend = 'Alcista' 
            elif last['st_trend'] < 0:
                trend = 'Bajista' 
            trends[symbol][bnc_interval] = trend 
            print(f'{bnc_interval.rjust(3)} {trend.ljust(10)}', end=' ')
        print(' ')