import pandas as pd
import numpy as np
from scripts.Exchange import Exchange
from scripts.indicators import get_pivots_alert
import pickle
import json
import os
from datetime import datetime, timedelta
from scripts.app_log import app_log as Log
from scripts.functions import get_intervals
from django.conf import settings

from scripts.indicators import resample

# Configuraciones iniciales
LOG_DIR = os.path.join(settings.BASE_DIR,'log')
DATA_FILE = os.path.join(LOG_DIR, "futures_alerts_data.pkl")
USDT_PAIR = "USDT"
LIMIT_MINUTES = 3000
KLINES_TO_GET_ALERTS = 50
INTERVAL_ID = '0m15'
ALERT_THRESHOLD = 1.5

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

def timedelta_a_minutos(delta):
    """Convierte timedelta a minutos con precisión"""
    return delta.total_seconds() / 60

def ohlc_from_prices(datetime, prices,interval_minutes):

    df = pd.DataFrame({'datetime': datetime, 'close': prices, })
    df['high'] = df['close']
    df['low'] = df['close']
    df['open'] = df['close'].shift() 
    df['volume'] = 0.0
    df.at[0,'open'] = prices[0]
    if interval_minutes > 1:
        df = resample(df,periods=interval_minutes)
    return df

def alert_add_data(alert, actual_price):
    alert['actual_price_legend'] = ''
    alert['actual_price_class'] = ''  
    alert['status_class'] = 'status_ok'
    if alert['side'] == 1: #LONG
        alert['class'] = 'success'
        alert['tp1_perc'] = round((alert['tp1']/alert['in_price']-1)*100,2)
        alert['sl1_perc'] = round((alert['sl1']/alert['in_price']-1)*100,2)
        actual_price_perc = round((actual_price/alert['in_price']-1)*100,2)
        if actual_price > alert['tp1'] or actual_price < alert['sl1']:
            alert['actual_price_legend'] = 'El precio actual se encuentra fuera de rango'
            alert['actual_price_class'] = 'text-danger'
            alert['status_class'] = 'status_out'
        elif abs(actual_price_perc) < alert['tp1_perc']/3:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-success'
        else:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-warning'
            alert['status_class'] = 'status_out'

    else:   #SHORT
        alert['class'] = 'danger'
        alert['tp1_perc'] = round((alert['in_price']/alert['tp1']-1)*100,2)
        alert['sl1_perc'] = round((alert['in_price']/alert['sl1']-1)*100,2)
        actual_price_perc = round((alert['in_price']/actual_price-1)*100,2)
        if actual_price < alert['tp1'] or actual_price > alert['sl1']:
            alert['actual_price_legend'] = 'El precio actual se encuentra fuera de rango'
            alert['actual_price_class'] = 'text-danger'
            alert['status_class'] = 'status_out'
        elif abs(actual_price_perc) < alert['tp1_perc']/3:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-success'
        else:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-warning'
            alert['status_class'] = 'status_out'

            
        

    return alert

