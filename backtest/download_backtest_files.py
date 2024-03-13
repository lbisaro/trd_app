#Importar modulos 
import pandas as pd
from binance.client import Client
import pickle
import os
from config import periodos,intervals
import datetime as dt

""" INFO """
"""
                #Como cargar un archivo .DataFrame 
                #Definir la ruta al archivo
                timeframe = '1m'
                file = timeframe+'/Alcista_BTCUSDT_'+timeframe+'_2020-09-07_2021-05-03.DataFrame'
                #Abrir archivo como lectura binaria
                with open(file, 'rb') as f:
                    #Cargar el dataframe
                    df_cargado = pickle.load(f)

                # Ahora df_cargado contiene el DataFrame que guardaste previamente
                df_cargado.tail()
"""




#Conexion con Binance sin API-KEY
client = Client()

#Funcion para descarga de velas
def get_klines(start,end,symbol,timeframe):
    df = client.get_historical_klines(symbol=symbol, interval=timeframe, start_str=start, end_str=end)
    df = pd.DataFrame(df)
    df = df.iloc[:, :6]
    df.columns = ["datetime", "open", "high", "low", "close", "volume"]
    df['open'] = df['open'].astype('float')
    df['high'] = df['high'].astype('float')
    df['low'] = df['low'].astype('float')
    df['close'] = df['close'].astype('float')
    df['volume'] = df['volume'].astype('float')
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') 
    #df=df.set_index('datetime')
    return df

#proceso para descarga de velas en los periodos definidos
for index, row in intervals.iterrows():

    interval_id = index
    interval = row['binance']
    minutes_back = row['minutes'] * 210  #Se agregan 210 velas previas para preparar los indicadores
    days_back = minutes_back/24/60

    folder = f'./backtest/klines/{interval_id}/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for p in periodos:
        tipo = p['tipo']
        start = p['start']
        end = p['end']
        real_start = (dt.datetime.strptime(start, "%Y-%m-%d") - dt.timedelta(minutes=minutes_back)).strftime("%Y-%m-%d")
        real_end = (dt.datetime.strptime(end, "%Y-%m-%d") ).strftime("%Y-%m-%d")
        utc_start = real_start+' 00:00:00'
        utc_end = real_end+' 23:59:59'
        
        for symbol in p['symbols']:
            file_dump = f'{folder}{tipo}_{symbol}_{interval_id}_{start}_{end}.DataFrame'
            print(file_dump,end=" ")
            if os.path.exists(file_dump):
                print(' -> Exists')
            else:
                print('')
                df = get_klines(utc_start,utc_end,symbol,interval)
                print(' -> Downloading OK',end=" ")
                with open(file_dump, 'wb') as f:
                    pickle.dump(df, f)
                print(' -> Create file OK')