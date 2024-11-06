from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *
from scripts.indicators import predict_price,psar,resample,join_after_resample
import random
import string
import datetime as dt

class BotPolyfit(Bot_Core):

    short_name = 'PolyFit'
    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock
    periods = 0      #Periodo de analisis
    gap = 0         #Rango +/- de porcentaje en el que no se determina la tendencia
    resample = 0

    last_order_id = 0
    
    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.periods = 0
        self.gap = 0.5
        self.resample = 0
        
    
    descripcion = 'Bot Polyfit, basado en prediccion de precio por diferencia de cuadrados. \n'\
                  'Los periodos de analisis corresponden con la cantidad de datos para evaluar la tendencia \n'\
                 
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par', },
                  'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Compra',
                        'v' :'95',
                        't' :'perc',
                        'pub': True,
                        'sn':'Inicio', },
                  'stop_loss': {
                        'c' :'stop_loss',
                        'd' :'Stop Loss',
                        'v' :'0.15',
                        't' :'perc',
                        'pub': True,
                        'sn':'SL', },
                  'take_profit': {
                        'c' :'take_profit',
                        'd' :'Take Profit',
                        'v' :'5',
                        't' :'perc',
                        'pub': True,
                        'sn':'TP', },
                  'periods': {
                        'c' :'periods',
                        'd' :'Periodos de analisis',
                        'v' :'21',
                        't' :'int',
                        'pub': True,
                        'sn':'PR', },
                  'resample': {
                        'c' :'resample',
                        'd' :'PSAR Resample',
                        'v' :'4',
                        't' :'int',
                        'pub': True,
                        'sn':'rsmpl', },
                  'gap': {
                        'c' :'gap',
                        'd' :'Gap',
                        'v' :'0.5',
                        't' :'perc',
                        'pub': True,
                        'sn':'GAP', },               
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de capital por operacion debe ser mayor a 0")
        if self.periods < 3:
            err.append("Los Periodos de analisis debe ser mayor a 3")
        if self.gap < 0:
            err.append("El GAP debe ser mayor o igual a 0")
        if self.stop_loss < 0:
            err.append("El Stop Loss debe ser mayor o igual a 0")
        if self.take_profit < 0:
            err.append("El Take Profit debe ser mayor o igual a 0")

        if len(err):
            raise Exception("\n".join(err))
        
    def get_status(self):
        status_datetime = dt.datetime.now()
        status = super().get_status()
        
        if self.signal != 'NEUTRO':
            if self.signal == 'COMPRA':
                cls = 'text-success'
            else: 
                cls = 'text-danger'
            status['signal'] = {'l': 'Ultima señal','v': self.signal+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.signal, 'cls': cls}
        return status
        
    def start(self):

        df = self.klines.copy()
        if self.resample > 1:
            dfr = resample(df,self.resample)
            dfr = psar(dfr)
            dfr['psar'] = np.where(dfr['psar_high']>0,dfr['psar_high'],dfr['psar_low'])
            df = join_after_resample(df,dfr,'psar')
            df['psar'].ffill(inplace=True)
            df['psar_low'] = np.where(df['psar']<df['close'],df['psar'],None)
            df['psar_high'] = np.where(df['psar']>df['close'],df['psar'],None)
            df.drop('datetime', axis=1, inplace=True)
            df.reset_index(inplace=True)
        else:
            df = psar(df)

        self.klines = df
        gap = self.gap/100
        self.klines['pred'] = self.klines['close'].rolling(self.periods).apply(lambda x: predict_price(x))
        self.klines['change']  = ((self.klines['pred']/self.klines['pred'].shift(1))-1)
       
        self.klines['trend+'] = np.where(self.klines['change']>gap,self.klines['pred'],None)
        self.klines['trend-'] = np.where(self.klines['change']<-gap,self.klines['pred'],None)

        self.klines['signal']  = np.where((self.klines['psar_low'] >0) 
                                          & (self.klines['trend+'] >0) 
                                          & (self.klines['trend+']<self.klines['close']),'COMPRA','NEUTRO')
        self.klines['signal']  = np.where(self.klines['change']<0,'VENTA',self.klines['signal'])
              
        self.print_orders = False
        self.graph_open_orders = False
        self.graph_signals = False
    
    def next(self):
        if self.signal == 'COMPRA': 
            tag = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            quote_qty = self.quote_qty if self.wallet_quote >= self.quote_qty else self.wallet_quote
            quote_to_sell = round_down(quote_qty*(self.quote_perc/100) , self.qd_quote )
            qty = round_down(quote_to_sell / self.price , self.qd_qty)
            #self.buy_limit(qty=qty,limit_price = self.row['ema'],flag=Order.FLAG_TAKEPROFIT,tag='BUY')
            self.buy(qty=qty,flag=Order.FLAG_SIGNAL,tag=tag)
        #if self.signal == 'VENTA':
        #    self.sell(qty=self.wallet_base,flag=Order.FLAG_SIGNAL)

    
    def on_order_execute(self,order):
        if order.side == Order.SIDE_BUY:
            qty = order.qty
            sl_price = round(order.price*(1-self.stop_loss/100) , self.qd_price)
            tp_price = round(order.price*(1+self.take_profit/100) , self.qd_price)
            self.sell_limit(qty=qty,flag=Order.FLAG_STOPLOSS,limit_price=sl_price,tag=order.tag)
            self.sell_limit(qty=qty,flag=Order.FLAG_TAKEPROFIT,limit_price=tp_price,tag=order.tag)

        else:
            order_to_cancel = self.get_order_by_tag(order.tag)
            if order_to_cancel:
                self.cancel_order(order_to_cancel.id)
            
           