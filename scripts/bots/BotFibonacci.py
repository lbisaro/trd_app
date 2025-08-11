from bot.model_kline import *
import numpy as np
import datetime as dt
from scripts.Bot_Core import Bot_Core
from scripts.indicators import zigzag, fibonacci_extension
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class BotFibonacci(Bot_Core):

    short_name = 'Fibo'
    symbol = ''
    quote_perc = 0.0
    interes = 's'
    rsmpl = 0
    trail = 0
    vp = 0

    indicadores = [
            {'col': 'ZigZag', 'name': 'ZigZag', 'color': 'gray', 'row': 1,  'mode':'lines',},             
            {'col': 'long_fbe_0', 'name': 'Fibonacci Signal', 'color': 'gray', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
            #{'col': 'long_fbe_1', 'name': 'Fibonacci TakeProfit', 'color': 'green', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
            #{'col': 'long_fbe_2', 'name': 'Fibonacci StopLoss', 'color': 'red', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
            ]
    
    fb_levels = [0.0,        
                 0.236,      
                 0.382, 
                 0.5, 
                 0.618, 
                 0.786,
                 1.0, 
                 1.272, 
                 1.618, 
                 2.0, 
                 2.618
                 ]

    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.interes = 's'  
        self.rsmpl = 0
        self.trail = 0

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra por Extension de Fibonacci, con Stop-Loss en nivel 0.0 , '\
                  'Genera ventas parciales cuando el PNL supera 1% la compra inicial, '\
                  'Cierra la operación por Stop-Loss o Trail-Stop.'\
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Sym',},
                 'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Operacion sobre capital',
                        'v' :'95',
                        'l' :'[10,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'Quote', },
                 'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'s',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },
                 'vp': {
                        'c' :'vp',
                        'd' :'Ventas parciales',
                        'v' : '0',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'VP', },
                 'rsmpl': {
                        'c' :'rsmpl',
                        'd' :'Resample para Pivots',
                        'v' : '4',
                        'l' :'[1,100]',
                        't' :'int',
                        'pub': True,
                        'sn':'Rsmpl', },
                 'trail': {
                        'c' :'trail',
                        'd' :'Trail Stop Loss',
                        'v' : '2',
                        'l' :'(0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'TRL', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.rsmpl < 1:
            err.append("Se debe especificar el Resample >= 1")
        if self.trail < 1:
            err.append("Se debe especificar el Trail >= 1")
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        
        self.klines = zigzag(self.klines, resample_periods=self.rsmpl)
 
        #Detectando pivots para analisis de fibonacci
        pivots = self.klines[self.klines['ZigZag']>0].copy()
        pivots['pivots'] = pivots['ZigZag'].copy()
        pivots['fb_0'] = pivots['ZigZag'].copy()
        pivots['fb_1'] = pivots['ZigZag'].shift(1)
        pivots['fb_2'] = pivots['ZigZag'].shift(2)

        #Cambios de tendencia
        pivots['trend'] = np.where((pivots['fb_0']>pivots['fb_2']) & (pivots['fb_1']>pivots['fb_0']), 2,0)
        pivots['trend'] = np.where((pivots['fb_0']>pivots['fb_2']) & (pivots['fb_1']<pivots['fb_0']), 1,pivots['trend'])
        pivots['trend'] = np.where((pivots['fb_0']<pivots['fb_2']) & (pivots['fb_1']<pivots['fb_0']),-2,pivots['trend'])
        pivots['trend'] = np.where((pivots['fb_0']<pivots['fb_2']) & (pivots['fb_1']>pivots['fb_0']),-1,pivots['trend'])
        first_pivot_index = pivots.index[0]
        pivots.at[first_pivot_index,'trend'] = 0 #El primer pivot no se puede definir por lo tanto queda neutro

        #Completando el datafame principal con los datos de pivots
        df_cols = self.klines.columns.copy()
        for col in pivots.columns:
            if not col in df_cols:
                self.klines[col]=None
        for index, row in pivots.iterrows():
            for col in pivots.columns:
                if not col in df_cols:
                    self.klines.at[index,col] = row[col]

        self.klines['signal'] = np.where(self.klines['trend'] ==  2, 'COMPRA' , None)
        self.klines['signal'] = np.where(self.klines['trend'] == -2, 'VENTA' , self.klines['signal'])
        if self.rsmpl>1:
            self.klines['signal'] = self.klines['signal'].fillna(method='ffill', limit=(self.rsmpl-1))
        self.klines['signal'] = self.klines['signal'].fillna('NEUTRO')

        self.klines['trend'].ffill(inplace=True)
        self.klines['fb_0'].ffill(inplace=True)
        self.klines['fb_1'].ffill(inplace=True)
        self.klines['fb_2'].ffill(inplace=True)

        self.klines['long_fbe_0'] = np.where(self.klines['trend']==2, self.klines['fb_0'] , None)
        self.klines['long_fbe_1'] = np.where(self.klines['trend']==2, self.klines['fb_1'] , None)
        self.klines['long_fbe_2'] = np.where(self.klines['trend']==2, self.klines['fb_2'] , None)

        self.print_orders = False
        self.graph_signals = False
        self.graph_open_orders = True

    def get_status(self):
        status_datetime = dt.datetime.now()
        status = super().get_status()
        
        if 'trend' in self.row:
            if self.row['trend'] >= 2:
                cls = 'text-success'
                trend = 'Alza+'
            elif self.row['trend'] == 1:
                cls = 'text-success'
                trend = 'Alza'
            elif self.row['trend'] == -1:
                cls = 'text-danger'
                trend = 'Baja'
            elif self.row['trend'] <= -2:
                cls = 'text-danger'
                trend = 'Baja+'
            else: 
                cls = ''
                trend = 'Neutral'
            status['trend'] = {'l': 'Tendencia',
                               'v': trend+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 
                               'r': self.row['trend'], 
                               'cls': cls}

            status['pivots'] = None
        return status    
    
    def next(self):
        price = self.price
        update_stop_loss = False
        self.position = False
        if self.wallet_base*self.price >= 2:
            self.position = True
        if self.signal == 'COMPRA':

            #Buscando el stop-loss en el nivel de fibonacci anterior al precio de compra
            stop_loss_price = fibonacci_extension(self.row['long_fbe_2'],self.row['long_fbe_1'],self.row['long_fbe_0'],level=0.0)
            pre_level = -1.0
            for i, level in enumerate(self.fb_levels):
                if level >= 0:
                    level_price = fibonacci_extension(self.row['long_fbe_2'],self.row['long_fbe_1'],self.row['long_fbe_0'],level)
                    pre_level_price = fibonacci_extension(self.row['long_fbe_2'],self.row['long_fbe_1'],self.row['long_fbe_0'],pre_level)
                    if level_price > self.price > pre_level_price:
                        slprice = fibonacci_extension(self.row['long_fbe_2'],self.row['long_fbe_1'],self.row['long_fbe_0'],pre_level)
                        slperc = round(((self.price/slprice)-1)*100,2)
                        if slperc > 1:
                            stop_loss_price = slprice
                pre_level = level
            
            #PENDIENTE - Analisis del riesgo a tomar
            stop_loss_price = round_down(stop_loss_price , self.qd_price)
            self.stop_loss = round((1-(stop_loss_price/self.price))*100,2)
                
            if not self.position:
                if self.interes == 's': #Interes Simple
                    quote_qty = self.quote_qty if self.wallet_quote >= self.quote_qty else self.wallet_quote
                    quote_to_sell = round_down(quote_qty*(self.quote_perc/100) , self.qd_quote )
                elif self.interes == 'c': #Interes Compuesto
                    quote_to_sell = round_down(self.wallet_quote*(self.quote_perc/100) , self.qd_quote ) 
                
                quote_to_sell = round_down(quote_to_sell , self.qd_quote ) 
                base_to_buy = round_down((quote_to_sell/price) , self.qd_qty) 
            
                orderid_buy = self.buy(base_to_buy,Order.FLAG_SIGNAL)
                if orderid_buy > 0:

                    buyed_qty = self._trades[orderid_buy].qty
                    
                    self.position = True
                    self.orderid_sl = self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price,tag="STOP_LOSS")
               
        
            else:
                sl_order = self.get_order_by_tag(tag='STOP_LOSS')
                if sl_order and sl_order.limit_price < stop_loss_price:
                    update_stop_loss = True
                    self.update_order_by_tag('STOP_LOSS',limit_price=round_down(stop_loss_price,self.qd_price))      

        #Gestion del Trail Stop
        if self.position:
            if 'pos___max_price' in self.status:
                max_price = self.status['pos___max_price']['r']
                trl_stop_price = max_price * (1-(self.trail/100))
                buyed_qty = self.status['pos___base_qty']['r'] 
                trl_order = self.get_order_by_tag(tag='STOP_LOSS')
                if trl_order:
                    if trl_order.limit_price < trl_stop_price:
                        update_stop_loss = True
                        self.update_order_by_tag('STOP_LOSS',limit_price=round_down(trl_stop_price,self.qd_price))  
                else:
                    self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,trl_stop_price,tag="STOP_LOSS")

        
        #Gestion de venta parcial
        if self.position and self.vp > 0 and update_stop_loss:
            buyed_quote = 0
            wallet = self.wallet_quote + self.wallet_base*self.price

            for i in self._trades:
                order = self._trades[i]
                if order.pos_order_id == 0:
                    if order.side == Order.SIDE_BUY:
                        buyed_quote = order.price * order.qty
            pnl_quote = wallet-buyed_quote
            #Ejecuta una venta parcial si la ganancia en QUOTE es mayor a 11 USD y mayor al % establecido para venta parcial?
            if pnl_quote > 11 and pnl_quote > buyed_quote*(self.vp/100):
                usd_to_sell = pnl_quote
                qty_to_sell = round(usd_to_sell/self.price,self.qd_qty)
                if self.sell(qty=qty_to_sell, flag=Order.FLAG_TAKEPROFIT):
                    self.update_order_by_tag('STOP_LOSS',qty=round_down(self.wallet_base,self.qd_qty)) 
        

    def on_order_execute(self, order):
        if order.side == Order.SIDE_SELL and order.tag == 'STOP_LOSS':
            self.cancel_orders()
