import time
import pickle
import os
from datetime import datetime, timedelta
from django.conf import settings

from scripts.OrderBookAnalizer import OrderBookAnalyzer

from binance import ThreadedDepthCacheManager

depth = {'bids': [], 'asks': []}
execution_time = 180  # segundos
symbol = 'BTCUSDT'
def handle_dcm_message(depth_cache):
    global depth
    depth['bids'] = depth_cache.get_bids()
    depth['asks'] = depth_cache.get_asks()

def run():

    #Control de ejecucion
    startDt = datetime.now()+timedelta(hours=3)
    hh = startDt.strftime('%H')
    mm = startDt.strftime('%M')

    if mm == '00' or mm == '30': #Cada 30 minutos
        
        global execution_time, symbol
        dcm = ThreadedDepthCacheManager()
        dcm.start()
        print(f'Conectando al Exchange....', flush=True)



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
            LOG_DIR = os.path.join(settings.BASE_DIR,'log')
            DATA_FILE = os.path.join(LOG_DIR, f"order_book_{symbol}.pkl")
            print('Registrando datos en: ',DATA_FILE)

            # Crear directorio de logs si no existe
            os.makedirs(LOG_DIR, exist_ok=True)

            with open(DATA_FILE, "wb") as archivo:
                pickle.dump(depth, archivo)

            bids = depth['bids']
            asks = depth['asks']

            DATA_FILE = os.path.join(LOG_DIR, f"order_book_{symbol}_historic.pkl")
            analyzer = OrderBookAnalyzer(DATA_FILE)
            analysis_result = analyzer.analyze_order_book(bids, asks)

            print("Análisis completado. Resumen:")
            print(f"Precio base: {analysis_result['base_price']}")
            print(f"Desbalance del mercado: {analysis_result['market_imbalance']['imbalance_pct']:.2f}%")
            print(f"Soportes significativos encontrados: {len(analysis_result['bid_supports']['levels'])}")
            for s in analysis_result['bid_supports']['levels']:
                print(f"{s['price']}", f"{s['volume_pct']:.2f} %")
            print(f"Resistencias significativas encontradas: {len(analysis_result['ask_resistances']['levels'])}")
            for s in analysis_result['ask_resistances']['levels']:
                print(f"{s['price']}", f"{s['volume_pct']:.2f} %")
            