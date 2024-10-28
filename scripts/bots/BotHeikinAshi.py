from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotHeikinAshi(Bot_Core):

    symbol = ''
    quote_perc =  0 
    quote_perc_down = 0 
    interes = 's'
    last_buy_price = 0


    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.interes = 's'
        self.last_buy_price = 0


    
    descripcion = 'Bot basado en velas Heikin Ashi'
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par',},
                'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Lote de compras (%)',
                        'v' :'20',
                        't' :'perc',
                        'pub': True,
                        'sn':'Compra', },
                'ma': {
                        'c' :'ma',
                        'd' :'Periodo de la Media Simple',
                        'v' :'30',
                        't' :'int',
                        'pub': True,
                        'sn':'MA', },
                'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'s',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de Lote Compra debe ser mayor a 0")


        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):

        df = self.klines.copy()
        # Crear una copia para convertir en Heikin-Ashi 
        df['HA_close'] = (df['close'].shift(1) + df['close']) / 2
        df['HA_open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
        df['HA_high'] = df[['high', 'HA_open', 'HA_close']].max(axis=1)
        df['HA_low'] =  df[['low', 'HA_open', 'HA_close']].min(axis=1)

        df['open'] = df['HA_open']
        df['close'] = df['HA_close']
        df['high'] = df['HA_high']
        df['low'] = df['HA_low']
        df.drop(columns=['HA_open','HA_close','HA_high','HA_low'],inplace=True)
        

        df['sign'] = np.where(df['close']>df['open'],1,-1)
        df['group'] = (df['sign'] != df['sign'].shift()).cumsum()
        df['streak'] = df.groupby('group').cumcount() + 1
        df['buy'] = np.where((df['sign']==1)&(df['streak']>=2),1,None)
        df['sell'] = np.where((df['sign']==-1)&(df['streak']==1),1,None)

        self.klines['buy'] = df['buy']
        self.klines['sell'] = df['sell']
        self.klines['hl2'] = (self.klines['high']+self.klines['low'])/2
        self.klines['ma'] = self.klines['hl2'].rolling(window=self.ma).mean()
        self.klines['signal'] = np.where((self.klines['buy']==1)&(self.klines['hl2']>self.klines['ma']),'COMPRA','NEUTRO')   
        self.klines['signal'] = np.where(self.klines['sell']==1,'VENTA',self.klines['signal'])   

        self.print_orders = False
        self.graph_open_orders = True
        self.graph_signals = False
    
    def next(self):
        price = self.price
        start_cash = round(self.quote_qty ,self.qd_quote)
        
        if self.signal == 'COMPRA':
        
            if self.interes == 's': #Interes Simple
                cash = start_cash if start_cash <= self.wallet_quote else self.wallet_quote
            else: #Interes Compuesto
                cash = self.wallet_quote

            lot_to_buy = cash * (self.quote_perc/100)
            if lot_to_buy <= self.wallet_quote and lot_to_buy > 12:
                qty = round_down(lot_to_buy/self.price,self.qd_qty)
                buy_order_id = self.buy(qty,Order.FLAG_SIGNAL)
                if buy_order_id:
                    buy_order = self._trades[buy_order_id]

                    self.last_buy_price = buy_order.price
            
        elif self.signal == 'VENTA': 
            self.close(Order.FLAG_SIGNAL)
            self.last_buy_price = 0

                
            