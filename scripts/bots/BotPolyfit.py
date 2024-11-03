from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *
import scripts.indicators as ind
import random
import string

class BotPolyfit(Bot_Core):

    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock
    periods = 0      #Periodo de analisis
    fwd = 0         #Periodo de prediccion
    gap = 0         #Rango +/- de porcentaje en el que no se determina la tendencia

    last_order_id = 0
    
    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.periods = 0
        self.fwd = 0
        self.gap = 0.5
        
    
    descripcion = 'Bot Polyfit, basado en prediccion de precio por diferencia de cuadrados. \n'\
                  'Los periodos de analisis corresponden con la cantidad de datos para evaluar la tendencia \n'\
                  'Los periodos de prediccion corresponden con la cantidad de peridos hacia adelante en los que se predice el precio \n'\
                 
    
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
                  'fwd': {
                        'c' :'fwd',
                        'd' :'Periodos de prediccion',
                        'v' :'1',
                        't' :'int',
                        'pub': True,
                        'sn':'FWD', }, 
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
        if self.fwd < 1:
            err.append("El Periodos de prediccion debe ser mayor a 1")
        if self.gap < 0:
            err.append("El GAP debe ser mayor o igual a 0")
        if self.stop_loss < 0:
            err.append("El Stop Loss debe ser mayor o igual a 0")
        if self.take_profit < 0:
            err.append("El Take Profit debe ser mayor o igual a 0")

        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        gap = self.gap/100
        self.klines['pred'] = self.klines['close'].rolling(self.periods).apply(lambda x: ind.predict_price(x,self.fwd))
        self.klines['change']  = ((self.klines['pred']/self.klines['pred'].shift(1))-1)
       
        self.klines['trend+'] = np.where(self.klines['change']>gap,self.klines['pred'],None)
        self.klines['trend-'] = np.where(self.klines['change']<-gap,self.klines['pred'],None)

        self.klines['signal']  = np.where((self.klines['trend+'] >0) 
                                          & (self.klines['trend+']<self.klines['close']),'COMPRA','NEUTRO')
        self.klines['signal']  = np.where(self.klines['change']<0,'VENTA',self.klines['signal'])
              
        self.print_orders = False
        self.graph_open_orders = False
        self.graph_signals = False


    
    def next(self):
        print('--kk 3.2 - self.row')
        print(self.row)
        print('--kk 3.2 - self.row')
        if self.row['signal'] == 'COMPRA': 
            tag = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            quote_qty = self.quote_qty if self.wallet_quote >= self.quote_qty else self.wallet_quote
            quote_to_sell = round_down(quote_qty*(self.quote_perc/100) , self.qd_quote )
            qty = round_down(quote_to_sell / self.price , self.qd_qty)
            #self.buy_limit(qty=qty,limit_price = self.row['ema'],flag=Order.FLAG_TAKEPROFIT,tag='BUY')
            self.buy(qty=qty,flag=Order.FLAG_SIGNAL,tag=tag)
        #if self.row['signal'] == 'VENTA':
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
            
           