import pandas as pd
import numpy as np
from scripts.functions import round_down
from scripts.indicators import find_pivots
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import Order
from django.utils import timezone as dj_timezone
import datetime as dt


class BotNPattern(Bot_Core):

    symbol = ''
    quote_perc =  0 #% de compra inicial, para stock
    
    
    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.lot_to_safe = 0.0
        self.re_buy_perc = 0.0  
        self.interes = '' 
    
    descripcion = 'Bot de Balanceo de Billetera \n'\
                  'Con tendencia alcista, Realiza una compra al inicio, y Vende parcial para tomar ganancias cuando el capital es mayor a la compra inicial, \n'\
                  'Con tendencia bajista, Vende el total.'
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par',},
                'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Tamaño de posicion',
                        'v' :'35',
                        't' :'perc',
                        'pub': True,
                        'sn':'Inicio', },
                'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'s',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },                
                #'stop_loss': {
                #        'c' :'stop_loss',
                #        'd' :'Stop Loss',
                #        'v' :'3',
                #        't' :'perc',
                #        'pub': True,
                #        'sn':'SL', },

                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de capital por operacion debe ser mayor a 0")
        if len(err):
            raise Exception("\n".join(err))
    
    def get_status(self):
        status_datetime = dt.datetime.now()
        status = super().get_status()
        #if 'st_trend' in self.row:
        #    if self.row['st_trend'] > 0:
        #        tendencia = 'Alcista '+status_datetime.strftime('%d-%m-%Y %H:%M')
        #        cls = 'text-success'
        #    elif self.row['st_trend'] < 0:
        #        tendencia = 'Bajista '+status_datetime.strftime('%d-%m-%Y %H:%M')
        #        cls = 'text-danger'
        #    else:
        #        tendencia = 'Neutral '+status_datetime.strftime('%d-%m-%Y %H:%M')
        #        cls = 'text-secondary'
        #    status['trend'] = {'l': 'Tendencia','v': tendencia, 'r': self.row['st_trend'], 'cls': cls}
        #
        #if self.signal != 'NEUTRO':
        #    if self.signal == 'COMPRA':
        #        cls = 'text-success'
        #    else: 
        #        cls = 'text-danger'
        #    status['signal'] = {'l': 'Ultima señal','v': self.signal+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.signal, 'cls': cls}
        return status
        
        
    def start(self):
        self.klines['last_max'] = None
        self.klines['last_min'] = None
        self.klines['signal'] = None

        self.klines = find_pivots(self.klines)
        pre_row = None  
        for index, row in self.klines.iterrows():
            if pre_row is not None:
                self.klines.at[index, 'last_max'] = pre_row['last_max']
                self.klines.at[index, 'last_min'] = pre_row['last_min']

                if row['max_pivots']>0:
                    self.klines.at[index, 'last_max'] = row['max_pivots']

                if row['min_pivots']>0:
                    if (pre_row['last_min'] is not None and pre_row['last_max'] is not None and  
                        row['min_pivots'] > pre_row['last_min'] and pre_row['last_max'] > row['min_pivots']):
                            self.klines.at[index, 'signal'] = 'COMPRA'
                    if  pre_row['last_min'] is not None and row['min_pivots'] < pre_row['last_min']:
                        self.klines.at[index, 'signal'] = 'VENTA'
                    self.klines.at[index, 'last_min'] = row['min_pivots']
                
            pre_row = self.klines.iloc[index]    
        
        self.print_orders = False
        self.graph_open_orders = False
        self.graph_signals = False

    def on_order_execute(self,order):
        if self.wallet_base*self.price < 12:
            self.cancel_orders()
    
    def next(self):
        price = self.price

        #start_cash = round(self.quote_qty * (self.quote_perc/100),self.qd_quote)
        #hold = round(self.wallet_base*price,self.qd_quote)
        
        if self.signal == 'COMPRA' and self.wallet_quote > 20:
            
            if self.interes == 's': #Interes Simple
                cash = round(self.quote_qty * (self.quote_perc/100),self.qd_quote)
                if cash > self.wallet_quote:
                    cash = self.wallet_quote
            else: #Interes Compuesto
                cash = round(self.wallet_quote * (self.quote_perc/100),self.qd_quote)
                if cash < 20:
                    cash = self.wallet_quote

            qty = round_down(cash/self.price,self.qd_qty)
            buy_order_id = self.buy(qty,Order.FLAG_SIGNAL)
            #if buy_order_id:
            #    buy_order = self.get_order(buy_order_id)
            #    
            #    #Stop-loss price
            #    if self.stop_loss > 0:
            #        limit_price = round(buy_order.price * (1-(self.stop_loss/100)) ,self.qd_price)
            #        self.sell_limit(qty,Order.FLAG_STOPLOSS,limit_price,tag='STOP_LOSS')
                
        elif self.signal == 'VENTA' and self.wallet_base > 0: 
            self.close(Order.FLAG_SIGNAL)
        
        #else:
        #    if self.lot_to_safe > 0 and hold > start_cash*(1+(self.lot_to_safe/100)):
        #        qty = round_down(((hold - start_cash)/price) , self.qd_qty)
        #        if (qty*self.price) < 20.0:
        #            qty = round_down(20.0/price, self.qd_qty)
        #        sell_order_id = self.sell(qty,Order.FLAG_TAKEPROFIT)
        #         
        #        if sell_order_id > 0:
        #            if self.re_buy_perc > 0:
        #                sell_order = self.get_order(sell_order_id)
        #                limit_price = round(sell_order.price*(1-(self.re_buy_perc/100)),self.qd_price)
        #                rebuy_order_id = self.buy_limit(qty,Order.FLAG_TAKEPROFIT,limit_price)
        #
        #if 'st_trend' in self.row and hold > 10:
        #    qty = self.wallet_base
        #    sl_order = self.get_order_by_tag('STOP_LOSS')
        #    if sl_order:
        #        limit_price = round(self.row['st_low'],self.qd_price)
        #        if limit_price < sl_order.limit_price:
        #            limit_price = sl_order.limit_price
        #        if sl_order and (sl_order.limit_price != limit_price or sl_order.qty != qty):
        #            self.update_order_by_tag('STOP_LOSS',limit_price=limit_price, qty=qty)