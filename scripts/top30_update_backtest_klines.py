import pandas as pd
import numpy as np
import pickle
import datetime as dt
import os
import glob

from bot.model_kline import Symbol
from binance.client import Client

client = Client()

tipo = 'top30'
klines_start = '2023-01-01'
klines_end = '2025-11-07'
top30_file = f'./backtest/klines/1h01/{tipo}_TOP30_1h01_{klines_start}_{klines_end}.DataFrame'
backtest_symbols = ['BTCUSDT','ETHUSDT','BNBUSDT','TRXUSDT',]

def get_klines(symbol,interval,start,end):
    print('Descargando velas',symbol, interval, start, end )
    df = client.get_historical_klines(symbol=symbol, interval=interval, start_str=start, end_str=end)
    df = pd.DataFrame(df)
    df = df.iloc[:, :6]
    df.columns = ["datetime", "open", "high", "low", "close", "volume"]
    df['open'] = df['open'].astype('float')
    df['high'] = df['high'].astype('float')
    df['low'] = df['low'].astype('float')
    df['close'] = df['close'].astype('float')
    df['volume'] = df['volume'].astype('float')
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') - dt.timedelta(hours=3)
    return df


def download_top30_files(top30_symbols):
    return download_files(top30_symbols, interval_id = '1h01', interval = '1h')

def download_backtest_files(backtest_symbols):
    return download_files(backtest_symbols, interval_id = '0m01', interval = '1m')

def download_files(symbols,interval_id,interval):
    max_klines = 0
    hours_back = 210 * 24
    
    folder = f'./backtest/klines/{interval_id}/'

    real_start = (dt.datetime.strptime(klines_start, "%Y-%m-%d") - dt.timedelta(hours=hours_back)).strftime("%Y-%m-%d")
    real_end = (dt.datetime.strptime(klines_end, "%Y-%m-%d") ).strftime("%Y-%m-%d")
    utc_start = real_start+' 00:00:00'
    utc_end = real_end+' 23:59:59'

    print(utc_start,utc_end)
    
    for symbol in symbols:
        file_dump = f'{folder}{tipo}_{symbol}_{interval_id}_{klines_start}_{klines_end}.DataFrame'
        print('File Dump:',file_dump,end=" ")

        #verificando si existe algun archivo 
        patron = file_dump.replace(klines_start,'*')
        patron = patron.replace(klines_end,'*')
        exists_data = glob.glob(patron)
        exists_data = [str(p.replace('\\', '/')) for p in exists_data]

        #Si el archivo ya existe
        if file_dump in exists_data:
            with open(file_dump, 'rb') as f:
                df = pickle.load(f)
                if max_klines == 0:
                    max_klines = len(df)
                qty_klines = len(df)
            print(f' -> Exists {qty_klines}')

        #Si no existe informacion previa
        else: 
            print('')
            df = get_klines(symbol,interval,utc_start,utc_end)
            print(' -> Records ',len(df),end=" ")
            print(' -> Downloading OK',end=" ")
            if max_klines == 0:
                max_klines = len(df)
            else:
                if len(df) != max_klines:
                    print('From',df.iloc[0]['datetime'],'To',df.iloc[-1]['datetime'])
                    print(" ****************************** ")
                    print(" ERROR EN CANTIDAD DE REGISTROS ")
                    print(" ****************************** ")
                    return False
                
            with open(file_dump, 'wb') as f:
                pickle.dump(df, f)
            print(' -> Create file OK') 

        #Eliminando los datos innecesarios
        exists_data = glob.glob(patron)
        exists_data = [str(p.replace('\\', '/')) for p in exists_data]
        for f in exists_data:
            if f != file_dump:
                print(f' -> Eliminando archivo {f}')
                os.remove(f)
    return True

