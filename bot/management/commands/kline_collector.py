import signal
import time
import os
import pickle
import logging
from collections import deque
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from binance import ThreadedWebsocketManager
from binance.client import Client
from django.conf import settings
from scripts.app_log import app_log

date_format = '%Y-%m-%d %H:%M'

# La clase Candle y la configuración de logging se mantienen igual
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
breadth_file = os.path.join(settings.BASE_DIR,f'log/top30_breadth.pkl')
class ShutdownHandler:
    """
    Clase para manejar las señales de apagado (Ctrl+C y systemd) de forma limpia.
    """
    def __init__(self, twm):
        self.twm = twm
        self.shutdown_requested = False
        self.client = False
        self.breadth = False
        self.breadth_file = False
        self.alerts_log = False
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        logging.info(f"Señal de apagado recibida (Señal: {signal.Signals(signum).name}).")
        # Ponemos una bandera para indicar que el apagado fue solicitado
        self.shutdown_requested = True
        # Detenemos el gestor de websockets. Esto hará que twm.join() se desbloquee.
        self.twm.stop()

class Candle:
    def __init__(self, open_time, o, h, l, c, v):
        self.open_time = open_time
        self.open = float(o)
        self.high = float(h)
        self.low = float(l)
        self.close = float(c)
        self.volume = float(v)
        self.breadth = False
        
    def __repr__(self):
        dt_obj = datetime.fromtimestamp(self.open_time, tz=timezone.utc)
        return f"Candle(T='{dt_obj}', O={self.open}, H={self.high}, L={self.low}, C={self.close})"
    
