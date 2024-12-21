from scripts.Exchange import Exchange
from bot.models import *
from bot.model_kline import *
import pickle
import os
from datetime import datetime, timedelta
from scripts.app_log import app_log as Log
from django.conf import settings

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

def run():
    print('Ejecución del script crontab_check_24hs_change.py')
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
    
    if 'alerts' not in data:
        data['alerts'] = {} 
    

    # Actualizar data de prices
    klines_downloaded = 0
    for symbol, price in actual_prices.items():
        if symbol not in data['symbols']:
            klines = exch.get_klines(symbol,'2d01',DIAS_HL)
            klines_downloaded += 1
            hl_data = klines[['datetime','high','low']].copy()
            hl_data['date'] = hl_data['datetime'].dt.strftime('%Y-%m-%d')
            hl_data.drop('datetime', axis=1, inplace=True)

            #Obtener el high y Low del registro actual
            high = hl_data.iloc[-1]['high']
            low = hl_data.iloc[-1]['low']

            #Eliminar los datos correspondientes a la fecha de proceso
            hl_data = hl_data[hl_data['date']<proc_date]

            symbol_info = {'date':proc_date,'price':price,'high':high,'low':low,'hl_data':hl_data}
            print('Descargando...',symbol)
        else:
            symbol_info = data['symbols'][symbol]
            symbol_info['price'] = price
            hl_data = symbol_info['hl_data']

            #Verificando que exista correlacion entre hl_data y proc_date
            check_hl_data = datetime.strptime(hl_data['date'].max(), '%Y-%m-%d').date()
            check_proc_date = datetime.strptime(proc_date, '%Y-%m-%d').date()
            diff_days = abs((check_proc_date - check_hl_data).days)
            if diff_days>1:
                del data['symbols'][symbol]
                print('ERROR en fechas',symbol,check_hl_data,check_proc_date)
                continue

            if symbol_info['date'] == proc_date:
                if price>symbol_info['high']:
                    symbol_info['high'] = price            
                elif price<symbol_info['low']:
                    symbol_info['low'] = price
            else: #Cambio de dia
                if hl_data['date'].count() == DIAS_HL: #hl_data completo
                    hl_data = hl_data.shift(-1)
                    hl_data.at[DIAS_HL-1,'date'] = symbol_info['date']
                    hl_data.at[DIAS_HL-1,'high'] = symbol_info['high']
                    hl_data.at[DIAS_HL-1,'low'] = symbol_info['low']
                else:
                    to_add = {'date': symbol_info['date'], 'high': symbol_info['high'], 'low': symbol_info['low']}
                    hl_data = pd.concat([hl_data, pd.DataFrame([to_add]) ], ignore_index=True)

                symbol_info['price'] = price
                symbol_info['high'] = price
                symbol_info['low'] = price
                symbol_info['hl_data'] = hl_data
            
            symbol_info['date'] = proc_date
        
        data['symbols'][symbol] = symbol_info

        if klines_downloaded > 5: #Limita la cantidad de symbols que se descargan por ciclo
            break

    print("Cantidad de symbols:",len(data['symbols']))
    print('proc_date:',proc_date)
    
    #Analisis de los datos
    for symbol, symbol_info in data['symbols'].items():
        hl_data = symbol_info['hl_data']
        price = symbol_info['price']
        high = symbol_info['high']
        low = symbol_info['low']
        if hl_data['date'].count()==DIAS_HL:
            hl_data_high = hl_data['high'].max()
            hl_data_low = hl_data['low'].min()
            hl_data_band = hl_data_high-hl_data_low
            hl_data_umbral = hl_data_high+hl_data_band/10

            if price > hl_data_umbral:
                alert_str = f'Price Change <b>{symbol}</b><br>Precio: {price}<br>High 20 dias: {hl_data_high}<br>Umbral: {hl_data_umbral}'
                if symbol not in data['alerts']:
                    log.alert(alert_str)
                    print(alert_str)
                data['alerts'][symbol] = alert_str                
            else:
                if symbol in data['alerts']:
                    del data['alerts'][symbol]
        else:
            if symbol in data['alerts']:
                del data['alerts'][symbol]

    data['updated'] = datetime.now().strftime('%d-%m-%Y %H:%M')
    data['proc_duration'] = round((datetime.now()-proc_start).total_seconds(),1)

    # Guardar data actualizados en binario
    save_data_file(DATA_FILE, data)