def procces_klines_files(top30):


    data = pd.DataFrame(columns=['datetime'])
    symbols_len = len(top30)
    symbols_rec = 0
    for symbol in top30:
        symbols_rec += 1
        klines_file  = f'./backtest/klines/1h01/{tipo}_{symbol}_1h01_{klines_start}_{klines_end}.DataFrame'
        with open(klines_file, 'rb') as file:
            df = pickle.load(file)
            print(f'Procesando {symbol}    {symbols_rec}/{symbols_len}       ',end='\r')

            if len(data)==0:
                data['datetime'] = df['datetime']
                
            df.set_index('datetime',inplace=True)
            # Paso 1: Obtener los precios de cierre de las velas de 4H ya completadas
            # Usamos resample('4H').last() para obtener el último precio de cierre de cada bloque de 4 horas.
            close_4h = df['close'].resample('4H').last()

            # Paso 2: Definir la función que hará el cálculo para cada vela de 1H
            def calculate_intra_bar_sma(row, series_4h_closes, period):
                """
                Calcula la SMA de 4H para una vela de 1H específica.
                
                Args:
                    row (pd.Series): La fila del dataframe de 1H. El índice debe ser el timestamp.
                    series_4h_closes (pd.Series): La serie con los cierres de las velas de 4H.
                    period (int): El período de la SMA (en este caso, 60).
                """
                current_time = row.name
                current_close = row['close']
                
                # Identificar el inicio del bloque de 4H al que pertenece la vela actual
                current_4h_block_start = current_time.floor('4H')
                
                # Obtener los cierres de las velas de 4H que se completaron ANTES del bloque actual
                previous_4h_closes = series_4h_closes[series_4h_closes.index < current_4h_block_start]
                
                # Necesitamos los últimos (periodo - 1) cierres, es decir, 59
                if len(previous_4h_closes) < period - 1:
                    return np.nan # No hay suficientes datos históricos
                    
                last_59_closes = previous_4h_closes.tail(period - 1)
                
                # Creamos una serie con el cierre actual para concatenarlo
                current_value_series = pd.Series([current_close])
                
                # Combinamos los 59 cierres históricos con el cierre de la vela de 1H actual
                values_for_sma = pd.concat([last_59_closes, current_value_series])
                
                # Calculamos y devolvemos la media
                return values_for_sma.mean()

            # Paso 3: Aplicar la función a cada fila del DataFrame de 1H
            # Esto puede tardar un poco en dataframes muy grandes, pero es la forma más precisa de simularlo.

            df['sma_4h'] = df.apply(
                calculate_intra_bar_sma, 
                axis=1, # Aplicar por filas
                series_4h_closes=close_4h, 
                period=60
            )

            df.reset_index(inplace=True)
            data[f'{symbol}_c'] = df['close']
            data[f'{symbol}_m'] = df['sma_4h']
            data[f'{symbol}_ta'] = np.where(df['close']>df['sma_4h'],1,0)
        
    print('')

    ta_columns = []
    for symbol in top30:
        ta_columns.append(f'{symbol}_ta')

    data['ta_sum'] = data[ta_columns].sum(axis=1)
    data['breadth'] = (data['ta_sum']/len(ta_columns))*100

    with open(top30_file, 'wb') as f:
        pickle.dump(data, f)
    print('Grabando archivo')
    
    patron = top30_file.replace(klines_start,'*')
    patron = patron.replace(klines_end,'*')
    lista_de_archivos = glob.glob(patron)
    lista_de_archivos = [ruta.replace('\\', '/') for ruta in lista_de_archivos]

    for f in lista_de_archivos:
        if f != top30_file:
            print(f' -> Eliminando archivo {f}')
            os.remove(f)

