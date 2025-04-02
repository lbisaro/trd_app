import time
import pickle
import os
from datetime import datetime, timedelta
from django.conf import settings

from scripts.OrderBookAnalizer import OrderBookAnalyzer

from binance import AsyncClient, ThreadedWebsocketManager

depth = {'bids': [], 'asks': []}
price = {'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0}
execution_time = 180  # segundos
symbol = 'BTCUSDT'

def handle_twm_message(msg):
    global depth,price
    if msg['e'] == 'depthUpdate':
        depth['bids'] = msg['b']
        depth['asks'] = msg['a']
    elif msg['e'] == 'kline' and 'k' in msg['e']:
        high = float(msg['k']['h'])
        low = float(msg['k']['l'])
        close = float(msg['k']['c'])
        volume = float(msg['k']['q'])
        price['close'] = close
        price['volume'] = volume
        if price['high'] == 0.0 or high>price['high']:
            price['high'] = high
        if price['low'] == 0.0 or low<price['low']:
            price['low'] = low

def run():

    #Control de ejecucion
    startDt = datetime.now()+timedelta(hours=3)
    hh = startDt.strftime('%H')
    mm = startDt.strftime('%M')

    if mm == '56' or mm == '26': #Cada 30 minutos, 4 minutos antes de 00 y 30 min
        
        global execution_time, symbol
        twm = ThreadedWebsocketManager()
        twm.start()
        print(f'Conectando al Exchange....', flush=True)

        kline_name = twm.start_kline_socket(callback=handle_twm_message, symbol=symbol, interval=AsyncClient.KLINE_INTERVAL_30MINUTE)
        depth_name = twm.start_depth_socket(callback=handle_twm_message, symbol=symbol)

        start_time = time.time()

        try:
            while time.time() - start_time < execution_time:
                progress = int(((time.time() - start_time)/execution_time)*100)
                if progress>100:
                    progress = 100
                print(f'\rObteniendo Kline, Bids y Asks [{progress} %]',end='', flush=True)
                time.sleep(0.1)  
        finally:
            # Esto se ejecutará cuando termine el tiempo o si hay una interrupción
            twm.stop_socket(kline_name)
            twm.stop_socket(depth_name)
            twm.stop
            time.sleep(3)
            print(f'\rObteniendo Kline, Bids y Asks [100 %]',flush=True)

            #Almacenando la data del depth en un archivo de log
            LOG_DIR = os.path.join(settings.BASE_DIR,'log')
            DATA_FILE = os.path.join(LOG_DIR, f"order_book_{symbol}.pkl")
            print('Registrando datos en: ',DATA_FILE)

            depth['bids'] = [[float(x) for x in pair] for pair in depth['bids']]
            depth['asks'] = [[float(x) for x in pair] for pair in depth['asks']]

            # Crear directorio de logs si no existe
            os.makedirs(LOG_DIR, exist_ok=True)

            with open(DATA_FILE, "wb") as archivo:
                pickle.dump(depth, archivo)

            bids = depth['bids']
            asks = depth['asks']
            high = price['high']
            low = price['low']
            close = price['close']
            volume = price['volume']

            DATA_FILE = os.path.join(LOG_DIR, f"order_book_{symbol}_historic.pkl")
            analyzer = OrderBookAnalyzer(DATA_FILE)
            analysis_result = analyzer.analyze_order_book(high, low, close, volume, bids, asks )
            print("Análisis completado. Resumen:")
            print(f"Precio base: {analysis_result['base_price']}")
            print(f"Desbalance del mercado: {analysis_result['market_imbalance']['imbalance_pct']:.2f}%")
            print(f"Soportes significativos encontrados: {len(analysis_result['bid_supports']['levels'])}")
            for s in analysis_result['bid_supports']['levels']:
                print(f"{s['price']}", f"{s['volume_pct']:.2f} %")
            print(f"Resistencias significativas encontradas: {len(analysis_result['ask_resistances']['levels'])}")
            for s in analysis_result['ask_resistances']['levels']:
                print(f"{s['price']}", f"{s['volume_pct']:.2f} %")
