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

from scripts.indicators import zigzag,resample

# Configuraciones iniciales
LOG_DIR = os.path.join(settings.BASE_DIR,'log')
DATA_FILE = os.path.join(LOG_DIR, "pchange_data.pkl")
USDT_PAIR = "USDT"
DIAS_HL = 20

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

def ohlc_from_prices(prices,resample_period):
    df = pd.DataFrame({'close': prices})
    df['high'] = df['close']
    df['low'] = df['close']
    df['open'] = df['close'].shift()
    df['volume'] = 0.0
    now = datetime.now().replace(second=0, microsecond=0)  # Fecha y hora actuales
    intervalos = [now - timedelta(minutes=i) for i in range(len(df))]
    df['datetime'] = intervalos[::-1]  # Revertir el orden para que el último sea el actual

    df = resample(df,periods=resample_period)
    return df



def run():
    print('Ejecución del script crontab_check_price_change.py')
    log = Log('pchange')
    
    proc_date = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d')
    proc_start = datetime.now()
    # Inicializar cliente
    exch = Exchange(type='info', exchange='bnc', prms=None)

    # Obtener prices actuales
    actual_prices = {}
    tickers = exch.client.get_ticker()
    

    for ticker in tickers:
        symbol = ticker['symbol']
        close_time = datetime.fromtimestamp(ticker['closeTime']/1000)
        close_time = (close_time + timedelta(hours=3)).date()
        check_proc_date = datetime.strptime(proc_date, '%Y-%m-%d').date()

        diff_days = abs((check_proc_date - close_time).days)
        if symbol.endswith(USDT_PAIR) and diff_days==0:
            actual_prices[symbol] = float(ticker['lastPrice'])

    # Cargar data previos
    data = load_data_file(DATA_FILE)

    if 'symbols' not in data:
        data['symbols'] = {} 

    if 'alerts' in data:
        del data['alerts']
    
    if 'scan_pivots' in data:
        del data['scan_pivots'] 
    
    if 'log_alerts' not in data:
        data['log_alerts'] = {}

    # Actualizar data de prices
    klines_downloaded = 0
    for symbol, price in actual_prices.items():
        if symbol not in data['symbols']:
            klines = exch.get_klines(symbol,'2d01',DIAS_HL)
            klines_downloaded += 1
            hlc_1h = klines[['datetime','high','low','close']].copy()
            hlc_1h['date'] = hlc_1h['datetime'].dt.strftime('%Y-%m-%d')
            hlc_1h.drop('datetime', axis=1, inplace=True)

            #Obtener el high y Low del registro actual
            high = hlc_1h.iloc[-1]['high']
            low = hlc_1h.iloc[-1]['low']

            #Eliminar los datos correspondientes a la fecha de proceso
            hlc_1h = hlc_1h[hlc_1h['date']<proc_date]

            symbol_info = {'date':proc_date,'price':price,'high':high,'low':low,'hlc_1h':hlc_1h, 'c_1m':[price]}
            print('Descargado ',symbol)

        else:
            symbol_info = data['symbols'][symbol]
            symbol_info['price'] = price
            if 'c_1m' not in symbol_info:
                symbol_info['c_1m'] = []
            symbol_info['c_1m'].append(price)
            symbol_info['c_1m'] = symbol_info['c_1m'][-3000:]
            hlc_1h = symbol_info['hlc_1h']

            #Verificando que exista correlacion entre hlc_1h y proc_date
            check_hlc_1h = datetime.strptime(hlc_1h['date'].max(), '%Y-%m-%d').date()
            check_proc_date = datetime.strptime(proc_date, '%Y-%m-%d').date()
            diff_days = abs((check_proc_date - check_hlc_1h).days)
            if diff_days>2:
                del data['symbols'][symbol]
                print('ERROR en fechas',symbol,check_hlc_1h,check_proc_date)
                continue

            if symbol_info['date'] == proc_date:
                if price>symbol_info['high']:
                    symbol_info['high'] = price            
                elif price<symbol_info['low']:
                    symbol_info['low'] = price
            else: #Cambio de dia
                if hlc_1h['date'].count() == DIAS_HL: #hlc_1h completo
                    hlc_1h = hlc_1h.shift(-1)
                    hlc_1h.at[DIAS_HL-1,'date'] = symbol_info['date']
                    hlc_1h.at[DIAS_HL-1,'high'] = symbol_info['high']
                    hlc_1h.at[DIAS_HL-1,'low'] = symbol_info['low']
                    hlc_1h.at[DIAS_HL-1,'close'] = symbol_info['price']
                else:
                    to_add = {'date': symbol_info['date'], 'high': symbol_info['high'], 'low': symbol_info['low'], 'close': symbol_info['price']}
                    hlc_1h = pd.concat([hlc_1h, pd.DataFrame([to_add]) ], ignore_index=True)

                symbol_info['price'] = price
                symbol_info['high'] = price
                symbol_info['low'] = price
                symbol_info['hlc_1h'] = hlc_1h
            
            symbol_info['date'] = proc_date
        
        data['symbols'][symbol] = symbol_info

        if klines_downloaded > 5: #Limita la cantidad de symbols que se descargan por ciclo
            break

    if 'BTCUSDT' in data['symbols']:
        print("Cantidad de precios 1m:",len(data['symbols']['BTCUSDT']['c_1m']))
    print("Cantidad de symbols:",len(data['symbols']))
    
    #Limpiando el log de alertas
    time_limit = proc_start - timedelta(minutes=15)
    log_alerts = {}
    for symbol, alert in data['log_alerts'].items():
        if alert['datetime'] >= time_limit:
            log_alerts[symbol] = alert
    data['log_alerts'] = log_alerts
    
    #Analisis de los datos
    sent_alerts = 0
    for symbol, symbol_info in data['symbols'].items():
        hlc_1h = symbol_info['hlc_1h']
        price = symbol_info['price']
        high = symbol_info['high']
        low = symbol_info['low']

        #Escaneando precios para detectar tendencia
        prices = data['symbols'][symbol]['c_1m']
        resample_period = 15
        if len(prices)>=250:
            df = ohlc_from_prices(prices,resample_period)
            df = df[-250:]
            alert = get_pivots_alert(df)

            """
            🟢📈 LONG
            🔴📉 SHORT
            🔔 ALERTA
            """
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
    # Guardar data actualizados en binario
    
    save_data_file(DATA_FILE, data)

