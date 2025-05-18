import pandas as pd
import numpy as np
from scripts.Exchange import Exchange
from scripts.indicators import get_pivots_alert
import pickle
import json
import os
from datetime import datetime, timedelta
from scripts.app_log import app_log as Log
from django.conf import settings

from scripts.indicators import resample

# Configuraciones iniciales
LOG_DIR = os.path.join(settings.BASE_DIR,'log')
DATA_FILE = os.path.join(LOG_DIR, "futures_alerts_data.pkl")
USDT_PAIR = "USDT"
LIMIT_MINUTES = 3000
KLINES_TO_GET_ALERTS = 100

# Crear directorio de logs si no existe
os.makedirs(LOG_DIR, exist_ok=True)

def save_data_file(ruta, data):
    with open(ruta, "wb") as archivo:
        pickle.dump(data, archivo)

def load_data_file(ruta):
    try:
        if os.path.exists(ruta):
            with open(ruta, "rb") as archivo:
                return pickle.load(archivo)
    except Exception as e:
        print(f"Error al cargar el archivo {ruta}: {e}")
    return {}

def ohlc_from_prices(datetime, prices,resample_period):

    df = pd.DataFrame({'datetime': datetime, 'close': prices, })
    df['high'] = df['close']
    df['low'] = df['close']
    df['open'] = df['close'].shift() 
    df['volume'] = 0.0
    df.at[0,'open'] = prices[0]
    if resample_period > 1:
        df = resample(df,periods=resample_period)
    return df

def run():
    print('Ejecución del script crontab_futures_alerts.py')
    log = Log('futures_alerts')
        
    proc_start = (datetime.now().strftime('%Y-%m-%d %H:%M'))
    proc_start = datetime.strptime(proc_start, "%Y-%m-%d %H:%M")
    # Inicializar cliente
    exch = Exchange(type='info', exchange='bnc', prms=None)

    # Obtener prices actuales
    actual_prices = {}
    tickers = exch.client.futures_symbol_ticker()
    for ticker in tickers:
        symbol = ticker['symbol']
        if symbol.endswith(USDT_PAIR):
            actual_prices[symbol] = float(ticker['price'])

    # Cargar data previos
    data = load_data_file(DATA_FILE)
    
    #datetime almacena la fecha y hora del proces en minutos
    if 'datetime' not in data:
        data['datetime'] = [proc_start]
    else:
        #Verifica si el ultimo registro generado tiene diferencia de 1 minuto
        if proc_start-data['datetime'][-1] > timedelta(minutes=1):
            print('Existe mas de 1 minuto entre el ultimo registro y el actual. Se reinicia el archivo de datos')
            data = {}
            data['datetime'] = [proc_start]
        else:
            data['datetime'].append(proc_start)
            data['datetime'] = data['datetime'][-LIMIT_MINUTES:]
            
    #symbols almacena el precio de cada symbol en minutos 
    if 'symbols' not in data:
        data['symbols'] = {} 
    
    if 'log_alerts' not in data:
        data['log_alerts'] = {}

    # Actualizar data de prices
    registros_datetime = len(data['datetime'])
    for symbol, price in actual_prices.items():
        if symbol not in data['symbols']:
            c_1m = [None] * registros_datetime
            symbol_info = {'c_1m':c_1m}
        else:
            symbol_info = data['symbols'][symbol]
            if 'c_1m' not in symbol_info:
                c_1m = [None] * registros_datetime
                symbol_info['c_1m'] = c_1m
        symbol_info['c_1m'].append(price)
        symbol_info['c_1m'] = symbol_info['c_1m'][-registros_datetime:]
            
        
        data['symbols'][symbol] = symbol_info


    print("Cantidad de registros:",len(data['datetime']))
    print("Cantidad de symbols:",len(data['symbols']))
    
    #Limpiando el log de alertas
    time_limit = proc_start - timedelta(minutes=60)
    log_alerts = {}
    for symbol, alert in data['log_alerts'].items():
        if alert['datetime'] >= time_limit:
            log_alerts[symbol] = alert
    data['log_alerts'] = log_alerts
    

    #Analisis de los datos para alertas
    sent_alerts = 0
    qty_len_ok = 0
    qty_df = 0
    qty_check_alert = 0
    for symbol, symbol_info in data['symbols'].items():

        #Escaneando precios para detectar alertas
        prices = data['symbols'][symbol]['c_1m']
        resample_period = 15
        if len(data['datetime'])>=KLINES_TO_GET_ALERTS*resample_period:
            qty_len_ok += 1
            try:
                df = ohlc_from_prices(data['datetime'],prices,resample_period)
                qty_df += 1
            except:
                break
            df = df[-KLINES_TO_GET_ALERTS:]
            alert = get_pivots_alert(df)
            if alert != 0:
                qty_check_alert += 1
            # 🟢📈 LONG
            # 🔴📉 SHORT
            # 🔔 ALERTA
            
            if alert['alert'] == 1:

                trend_msg = alert['alert_str']
                alert_alert = alert['alert']
                alert_in_price = alert['in_price']
                alert_tp1 = alert['tp1']
                alert_sl1 = alert['sl1']

                alert_str = f'🟢📈 <b>LONG</b> Scanner {resample_period}m <b>{symbol}</b>'+\
                            f'\nPrecio de entrada: {alert_in_price}'+\
                            f'\nTake Profit: {alert_tp1}'+\
                            f'\nStop Loss: {alert_sl1}'+\
                            f'\n{trend_msg}'
                alert_key = f'{symbol}.{alert_alert}'
                if alert_key not in data['log_alerts']:
                    log.alert(alert_str)
                    sent_alerts += 1 
                    alert['start'] = proc_start
                else:
                    alert['start'] = data['log_alerts'][alert_key]['start']
                alert['origin'] = trend_msg
                alert['symbol'] = symbol
                alert['timeframe'] = f'{resample_period}m'
                alert['alert_str'] = alert_str
                alert['datetime'] = proc_start
                alert['price'] = price

                data['log_alerts'][alert_key] = alert

            elif alert['alert'] == -1:

                trend_msg = alert['alert_str']
                alert_alert = alert['alert']
                alert_in_price = alert['in_price']
                alert_tp1 = alert['tp1']
                alert_sl1 = alert['sl1']

                alert_str = f'🔴📉 <b>SHORT</b> Scanner {resample_period}m <b>{symbol}</b>'+\
                            f'\nPrecio de entrada: {alert_in_price}'+\
                            f'\nTake Profit: {alert_tp1}'+\
                            f'\nStop Loss: {alert_sl1}'+\
                            f'\n{trend_msg}'
                alert_key = f'{symbol}.{alert_alert}'
                if alert_key not in data['log_alerts']:
                    log.alert(alert_str)
                    sent_alerts += 1 
                    alert['start'] = proc_start
                else:
                    alert['start'] = data['log_alerts'][alert_key]['start']

                alert['origin'] = trend_msg
                alert['symbol'] = symbol
                alert['timeframe'] = f'{resample_period}m'
                alert['alert_str'] = alert_str
                alert['datetime'] = proc_start
                alert['price'] = price

                data['log_alerts'][alert_key] = alert

        if sent_alerts > 5:
            break

    data['updated'] = datetime.now().strftime('%d-%m-%Y %H:%M')
    data['proc_duration'] = round((datetime.now()-proc_start).total_seconds(),1)
    

    print('qty_len_ok:',qty_len_ok)
    print('qty_df:',qty_df)
    print('qty_check_alert:',qty_check_alert)
    # Guardar data actualizados en binario
    save_data_file(DATA_FILE, data)

