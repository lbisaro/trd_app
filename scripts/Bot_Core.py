import pandas as pd
import numpy as np
import datetime as dt

import scripts.functions as fn
from scripts.Exchange import Exchange
from scripts.Bot_Core_utils import *
from scripts.Bot_Core_stats import *
from scripts.Bot_Core_backtest import *
from scripts.Bot_Core_live import *
from scripts.functions import round_down
import time

from bot.models import Order as DbOrder
from bot.models import Bot as DbBot
from bot.model_kline import Symbol

class Bot_Core(Bot_Core_stats,Bot_Core_backtest,Bot_Core_live):

    short_name = ''
        
    DIAS_X_MES = 30.4375 #Resulta de tomar 3 años de 365 dias + 1 de 366 / 4 años / 12 meses

    signal = 'NEUTRO'
    order_id = 1

    parametros = {}
    indicadores = []

    #Trades para gestion de resultados
    _orders = {}
    df_trades_columns = ['start','buy_price','qty','end','sell_price','flag','type','days','result_usd','result_perc','orders'] 
    _trades = {}
    executed_order = False
    print_orders = False #Muestra las ordenes ejecutadas por consola

    quote_qty = 0
    interval_id = ''
    bot_id = None
    username = ''

    base_asset = ''
    quote_asset = ''
    qd_price = 0
    qd_qty = 0
    qd_quote = 0
    
    backtesting = True
    live = False

    exchange = None
    wallet_base = 0.0
    wallet_base_block = 0.0
    wallet_quote = 0.0
    wallet_quote_block = 0.0

    row = pd.DataFrame()

    #Gestion de data sobre ordenes buy_limit, stoploss y takeprofit 
    sl_price_data = []
    tp_price_data = []
    buy_price_data = []
    graph_open_orders = False


    def __init__(self):
        

        self.quote_qty = 0
        self.interval_id = ''
        self.bot_id = None

        self.base_asset = ''
        self.quote_asset = ''
        self.qd_price = 0
        self.qd_qty = 0
        self.qd_quote = 0
        
        self.backtesting = True
        self.exchange = None
        self.wallet_base = 0.0
        self.wallet_quote = 0.0

        self.row = pd.DataFrame()

        indicadores = []

    def set(self, parametros):
        for v in parametros:       
            if parametros[v]['t'] == 'int' and not float(parametros[v]['v']).is_integer():
                prm_d = parametros[v]['d']
                raise Exception(f'El parametro {prm_d} debe ser un numero entero.')
            self.__setattr__(parametros[v]['c'], parametros[v]['v'])
    
    def __setattr__(self, prm, val):
            
        type = 'str'
        if prm in self.parametros:
            type = self.parametros[prm]['t']
            if type == 'perc' or type == 'float':
                self.__dict__[prm] = float(val)
            elif type == 'dec' or type == 'float':
                self.__dict__[prm] = float(val)
            elif type == 'int':
                self.__dict__[prm] = int(val)
            elif type == 'bin': #Binario
                self.__dict__[prm] = 1 if int(val)>0 else 0
            else:
                self.__dict__[prm] = str(val)
        else:
            self.__dict__[prm] = val

    def valid(self):
        raise Exception(f'\n{self.__class__.__name__} Se debe establecer un metodo valid()')
        
    def start(self):
        raise Exception(f'\n{self.__class__.__name__} Se debe establecer un metodo start(df)')
    
    def next(self):
        raise Exception(f'\n{self.__class__.__name__} Se debe establecer un metodo next(df)')
    
    def is_backtesting(self):
        if self.backtesting and not self.live:
            return True
        return False

    def is_live_run(self):
        if self.live and not self.backtesting:
            return True
        return False

    def buy(self,qty,flag,**kwargs):
        qty = round(qty,self.qd_qty)
        if qty*self.price>=10: 
            self.order_id += 1
            order = Order(self.order_id,Order.TYPE_MARKET,self.datetime,Order.SIDE_BUY,qty,self.price,flag,**kwargs)
            return self.add_order(order)
        return 0

    def sell(self,qty,flag,**kwargs):
        qty = round_down(qty,self.qd_qty)
        if qty*self.price>=10: 
            self.order_id += 1
            order = Order(self.order_id,Order.TYPE_MARKET,self.datetime,Order.SIDE_SELL,qty,self.price,flag,**kwargs)
            return self.add_order(order)
        return 0
          
    def close(self,flag,**kwargs): #Vende el total existente en self.wallet_base
        self.order_id += 1
        qty = self.wallet_base
        if qty > 0:
            order = Order(self.order_id,Order.TYPE_MARKET,self.datetime,Order.SIDE_SELL,qty,self.price,flag,**kwargs)
            return self.add_order(order)
            
        return 0
        
    def sell_limit(self,qty,flag,limit_price,**kwargs):
        if flag != Order.FLAG_TAKEPROFIT and flag != Order.FLAG_STOPLOSS:
            raise Exception('El flag de las ordenes limit puede ser FLAG_TAKEPROFIT o FLAG_STOPLOSS')
        
        qty = round_down(qty,self.qd_qty)
        if qty*limit_price>=10:
            self.order_id += 1
            limit_price = round(limit_price,self.qd_price)
            order = Order(self.order_id,Order.TYPE_LIMIT,self.datetime,Order.SIDE_SELL,qty,limit_price,flag,**kwargs)
            return self.add_order(order)
        return 0  
    
    def buy_limit(self,qty,flag,limit_price,**kwargs):
        if flag != Order.FLAG_TAKEPROFIT and flag != Order.FLAG_STOPLOSS:
            raise Exception('El flag de las ordenes limit puede ser FLAG_TAKEPROFIT o FLAG_STOPLOSS')
        
        qty = round(qty,self.qd_qty)
        if qty*limit_price>=10:
            self.order_id += 1
            limit_price = round(limit_price,self.qd_price)
            order = Order(self.order_id,Order.TYPE_LIMIT,self.datetime,Order.SIDE_BUY,qty,limit_price,flag,**kwargs)
            return self.add_order(order)
        return 0    
        
    def cancel_order(self,orderid):
        if orderid in self._orders:
            if self.is_live_run():
                order = self._orders[orderid]
                self.delete_order(order)
            del self._orders[orderid]
        
    def cancel_orders(self):
        if self.is_live_run():
            for orderid in self._orders:
                order = self._orders[orderid]
                if order.completed == 0:
                    self.delete_order(order)
        self._orders = {}
    
    def is_order(self,orderid):
        if orderid in self._orders:
            return True
        return False
    
    def is_trade(self,orderid):
        if orderid in self._trades:
            return True
        return False
    
    def order_status(self,orderid):
        if self.is_order(orderid):
            return Order.STATE_NEW
        if self.is_trade(orderid):
            return Order.STATE_COMPLETE
        return Order.STATE_CANCEL
    
    def get_order(self,orderid):
        if orderid in self._orders:
            return self._orders[orderid]
        if orderid in self._trades:
            return self._trades[orderid]
        return None
    
    def get_order_by_tag(self,tag):
        for id in self._orders:
            order = self._orders[id]
            if order.tag == tag:
                return order
        return None
    
    def update_order_by_tag(self,tag,**kwargs):
        """
        tag: Se especifica para encontrar la primer orden existente con ese tab
        """
        order = self.get_order_by_tag(tag)
        if order:
            if 'limit_price' in kwargs:
                order.limit_price = kwargs['limit_price']
            if 'qty' in kwargs:
                order.qty = kwargs['qty']
            if 'flag' in kwargs:
                order.flag = kwargs['flag']
            self.update_order(order)
            return order
        
        return None
    
    def check_orders(self):
        if self.is_backtesting():
            return self.backtest_check_orders()
        if self.is_live_run():
            return self.live_check_orders()
        raise Exception(f'\n{self.__class__.__name__} No se ha definido el entorno de operacion (Live/Backtest)')

    def execute_order(self,orderid):
        if self.is_backtesting():
            return self.backtest_execute_order(orderid)
        if self.is_live_run():
            return self.live_execute_order(orderid)
        raise Exception(f'\n{self.__class__.__name__} No se ha definido el entorno de operacion (Live/Backtest)')
    
    def on_order_execute(self,order):
        #El metodo se llama cuando una orden es ejecutada y debe ser desarrollado en la estrategia
        pass

    def add_order(self,order):
        
        if self.is_live_run():
            order = self.insert_order(order)
            self._orders[order.id] = order
        else:
            self._orders[order.id] = order

        if order.type == Order.TYPE_MARKET:
            if self.execute_order(order.id):
                return order.id
        else:
            return order.id
        return 0

    def delete_order(self,order):
        print('Delete Order ',order)
        if order.completed == 0:
            print('Eliminada')
            order.delete()

    def insert_order(self,tmp_order):
        symbol_obj = Symbol.objects.get(symbol=self.symbol)

        bot_order = DbOrder()
        bot_order.side = tmp_order.side
        bot_order.completed = tmp_order.completed
        bot_order.qty = tmp_order.qty
        bot_order.price = tmp_order.price
        bot_order.pos_order_id = 0
        bot_order.bot_id = self.bot_id
        bot_order.flag = tmp_order.flag
        bot_order.datetime = timezone.now()
        bot_order.symbol = symbol_obj
        bot_order.limit_price = tmp_order.limit_price
        bot_order.tag = tmp_order.tag
        bot_order.type = tmp_order.type
        bot_order.activation_price = tmp_order.activation_price
        bot_order.save()
        return bot_order
    
    def update_order(self,order):
        if order.id in self._orders:
            self._orders[order.id] = order
        if self.is_live_run():
            order.datetime = timezone.now()
            order.save()
        return order

    def add_indicador(self, col, name, color, row=1, mode='lines'):
        self.indicadores.append(
            {'col': col,
             'name': name,
             'color': color,
             'row': row, 
             'mode':mode,
             },)