def run():
        #'GNSUSDT' 2023-02-17,
        #'RPLUSDT' 2023-01-18,
        #'NEXOUSDT' 2022-04-29,
        #'GLMRUSDT' 2022-01-11,
        #'MCUSDT' 2021-12-02,
        #'ALCXUSDT' 2021-11-30,
        #'RNDRUSDT' 2021-11-27,
        #'PYRUSDT' 2021-11-26,
        #'QNTUSDT' 2021-07-29,
        #'ARUSDT' 2021-05-14,
        #'1INCHUSDT' 2020-12-25,
        #'GRTUSDT' 2020-12-17,
        #'AAVEUSDT' 2020-10-15,
        #'AVAXUSDT' 2020-09-22,
        #'OCEANUSDT' 2020-08-19,
        #'DOTUSDT' 2020-08-18,
        #'CRVUSDT' 2020-08-15,
        #'SOLUSDT' 2020-08-11,
        #'MANAUSDT' 2020-08-06 ,
        #'DCRUSDT' 2020-07-30,
        #'NEARUSDT' 2020-10-14,
    #top30_symbols = [
    #    #'BTCUSDT',
    #    'ADAUSDT', 'ALGOUSDT', 'ATOMUSDT', 'BCHUSDT', 'DASHUSDT',
    #    'DOGEUSDT','ETCUSDT', 'FETUSDT', 'HBARUSDT', 'IOTAUSDT',
    #    'LINKUSDT', 'LTCUSDT', 'ZECUSDT', 'STXUSDT', 'THETAUSDT',
    #    'VETUSDT', 'XLMUSDT', 'XMRUSDT', 'XRPUSDT', 'XTZUSDT',
    #    'MATICUSDT', 
    #        ]

    #top30_symbols = Symbol.getTop30Symbols()
    #top30_symbols.remove('LUNCUSDT')
    #top30_symbols.remove('RONINUSDT')
    #top30_symbols.remove('POLUSDT')
    #top30_symbols.remove('USUALUSDT')
    #top30_symbols.remove('WBTCUSDT')
    #top30_symbols.remove('SUIUSDT')
    #top30_symbols.remove('PEPEUSDT')
    #top30_symbols.remove('APTUSDT')
    #top30_symbols.remove('WLDUSDT')
    
    #top30_symbols.remove('BNBUSDT')
    #top30_symbols.remove('ETHUSDT')
    #top30_symbols.remove('TRXUSDT')

    top30_symbols = [
        'AAVEUSDT',
        'ADAUSDT',
        'ATOMUSDT',
        'AVAXUSDT',
        'AXSUSDT',
        'BCHUSDT',
        'DOGEUSDT',
        'DOTUSDT',
        'ETCUSDT',
        'FETUSDT',
        'FILUSDT',
        'GRTUSDT',
        'HBARUSDT',
        'ICPUSDT',
        'INJUSDT',
        'LINKUSDT',
        'LTCUSDT',
        'MANAUSDT',
        'NEARUSDT',
        'OPUSDT',
        'SANDUSDT',
        'SHIBUSDT',
        'SOLUSDT',
        'THETAUSDT',
        'UNIUSDT',
        'VETUSDT',
        'XLMUSDT',
        'XRPUSDT',
        'XTZUSDT',
        'LUNAUSDT',
        'ZECUSDT',
        'ALGOUSDT',
        'PAXGUSDT',
        'QNTUSDT',
        'DASHUSDT',
        'IMXUSDT',
        'CAKEUSDT',
        'STXUSDT',
        'LDOUSDT',
        'NEXOUSDT',
        'PONDUSDT',
    ]

    top30_symbols = top30_symbols[:30]

    if download_top30_files(top30_symbols):
        print('Se ha completado la descarga de velas para el Top30')
        if download_backtest_files(backtest_symbols):
            print('Se ha completado la descarga de velas para el Backtesting')

            procces_klines_files(top30_symbols)
        
        else:

            print(' ************************************************************** ')
            print(' SE HAN ENCONTRADO ERRORES EN LOS ARCHIVOS DE DATOS DE BACKTEST ')
            print(' ************************************************************** ')
            

    else:

        print(' *********************************************************** ')
        print(' SE HAN ENCONTRADO ERRORES EN LOS ARCHIVOS DE DATOS DE VELAS ')
        print(' *********************************************************** ')




