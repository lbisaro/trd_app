from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
import datetime as dt

from local__config import COINMCAP_APK
from scripts.top30_update_backtest_klines import backtest_symbols
from scripts.Exchange import Exchange

class CoinmarketCap:
    stable_coin = 'USDT'


    def __init__(self):
        pass

    def top30(self):

        date_add_limit = '2021-01-01'

        disabled_symbols = ['SUIUSDT','XMRUSDT','TONUSDT','APTUSDT', 'WLDUSDT','RENDERUSDT','POLUSDT']

        bnc = Exchange(type='info',exchange='bnc',prms=None)
        bnc_symbols = bnc.get_all_prices()
        
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
                if symbol in bnc_symbols \
                   and 'stablecoin' not in rjd['tags'] \
                   and rjd['date_added'][:10] < date_add_limit \
                   and 'binance-listing' in rjd['tags'] \
                   and symbol not in backtest_symbols \
                   and symbol not in disabled_symbols :
                   
                    data.append(rjd['symbol']+self.stable_coin)

                if len(data) >= 30:
                    return data

            return data
        
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            print(e)