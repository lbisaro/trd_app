from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
import datetime as dt
import time
import pandas as pd

from local__config import COINMCAP_APK
from scripts.top30_update_backtest_klines import backtest_symbols
from scripts.Exchange import Exchange

from binance.client import Client
client = Client()
#Funcion para descarga de velas
def get_klines(symbol,interval,start,end):
    df = client.get_historical_klines(symbol=symbol, interval=interval, start_str=start, end_str=end)
    df = pd.DataFrame(df)
    df = df.iloc[:, :6]
    df.columns = ["datetime", "open", "high", "low", "close", "volume"]
    df['open'] = df['open'].astype('float')
    df['high'] = df['high'].astype('float')
    df['low'] = df['low'].astype('float')
    df['close'] = df['close'].astype('float')
    df['volume'] = df['volume'].astype('float')
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    #df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') - dt.timedelta(hours=3)
    #df=df.set_index('datetime')
    return df

class CoinmarketCap:
    stable_coin = 'USDT'


    def __init__(self):
        pass


    def top30(self):

        date_add_limit = '2020-11-01'
        date_end = '2024-01-01'

        symbols_ok = [
            'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'LINKUSDT', 'BCHUSDT', 
            'XLMUSDT', 'ZECUSDT', 'LTCUSDT', 'HBARUSDT',  
            'XMRUSDT',  'DOTUSDT',  
            'ETCUSDT', 'ALGOUSDT',  'VETUSDT', 'ATOMUSDT', 
            'DASHUSDT', 'STXUSDT', 'FETUSDT', 
            'CRVUSDT', 'XTZUSDT', 'IOTAUSDT', 'DCRUSDT',
            'MATICUSDT','THETAUSDT',
        ]

        bnc = Exchange(type='info',exchange='bnc',prms=None)
        exclude_symbols = ['RENDERUSDT','SOLUSDT','AVAXUSDT','UNIUSDT','NEARUSDT', 
                           'AAVEUSDT','FILUSDT','PAXGUSDT', 'INJUSDT', ]
        
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        parameters = {
            'start': 1,
            'convert': 'USD',
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': COINMCAP_APK,
        }

        session = Session()
        session.headers.update(headers)

        try:
            response = session.get(url, params=parameters)
            response_json = json.loads(response.text)
            data = []
            response_json_data = response_json['data']

            for rjd in response_json_data:
                symbol = rjd['symbol']+self.stable_coin
                if symbol not in exclude_symbols \
                    and 'stablecoin' not in rjd['tags'] \
                    and symbol not in backtest_symbols:
                    #and rjd['date_added'][:10] < date_add_limit \
                    #and 'binance-listing' in rjd['tags'] \
                    if symbol in symbols_ok:
                        data.append(rjd['symbol']+self.stable_coin)
                        print(f'Exist: {symbol} ',len(data))
                    else:
                        print('descargando',symbol,end=' ')
                        try:
                            
                            klines = get_klines(symbol,'1M',date_add_limit , date_end)
                            kline_start = str(klines.iloc[0]['datetime'])[0:10]
                            kline_end = str(klines.iloc[-1]['datetime'])[0:10]
                            if kline_start == date_add_limit and kline_end>=date_end:
                                data.append(rjd['symbol']+self.stable_coin)
                                print(f'Add: {symbol} ',len(data))
                                time.sleep(3) #Demora en segundos
                        except:
                            pass

                if len(data) >= 30:
                    return data

            return data
        
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            print(e)