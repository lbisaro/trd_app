import os
import pickle
from datetime import datetime, timedelta

from collections import deque

from scripts.Exchange import Exchange
from scripts.functions import get_intervals
from django.conf import settings
from scripts.app_log import app_log
from bot.model_kline import Symbol

date_format = '%Y-%m-%d %H:%M'
breadth_file = os.path.join(settings.BASE_DIR,f'log/top30_breadth.pkl')

class top30_alerts:
    interval_id = '1h04'

    min_interval_id = '0m15'
    interval_ids = ['0m15','1h01','1h04']
    
    limit_history = 1000
    PERIODS = 60

    history = {}
    tf_data = {}
    top30_history = {}

    def execute(self, *args, **options):
        print('Iniciando')
        self.breadth = 50
        self.alerts_log = []
        self.history = {}
        self.top30_history = {'dt':[],'0m15':[],'1h01':[],'1h04':[],}
        self.breadth_file = breadth_file
        self.exchange = Exchange(type='info',exchange='bnc',prms=None)
        self.tlg = app_log()
        self.interval = get_intervals(self.interval_id,'binance')
        
        self.load_pre_data()
        self.bootstrap_klines()
        self.analize()
        

    def load_pre_data(self):
        print('Cargando informacion previa')       
        if os.path.exists(self.breadth_file):
            with open(self.breadth_file, "rb") as archivo:
                status = pickle.load(archivo)
                self.breadth = status['breadth']
                self.alerts_log = status['log']
                if 'history' in status:
                    self.history = status['history']
                else:
                    self.history = {}
                if 'tf_data' in status:
                    self.tf_data = status['tf_data']
                else:
                    self.tf_data = {}

                if 'top30_history' in status:
                    self.top30_history = status['top30_history']

                #Si excede el limite de minutos entre el ultimo update y este, resetea el history para que vuelva a cargarlo
                if 'last_update_dt' in status:
                    diffMinutes = (datetime.now()-status['last_update_dt']).total_seconds()/60
                    if diffMinutes > 30:
                        self.tf_data = {}
                        self.history = {}
                

    
    def get_live_breadth(interval_id='default'):
        with open(breadth_file, "rb") as archivo:
            status = pickle.load(archivo)
            if interval_id == 'default':
                return status['breadth']
            else:
                return status['tf_data'][interval_id]['breadth']
        
    def bootstrap_klines(self):
        print('Obteniendo informacion del exchange')
        
        prices = self.exchange.get_all_prices()
        
        self.target_symbols = Symbol.getTop30Symbols() 
        self.target_symbols = self.target_symbols[0:30]
        tot_symbols = len(self.target_symbols)
        act_symbol = 0
        for symbol in self.target_symbols:
            act_symbol += 1
            if symbol in self.history:
                print(f' - Symbol: {symbol} ({act_symbol}/{tot_symbols}) - Agregando Close')
                self.history[symbol].append(prices[symbol])
            else:
                self.history[symbol] = deque(maxlen=self.limit_history)
                print(f' - Symbol: {symbol} ({act_symbol}/{tot_symbols}) - Descargando velas')
                klines = self.exchange.get_klines(symbol=symbol, interval_id=self.min_interval_id, limit=self.limit_history)
                klines = klines.iloc[:-1]
                for i,row in klines.iterrows():
                    self.history[symbol].append(row['close'])
                 

    def analize(self):

        #### #Fix dt in top30_history
        #### hst_length = len(self.top30_history['0m15'])
        #### hst_last_dt = datetime.now()
        #### self.top30_history['dt'] = []
        #### for i in range(1,hst_length+1):
        ####     minutes = hst_length-i+1
        ####     dt = hst_last_dt-timedelta(minutes=minutes*15 )
        ####     self.top30_history['dt'].append(dt)

        print('Analizando')
        last_update = datetime.now().strftime(date_format)
        tf_data = {}
        for interval_id in self.interval_ids:
            tf_data[interval_id] = {}
            tf_data[interval_id]['total_ok'] = 0
            tf_data[interval_id]['total_above'] = 0
            tf_data[interval_id]['breadth'] = 50

        for symbol in self.target_symbols:
            cierres_lista = self.history[symbol]
            cierre_15m = list(cierres_lista)
            last_close = cierre_15m[-1]

            if len(cierre_15m)>=60:
                cierres_15m_sma = cierre_15m[-60:]
                sma_15m = sum(cierres_15m_sma) / len(cierres_15m_sma)
                tf_data['0m15']['total_ok'] +=1
                if last_close>sma_15m:
                    tf_data['0m15']['total_above'] +=1
            
            if len(cierre_15m)>=240:
                ultimos_240_cierres_15m = cierre_15m[-240:]
                cierres_1h = ultimos_240_cierres_15m[3::4]
                sma_1h = sum(cierres_1h) / len(cierres_1h)
                tf_data['1h01']['total_ok'] +=1
                if last_close>sma_1h:
                    tf_data['1h01']['total_above'] +=1
            
            if len(cierre_15m)>=960:
                ultimos_960_cierres_15m = cierre_15m[-960:]
                cierres_4h = ultimos_960_cierres_15m[15::16]
                sma_4h = sum(cierres_4h) / len(cierres_4h)
                tf_data['1h04']['total_ok'] +=1
                if last_close>sma_4h:
                    tf_data['1h04']['total_above'] +=1            

        for interval_id in self.interval_ids:
            interval = get_intervals(interval_id,'binance')
            total_ok = tf_data[interval_id]['total_ok'] 
            total_above = tf_data[interval_id]['total_above'] 
            breadth = (total_above/total_ok)*100
            pre_breadth = 50
            if interval_id in self.tf_data and 'breadth' in tf_data[interval_id]:
                pre_breadth = self.tf_data[interval_id]['breadth']
            self.top30_history[interval_id].append(round(breadth,2))
            tf_data[interval_id]['breadth'] = round(breadth,2)
            str_alert = ''
            if pre_breadth < 100 and breadth == 100:
                str_alert = f'Top30 - {interval} - Vender'
                if interval_id == '1h04':
                    self.tlg.alert(str_alert)
                self.alerts_log.append(f'{last_update} - {str_alert}')
            elif pre_breadth > 0 and breadth == 0:
                str_alert = f'Top30 - {self.interval} - Comprar'
                if interval_id == '1h04':
                    self.tlg.alert(str_alert)
                self.alerts_log.append(f'{last_update} - {str_alert}')
        
        self.top30_history['dt'].append(datetime.now())

        self.breadth = 50
        if self.interval_id in tf_data and 'breadth' in tf_data[self.interval_id]:
            self.breadth = tf_data[self.interval_id]['breadth']
        
        
        status = {'breadth': self.breadth,
                  'timeframe_base': '15m',
                  'timeframe_agregado': self.interval,
                  'last_update': last_update,
                  'last_update_dt': datetime.now(),
                  'tf_data': tf_data,
                  'log': self.alerts_log,
                  'history': self.history,
                  'top30_history': self.top30_history,  
                  }
        with open(self.breadth_file, "wb") as archivo:
            pickle.dump(status, archivo)
        print('Proceso completo')



def run():
    
    top30 = top30_alerts()
    top30.execute()



        