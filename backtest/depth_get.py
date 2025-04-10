from binance import ThreadedDepthCacheManager
import time
import pickle
import os

dcm = ThreadedDepthCacheManager()
dcm.start()
print(f'Conectando al Exchange....', flush=True)
depth = {'bids_spot': [], 'asks_spot': [], 'bids_futures': [], 'asks_futures': []}
execution_time = 30  # segundos
symbol = 'BTCUSDT'

def handle_spot_message(depth_cache):
    global depth
    depth['bids_spot'] = depth_cache.get_bids()
    depth['asks_spot'] = depth_cache.get_asks()

def handle_futures_message(depth_cache):
    global depth
    depth['bids_futures'] = depth_cache.get_bids()
    depth['asks_futures'] = depth_cache.get_asks()
    

spot_name = dcm.start_depth_cache(callback=handle_spot_message, symbol=symbol)
futures_name = dcm.start_futures_depth_socket(callback=handle_futures_message, symbol=symbol)

start_time = time.time()

try:
    while time.time() - start_time < execution_time:
        progress = int(((time.time() - start_time)/execution_time)*100)
        if progress>100:
            progress = 100
        lens = [len(depth['bids_spot']),len(depth['asks_spot']),len(depth['bids_futures']),len(depth['asks_futures'])]
        print(f'\rObteniendo Bids y Asks [{progress} %] {lens}',end='', flush=True)
        time.sleep(0.1)  
finally:
    # Esto se ejecutará cuando termine el tiempo o si hay una interrupción
    dcm.stop_socket(spot_name)
    dcm.stop_socket(futures_name)
    dcm.stop()
    time.sleep(3)
    lens = [len(depth['bids_spot']),len(depth['asks_spot']),len(depth['bids_futures']),len(depth['asks_futures'])]
    print(f'\rObteniendo Bids y Asks [100 %] {lens}',flush=True)

    #Almacenando la data del depth en un archivo de log
    LOG_DIR = os.path.join('..','log')
    DATA_FILE = os.path.join(LOG_DIR, f"depth_{symbol}.pkl")
    print('Registrando datos en: ',DATA_FILE)

    # Crear directorio de logs si no existe
    os.makedirs(LOG_DIR, exist_ok=True)

    with open(DATA_FILE, "wb") as archivo:
        pickle.dump(depth, archivo)