def run():
    print('Ejecución del script crontab_futures_alerts.py')
    log = Log('futures_alerts')
        
    proc_start = (datetime.now().strftime('%Y-%m-%d %H:%M'))
    proc_start = datetime.strptime(proc_start, "%Y-%m-%d %H:%M")
    # Inicializar cliente
    exchInfo = Exchange(type='info', exchange='bnc', prms=None)

    # Obtener prices actuales
    actual_prices = {}
    tickers = exchInfo.client.futures_symbol_ticker()
    for ticker in tickers:
        symbol = ticker['symbol']
        if symbol.endswith(USDT_PAIR):
            actual_prices[symbol] = float(ticker['price'])

    # Cargar data previos
    data = load_data_file(DATA_FILE)
    
    #datetime almacena la fecha y hora del proceso en minutos
    lost_minutes = 0
    if 'datetime' not in data:
        data['datetime'] = [proc_start]
    else:
        #Verifica si el ultimo registro generado tiene diferencia de 1 minuto
        lost_minutes_ok = 30
        lost_minutes = timedelta_a_minutos(proc_start-data['datetime'][-1])-1
        if lost_minutes > timedelta_a_minutos(timedelta(minutes=lost_minutes_ok)):
            log.error(f'LOST DATA - Period {lost_minutes} minutes - From '+proc_start.strftime('%Y-%m-%d %H:%M')+' to '+data['datetime'][-1].strftime('%Y-%m-%d %H:%M'))
            print(f'Existe mas de {lost_minutes_ok} minutos entre el ultimo registro y el actual. Se reinicia el archivo de datos')
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
    analized_symbols = 0
    for symbol, symbol_info in data['symbols'].items():

        #Escaneando precios para detectar alertas
        prices = data['symbols'][symbol]['c_1m']
        interval_minutes = get_intervals(INTERVAL_ID,'minutes')
        interval_binance = get_intervals(INTERVAL_ID,'binance')

        if len(data['datetime'])>=KLINES_TO_GET_ALERTS*interval_minutes:
            try:
                df = ohlc_from_prices(data['datetime'],prices,interval_minutes)
            except:
                break
            df_last100 = df[-100:]
            last100_high = df_last100['high'].max()
            last100_min = df_last100['low'].min()
            variacion_pct = (last100_high - last100_min) / last100_min * 100
            if abs(variacion_pct) >= 2:
                analized_symbols += 1
                df = df[-200:]
                alert = get_pivots_alert(df,threshold=ALERT_THRESHOLD)
                
                # 🟢📈 LONG
                # 🔴📉 SHORT
                # 🔔 ALERTA

                binance_link = f'<a href="https://www.binance.com/es-LA/futures/{symbol}">Ir a Binance Futures</a>'

                if alert['alert'] != 0:
                    alert = alert_add_data(alert,actual_prices[symbol])
                    trend_msg = alert['alert_str']
                    alert_alert = alert['alert']
                    alert_in_price = alert['in_price']
                    alert_tp1 = alert['tp1']
                    alert_sl1 = alert['sl1']
                    alert_tp1_perc = alert['tp1_perc']
                    alert_sl1_perc = alert['sl1_perc']
                    alert_actual_price_legend = alert['actual_price_legend']
                
                if alert['alert'] == 1:

                    alert_str = f'🟢 <b>LONG</b> Scanner {interval_binance} <b>{symbol}</b>'+\
                                f'\nPrecio de entrada: {alert_in_price}'+\
                                f'\nTake Profit: {alert_tp1} ({alert_tp1_perc}%)'+\
                                f'\nStop Loss: {alert_sl1} ({alert_sl1_perc}%)'+\
                                f'\n{trend_msg}'+\
                                f'\n{alert_actual_price_legend}'+\
                                f'\n{binance_link}'
                    alert_key = f'{symbol}.{alert_alert}'
                    if alert_key not in data['log_alerts']:
                        log.alert(alert_str)
                        sent_alerts += 1 
                        alert['start'] = proc_start
                    else:
                        alert['start'] = data['log_alerts'][alert_key]['start']
                    alert['origin'] = trend_msg
                    alert['symbol'] = symbol
                    alert['timeframe'] = f'{interval_binance}'
                    alert['alert_str'] = alert_str
                    alert['datetime'] = proc_start
                    alert['price'] = price

                    data['log_alerts'][alert_key] = alert

                elif alert['alert'] == -1:
                    alert_str = f'🔴 <b>SHORT</b> Scanner {interval_binance} <b>{symbol}</b>'+\
                                f'\nPrecio de entrada: {alert_in_price}'+\
                                f'\nTake Profit: {alert_tp1} ({alert_tp1_perc}%)'+\
                                f'\nStop Loss: {alert_sl1} ({alert_sl1_perc}%)'+\
                                f'\n{trend_msg}'+\
                                f'\n{alert_actual_price_legend}'+\
                                f'\n{binance_link}'
                    alert_key = f'{symbol}.{alert_alert}'
                    if alert_key not in data['log_alerts']:
                        log.alert(alert_str)
                        sent_alerts += 1 
                        alert['start'] = proc_start
                    else:
                        alert['start'] = data['log_alerts'][alert_key]['start']

                    alert['origin'] = trend_msg
                    alert['symbol'] = symbol
                    alert['timeframe'] = f'{interval_binance}'
                    alert['alert_str'] = alert_str
                    alert['datetime'] = proc_start
                    alert['price'] = price

                    data['log_alerts'][alert_key] = alert

        if sent_alerts > 5:
            break

    data['updated'] = datetime.now().strftime('%d-%m-%Y %H:%M')
    data['analized_symbols'] = analized_symbols
    data['proc_duration'] = round((datetime.now()-proc_start).total_seconds(),1)
    

    # Guardar data actualizados en binario
    save_data_file(DATA_FILE, data)

