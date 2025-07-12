import os
import pickle
from datetime import datetime

from scripts.Exchange import Exchange
from scripts.functions import get_intervals
from django.conf import settings
from scripts.app_log import app_log

date_format = '%Y-%m-%d %H:%M'
breadth_file = os.path.join(settings.BASE_DIR,f'log/top30_breadth.pkl')

class top30_alerts:
    interval_id = '1h04'
    PERIODS = 60

    def execute(self, *args, **options):
        print('Iniciando')
        self.breadth = 50
        self.alerts_log = []
        self.history = {}
        self.breadth_file = breadth_file
        self.exchange = Exchange(type='info',exchange='bnc',prms=None)
        self.tlg = app_log()
        self.interval = get_intervals(self.interval_id,'binance')
        
        self.bootstrap_klines()

        self.load_pre_data()

        self.analize()
        

    def load_pre_data(self):
        print('Cargando informacion previa')       
        if os.path.exists(self.breadth_file):
            with open(self.breadth_file, "rb") as archivo:
                status = pickle.load(archivo)
                self.breadth = status['breadth']
                self.alerts_log = status['log']

    def bootstrap_klines(self):
        print('Obteniendo informacion del eschange')
        self.history = {}

        self.target_symbols = ['XRPUSDT','SOLUSDT','TRXUSDT','DOGEUSDT','ADAUSDT','WBTCUSDT','BCHUSDT',\
                               'SUIUSDT','LINKUSDT','XLMUSDT','AVAXUSDT','SHIBUSDT','LTCUSDT','HBARUSDT',\
                               'DOTUSDT','UNIUSDT','PEPEUSDT','AAVEUSDT','APTUSDT','NEARUSDT','ICPUSDT',\
                               'ETCUSDT','VETUSDT','ATOMUSDT','FETUSDT','FILUSDT','WLDUSDT','ALGOUSDT',
                               'NEXOUSDT','OPUSDT'] 
        tot_symbols = len(self.target_symbols)
        act_symbol = 0
        for symbol in self.target_symbols:
            act_symbol += 1
            print(f' - Symbol: {symbol} ({act_symbol}/{tot_symbols})')
            klines = self.exchange.get_klines(symbol=symbol, interval_id=self.interval_id, limit=self.PERIODS+1)
            self.history[symbol] = klines.iloc[:-1] 

    def analize(self):
        print('Analizando')
        total_above = 0
        total_ok = 0
        for symbol in self.target_symbols:
            df = self.history[symbol]
            if len(df) == 60:
                sma = df['close'].mean()
                last_close = self.history[symbol].iloc[-1]['close']
                total_ok += 1
                if last_close>sma:
                    total_above += 1

        breadth = (total_above/total_ok)*100
        str_alert = ''
        last_update = datetime.now().strftime(date_format)
        if self.breadth < 100 and breadth == 100:
            str_alert = f'Top30 - {self.interval} - Vender'
            print(str_alert)
            self.tlg.alert(str_alert)
            self.alerts_log.append(f'{last_update} - {str_alert}')
        elif self.breadth > 0 and breadth == 0:
            str_alert = f'Top30 - {self.interval} - Comprar'
            print(str_alert)
            self.tlg.alert(str_alert)
            self.alerts_log.append(f'{last_update} - {str_alert}')
        
        breadth = round(breadth,2)
        print(f'Breadth: {breadth}')
        
        self.breadth = breadth

        status = {'breadth': self.breadth,
                  'timeframe_base': '1h',
                  'timeframe_agregado': self.interval,
                  'last_update': last_update,
                  'log': self.alerts_log
                  }
        with open(self.breadth_file, "wb") as archivo:
            pickle.dump(status, archivo)
        
        print('Proceso completo')

def run():
    
    top30 = top30_alerts()
    top30.execute()



        