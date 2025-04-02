from binance import AsyncClient, ThreadedWebsocketManager, ThreadedDepthCacheManager
import time
import pickle
import os

#dcm = ThreadedDepthCacheManager()
#dcm.start()
twm = ThreadedWebsocketManager()
twm.start()

print(f'Conectando al Exchange....', flush=True)
depth = {'bids': [], 'asks': [], }
price = {'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0}
execution_time = 30  # segundos
symbol = 'BTCUSDT'

#def handle_dcm_message(msg):
#    global depth
#    depth['bids'] = msg.get_bids()
#    depth['asks'] = msg.get_asks()

def handle_twm_message(msg):
    global depth,price
    if msg['e'] == 'depthUpdate' and 'b' in msg['e']:
        depth['bids'] = msg['e']['b']
        depth['asks'] = msg['e']['a']
    elif msg['e'] == 'kline' and 'k' in msg['e']:
        price['close'] = msg['k']['c']
        price['volume'] = msg['k']['q']
        if price['high'] == 0.0 or msg['k']['h']>price['high']:
            price['high'] = msg['k']['h']
        if price['low'] == 0.0 or msg['k']['l']<price['low']:
            price['low'] = msg['k']['l']
        
        print('\n',price['close'],'\t',price['high'],'\t',price['low'],'\t',price['volume'],flush=True)


#dcm_name = dcm.start_depth_cache(callback=handle_dcm_message, symbol=symbol)
kline_name = twm.start_kline_socket(callback=handle_twm_message, symbol=symbol, interval=AsyncClient.KLINE_INTERVAL_30MINUTE)
depth_name = twm.start_depth_socket(callback=handle_twm_message, symbol=symbol)

start_time = time.time()

try:
    while time.time() - start_time < execution_time:
        progress = int(((time.time() - start_time)/execution_time)*100)
        if progress>100:
            progress = 100
        print(f'\rObteniendo Bids y Asks [{progress} %]',end='', flush=True)
        time.sleep(0.1)  
finally:
    # Esto se ejecutará cuando termine el tiempo o si hay una interrupción
    #dcm.stop_socket(dcm_name)
    #dcm.stop()
    twm.stop_socket(kline_name)
    twm.stop_socket(depth_name)
    twm.stop
    time.sleep(3)
    print(f'\rObteniendo Bids y Asks [100 %]',flush=True)

    """
    #Almacenando la data del depth en un archivo de log
    LOG_DIR = os.path.join('..','log')
    DATA_FILE = os.path.join(LOG_DIR, f"depth_{symbol}.pkl")
    print('Registrando datos en: ',DATA_FILE)

    # Crear directorio de logs si no existe
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(DATA_FILE, "wb") as archivo:
        pickle.dump(depth, archivo)
    """
    
    