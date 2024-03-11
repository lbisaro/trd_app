from binance.client import Client as BinanceClient
from local__config import *
import math
from datetime import datetime, timedelta, timezone
import pytz
import pandas as pd
from scripts.functions import get_intervals

from bot.model_kline import * 

class Exchange():

    start_klines_str = '2022-08-01 00:00:00 UTC-3'
    exchange = ''

    def __init__(self,type,exchange,prms):
        self.exchange = exchange
        if exchange == 'bnc':
            if type == 'info':
                self.client = BinanceClient()
        
            elif type == 'general_apikey':
                self.client = BinanceClient(api_key=LOC_BNC_AK, api_secret=LOC_BNC_SK, testnet=LOC_BNC_TESNET)

            elif type == 'user_apikey':
                apk = prms['bnc_apk']
                aps = prms['bnc_aps']
            
                if prms['bnc_env'] == 'test':
                    self.client = BinanceClient(api_key=apk, api_secret=aps, testnet=True)
                else:
                    self.client = BinanceClient(api_key=apk, api_secret=aps)

    def check_connection(self):
        try:
            if self.exchange == 'bnc':
                self.client.get_account()
                return True
            
            return False
        except:
            return False
        
    def get_exchange_time(self):
        time_res = self.client.get_server_time()
        time_res = datetime.utcfromtimestamp(time_res['serverTime'] / 1000) - timedelta(hours = 3)
        return time_res

    def get_symbol_info(self,symbol):
        symbol = symbol.upper()

        db = Symbol.objects.filter(symbol = symbol)
        if not db:
            symbol_info = self.client.get_symbol_info(symbol)
            qty_decs_qty   = self.calcular_decimales(float(symbol_info['filters'][1]['minQty']))
            qty_decs_price = self.calcular_decimales(float(symbol_info['filters'][0]['minPrice']))
            symbol_info['qty_decs_price'] = qty_decs_price
            symbol_info['qty_decs_qty'] = qty_decs_qty
            symbol_info['quote_asset'] = symbol_info['quoteAsset']
            symbol_info['base_asset'] = symbol_info['baseAsset']
            if symbol_info['quote_asset'] == 'USDT' or symbol_info['quote_asset'] == 'BUSD' or symbol_info['quote_asset'] == 'USDC':
                symbol_info['qty_decs_quote'] = 2

        else:
            symbol_info = {}
            for i in db:
                symbol_info['qty_decs_price'] = i.qty_decs_price
                symbol_info['qty_decs_qty'] = i.qty_decs_qty
                symbol_info['qty_decs_quote'] = i.qty_decs_quote
                symbol_info['quote_asset'] = i.quote_asset
                symbol_info['base_asset'] = i.base_asset
        
        return symbol_info

    def get_all_prices(self):
        all_prices = {}
        exch_prices = self.client.get_all_tickers()
        for item in exch_prices:
            all_prices[item['symbol']] = float(item['price'])
        return all_prices
    
    def calcular_decimales(self,step_size):
        potencia = int(math.log10(step_size))
        decimales = ( 0 if potencia>0 else -potencia )
        return decimales
    
    def get_symbol_price(self,symbol):
        result = self.client.get_avg_price(symbol=symbol)
        avg_price = float(result['price'])
        return avg_price
    
    def get_klines(self,symbol,interval_id,limit):
        interval = get_intervals(interval_id,'binance')
        klines = self.client.get_historical_klines(symbol=symbol, 
                                                   interval=interval,
                                                   limit=limit)
        df = pd.DataFrame(klines)
        df = df.iloc[:, :6]
        df.columns = ["datetime", "open", "high", "low", "close", "volume"]
        df['open'] = df['open'].astype('float')
        df['high'] = df['high'].astype('float')
        df['low'] = df['low'].astype('float')
        df['close'] = df['close'].astype('float')
        df['volume'] = df['volume'].astype('float')
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') - pd.Timedelta('3 hr')
        return df
        
    def update_klines(self,symbol='ALL'):
        MINUTES_TO_GET = 1440 # 60 minutos * 24 horas = 1 dia
        res = {}
        if symbol == 'ALL':
            symbols = Symbol.objects.filter(activo__gt=0)
        else:
            symbols = Symbol.objects.filter(symbol=symbol)
        
        for s in symbols:

            valid_last_minute = (datetime.now() - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M')
            last_kline = Kline.objects.filter(symbol_id=s.id).order_by('-datetime').first()
            if last_kline:
                
                last_minute = last_kline.datetime.strftime('%Y-%m-%d %H:%M')

                next_datetime = ( last_kline.datetime + timedelta(minutes=1) ).strftime('%Y-%m-%d %H:%M:%S') 
            else:
                ref_date = datetime.now()-timedelta(days=210)
                next_datetime = ref_date.strftime('%Y-%m-%d %H:%M:%S')
                last_minute = ref_date.strftime('%Y-%m-%d %H:%M')
            
            end_datetime = ( datetime.strptime(next_datetime, '%Y-%m-%d %H:%M:%S') + timedelta(minutes=MINUTES_TO_GET) ).strftime('%Y-%m-%d %H:%M:%S')
            
            if last_minute < valid_last_minute:
                try:
                    klines = self.client.get_historical_klines(symbol=s.symbol, 
                                                                interval='1m', 
                                                                start_str=next_datetime+ ' UTC-3',
                                                                end_str=end_datetime+ ' UTC-3')

                    df = pd.DataFrame(klines)
                    df = df.iloc[:, :6]
                    df.columns = ["datetime", "open", "high", "low", "close", "volume"]
                    df['open'] = df['open'].astype('float')
                    df['high'] = df['high'].astype('float')
                    df['low'] = df['low'].astype('float')
                    df['close'] = df['close'].astype('float')
                    df['volume'] = df['volume'].astype('float')
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') - pd.Timedelta('3 hr')
                    df['symbol_id'] = s.id
                    qty_records =  int(df['datetime'].count()) 

                    timezone = pytz.timezone('UTC')
                    
                    #Si no obtuvo el total de las velas esperadas es porque llego al final del lote
                    #Por lo tanto, se elimina el ultimo registro para no almacenar velas que estan en formacion
                    if qty_records < MINUTES_TO_GET: 
                        df = df[:-1]   
                         
                    updated = False
                    qty_records =  int(df['datetime'].count())
                    if qty_records > 0:

                        df_records = df.to_dict('records')
                        data = [Kline(
                            datetime = timezone.localize(row['datetime']),
                            open  = row['open'],
                            high  = row['high'],
                            low  = row['low'],
                            close  = row['close'],
                            volume  = row['volume'],
                            symbol_id  = row['symbol_id'],
                        ) for row in df_records]
                        Kline.objects.bulk_create(data)
                        if qty_records < MINUTES_TO_GET:
                            updated = True 
                        else:
                            updated = False
                        res[s.symbol] = {'qty':qty_records, 'updated': updated, 'datetime': df['datetime'].iloc[-1].strftime('%Y-%m-%d %H:%M')} 
                    else:
                        updated = True
                        res[s.symbol] = {'qty':0, 'updated': True, 'datetime': df['datetime'].iloc[-1].strftime('%Y-%m-%d %H:%M')} 
                    if updated:
                        s.activate()
                except Exception as e:
                    print(str(e))
                    pass 
            else:
                res[s.symbol] = {'qty':0, 'updated': True, 'datetime': valid_last_minute}
                s.activate()
                

        return res
    
    def get_wallet(self):
        wallet = {}
        account = self.client.get_account()
        for item in account['balances']:
            wallet[item['asset']] = {'free':float(item['free']),
                                     'locked':float(item['locked']),
                                    }
        return wallet

    def order_market_buy(self, symbol, qty):
        print(f'BUY {symbol} {qty}')
        order = self.client.order_market_buy(symbol=symbol, quantity=qty)
        return order

    def order_market_sell(self, symbol, qty):
        print(f'SELL {symbol} {qty}')
        order = self.client.order_market_sell(symbol=symbol, quantity=qty)
        return order
    
    def get_order(self,symbol,orderId):
        order = self.client.get_order(symbol=symbol,orderId=orderId)
        info = {}
        symbol_info = self.get_symbol_info(symbol=symbol)
         
        info['symbol'] = order['symbol']
        info['orderId'] = order['orderId']
        info['qty'] = float(order['executedQty'])
        info['quote'] = float(order['cummulativeQuoteQty'])
        info['price'] = round(float(order['cummulativeQuoteQty'])/float(order['executedQty']) , symbol_info['qty_decs_price'])
        info['status'] = order['status']
        info['type'] = order['type']
        info['side'] = order['side']
        info['time'] = datetime.utcfromtimestamp(order['time'] / 1000) - timedelta(hours = 3)
        return info
