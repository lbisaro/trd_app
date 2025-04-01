from binance import Client, ThreadedDepthCacheManager
import time
import pickle
import os

# Variables api_key y api_secret ya definidas previamente
client = Client()

dcm = ThreadedDepthCacheManager()
dcm.start()
print(f'Conectando al Exchange....', flush=True)
depth = {'bids': [], 'asks': []}
execution_time = 180  # segundos
symbol = 'BTCUSDT'

def handle_dcm_message(depth_cache):
    global depth
    depth['bids'] = depth_cache.get_bids()
    depth['asks'] = depth_cache.get_asks()

dcm_name = dcm.start_depth_cache(callback=handle_dcm_message, symbol=symbol)

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
    dcm.stop_socket(dcm_name)
    dcm.stop()
    time.sleep(3)
    print(f'\rObteniendo Bids y Asks [100 %]',flush=True)

    #Almacenando la data del depth en un archivo de log
    LOG_DIR = os.path.join('..','log')
    DATA_FILE = os.path.join(LOG_DIR, f"depth_{symbol}.pkl")
    print('Registrando datos en: ',DATA_FILE)

    # Crear directorio de logs si no existe
    os.makedirs(LOG_DIR, exist_ok=True)

    with open(DATA_FILE, "wb") as archivo:
        pickle.dump(depth, archivo)

    
    