class Command(BaseCommand):
    help = 'Inicia el recolector de datos usando python-binance y ThreadedWebsocketManager.'

    # ... (__init__ sin cambios)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TIMEFRAME_BASE = '1m'
        self.TIMEFRAME_AGREGADO = '4h'
        self.SEGUNDOS_AGREGADOS = 5 * 60
        self.history = {}
        self.current_candle = {}
        self.target_symbols = []


    ### CAMBIO 1: Bootstrap ahora solo obtiene historia COMPLETA ###
    def bootstrap_data(self):
        logging.info(f"Iniciando bootstrap (últimas 60 velas COMPLETAS de {self.TIMEFRAME_AGREGADO})...")
        self.target_symbols = ['XRPUSDT','SOLUSDT','TRXUSDT','DOGEUSDT','ADAUSDT','WBTCUSDT','BCHUSDT',\
                               'SUIUSDT','LINKUSDT','XLMUSDT','AVAXUSDT','SHIBUSDT','LTCUSDT','HBARUSDT',\
                               'DOTUSDT','UNIUSDT','PEPEUSDT','AAVEUSDT','APTUSDT','NEARUSDT','ICPUSDT',\
                               'ETCUSDT','VETUSDT','ATOMUSDT','FETUSDT','FILUSDT','WLDUSDT','ALGOUSDT',
                               'NEXOUSDT','OPUSDT'] 
        for symbol in self.target_symbols:
            try:
                # Pedimos 61 para asegurarnos de que al descartar la última (potencialmente parcial), nos queden 60.
                klines = self.client.get_historical_klines(symbol=symbol, interval=self.TIMEFRAME_AGREGADO, limit=61)
                
                
                self.history[symbol] = deque(maxlen=60)
                # IMPORTANTE: Descartamos la última vela de la API para asegurar que solo tenemos historia completa.
                for k in klines:
                    candle = Candle(
                        open_time=int(k[0] / 1000), o=k[1], h=k[2], l=k[3], c=k[4], v=k[5]
                    )
                    self.history[symbol].append(candle)
                logging.info(f"Bootstrap para {symbol} completado. {len(self.history[symbol])} velas cargadas.")

            except Exception as e:
                logging.error(f"Error en el bootstrap para {symbol}: {e}")
                self.history[symbol] = deque(maxlen=60)



    def run_analysis_for_symbol(self):
        """
        Realiza el análisis usando las 60 velas históricas y la vela parcial actual.
        """
        total_above = 0
        total_symbols = len(self.target_symbols)
        for symbol in self.target_symbols:
            history = self.history.get(symbol)
            if not history or len(history) < 60:
                logging.warning(f"Análisis para {symbol} omitido. Datos históricos insuficientes ({len(history)}/60).")
                return

            # La SMA se calcula sobre las velas completas del historial.
            closes_history = [c.close for c in history]
            sma_60 = sum(closes_history) / 60

            # El "último cierre" a comparar es el de la vela parcial actual.
            last_close = self.history[symbol][-1].close

            if last_close>sma_60:
                total_above += 1
        breadth = (total_above/total_symbols)*100
        str_alert = ''
        last_update = datetime.now().strftime(date_format)
        if self.breadth == 100 and breadth < 100:
            str_alert = f'Top30 {self.TIMEFRAME_BASE}/{self.TIMEFRAME_AGREGADO} - Vender'
            logging.info(str_alert)
            self.tlg.alert(str_alert)
            self.alerts_log.append(f'{last_update} - {str_alert}')
        elif self.breadth == 0 and breadth > 0:
            str_alert = f'Top30 {self.TIMEFRAME_BASE}/{self.TIMEFRAME_AGREGADO} - Comprar'
            logging.info(str_alert)
            self.tlg.alert(str_alert)
            self.alerts_log.append(f'{last_update} - {str_alert}')
        
        breadth = round(breadth,2)
        print(f'Breadth: {breadth}',end='\r')
        
        self.breadth = breadth

        status = {'breadth': self.breadth,
                  'timeframe_base': self.TIMEFRAME_BASE,
                  'timeframe_agregado': self.TIMEFRAME_AGREGADO,
                  'last_update': last_update,
                  'log': self.alerts_log
                  }
        with open(self.breadth_file, "wb") as archivo:
            pickle.dump(status, archivo)
        
        ##logging.info(f"ANÁLISIS CADA MINUTO ({symbol}): Último Cierre (parcial)={last_close:.2f} vs SMA_60 (histórica)={sma_60:.2f}")
        # ... Aquí iría tu lógica para disparar la alerta real ...

    def handle_socket_message(self, msg):
        if 'data' not in msg:
            return
        payload = msg['data']
        if payload.get('e') == 'kline':
            kline_data = payload['k']
            if not kline_data['x']:
                return
            symbol = kline_data['s']
            if symbol not in self.target_symbols:
                return
            
            new_candle_base = Candle(
                open_time=int(kline_data['t'] / 1000), 
                o=kline_data['o'], h=kline_data['h'], l=kline_data['l'], c=kline_data['c'], v=kline_data['v']
            )
            
            current_agg_candle = self.history[symbol][-1]
            block_start_time = new_candle_base.open_time - (new_candle_base.open_time % self.SEGUNDOS_AGREGADOS)
            if current_agg_candle.open_time != block_start_time:
                self.history[symbol].append(new_candle_base)
            else:
                # Agregamos la vela de 1m a la vela de 5m en curso.
                current_agg_candle.high = max(current_agg_candle.high, new_candle_base.high)
                current_agg_candle.low = min(current_agg_candle.low, new_candle_base.low)
                current_agg_candle.close = new_candle_base.close
                current_agg_candle.volume += new_candle_base.volume

            
            # --- ¡AQUÍ ESTÁ LA NUEVA LÓGICA! ---
            # Después de actualizar la vela de 5m (ya sea nueva o parcial),
            # llamamos a la función de análisis CADA VEZ que llega una vela de 1m.
        self.run_analysis_for_symbol()
            



    # --- PUNTO DE ENTRADA (handle) CON MANEJO DE SEÑALES ---
    def handle(self, *args, **options):
        self.breadth = 50
        self.alerts_log = []
        self.breadth_file = breadth_file
        self.client = Client()
        self.tlg = app_log()
        # Fase 1: Obtener historia completa
        self.bootstrap_data()

        #Obteniendo datos almacenedos
        
        if os.path.exists(self.breadth_file):
            with open(self.breadth_file, "rb") as archivo:
                status = pickle.load(archivo)
                self.breadth = status['breadth']
                self.alerts_log = status['log']

        
        streams = [f"{symbol.lower()}@kline_{self.TIMEFRAME_BASE}" for symbol in self.target_symbols]
        logging.info(f"Preparando multiplex socket para {len(streams)} streams.")

        twm = ThreadedWebsocketManager()
        shutdown_handler = ShutdownHandler(twm)
        twm.start()
        twm.start_multiplex_socket(
            callback=self.handle_socket_message, 
            streams=streams
        )
        logging.info("Colector iniciado y escuchando. Presiona Ctrl+C para detener.")
        while not shutdown_handler.shutdown_requested:
            time.sleep(1)
        logging.info("Apagado limpio completado. El programa terminará en breve.")