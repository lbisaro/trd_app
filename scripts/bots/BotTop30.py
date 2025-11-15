from bot.model_kline import *
import numpy as np
import datetime as dt
import pickle
from scripts.Bot_Core import Bot_Core
from scripts.functions import round_down
from scripts.Bot_Core_utils import *
from scripts.crontab_top30_alerts import top30_alerts as top30Live 
from scripts.top30_update_backtest_klines import top30_file

class BotTop30(Bot_Core):

    top30_file = ''
    valid_timeframe = '1h01'
    short_name = 'Top30'
    symbol = ''
    quote_perc = 0.0
    interes = ''
    rsmpl = 0
    trail = 2
    tp_ok = 1
    
    indicadores = [
            {'col': 'breadth', 'name': 'breadth', 'color': 'gray', 'row': 4,  'mode':'lines',},             
            ]
    

    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.distance = 0.0
        self.take_profit = 0.0
        self.interes = 's'  
        self.rsmpl = 0
        self.trail = 2
        self.top30_file = top30_file
        self.tp_ok = 1

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta compras parciales al recibir una señal de Compra por el indicador Top30, '\
                  'Cierra la operación por Señal de venta, con Stop-Loss o Trail-Stop.'\
    
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
                        'v' :'24',
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
                 'distance': {
                        'c' :'distance',
                        'd' :'Distancia de compras',
                        'v' :'5',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'Dst', },
                 'trail': {
                        'c' :'trail',
                        'd' :'Trail Stop Loss',
                        'v' : '2',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'TRL', },
                 'tp_ok': {
                        'c' :'tp_ok',
                        'd' :'Solo Take Profit',
                        'v' : 1,
                        't' :'bin',
                        'pub': True,
                        'sn':'TP_Ok', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.distance < 0:
            err.append("El Distancia de compra debe ser mayor o igual a 0")
        if len(err):
            raise Exception("\n".join(err))
        if self.interval_id != '1h01':
            err.append("El timeframe solo puede ser de 1h")
        
    def start(self):
        
        self.klines['signal'] = 'NEUTRO'
        
        #Cargando data del indicador Top30 1h
        self.klines['breadth'] = 50
        if self.is_backtesting():
            with open(self.top30_file, 'rb') as file:
                top30 = pickle.load(file)
                self.klines['breadth'] = top30['breadth']
        elif self.is_live_run():
            live_breadth = top30Live.get_live_breadth()
            self.klines['breadth'] = live_breadth
        
        self.klines['breadth'] = self.klines['breadth'].fillna(value='')

        self.klines['signal'] = np.where(self.klines['breadth']==0,'COMPRA',self.klines['signal'])
        self.klines['signal'] = np.where(self.klines['breadth']==100 ,'VENTA',self.klines['signal'])
        

        self.print_orders = False
        self.graph_open_orders = True
        self.graph_signals = True
    
    def next(self):

        self.position = False
        last_buy_price = 0
        self.high = self.row['high']
        self.low = self.row['low']

        for id in self._trades:
            o = self._trades[id]
            if o.side == Order.SIDE_BUY and o.pos_order_id == 0:
                self.position = True
                last_buy_price = o.price
        
        if self.row['signal'] == 'COMPRA': 
            if not self.position or self.price < (last_buy_price * (1-self.distance/100)):
                
                cash = 0
                if self.interes == 's': #Interes Simple
                    quote_to_buy = round(self.quote_qty * (self.quote_perc/100),self.qd_quote)
                    cash = quote_to_buy if quote_to_buy <= self.wallet_quote else self.wallet_quote
                else: #Interes Compuesto
                    quote_to_buy = round(self.wallet_quote * (self.quote_perc/100),self.qd_quote)
                    cash = quote_to_buy if quote_to_buy <= self.wallet_quote else self.wallet_quote
                
                if cash > 0:
                    limit_price = round(self.price,self.qd_price)
                    qty = round_down(cash/self.price,self.qd_qty)
                    tp_buy_order = self.get_order_by_tag(tag='BUY_LIMIT')
                    if tp_buy_order:
                        if tp_buy_order.limit_price > limit_price:
                            self.update_order_by_tag(tag="BUY_LIMIT",limit_price=limit_price,qty=qty)
                    else:
                        self.buy_limit(qty=qty,limit_price=limit_price,flag=Order.FLAG_STOPLOSS,tag='BUY_LIMIT')

        if self.position and self.row['signal'] == 'VENTA':
            sell_is_ok = False
            pos_pnl = 0.0
            if 'pos___pnl' in self.status:
                pos_pnl = self.status['pos___pnl']['r']
            if self.tp_ok>0:
                sell_is_ok = True
            elif self.trail > 0 and pos_pnl>self.trail:
                sell_is_ok = True

            if sell_is_ok:
                if self.trail <= 0: 
                    #Venta sin trail Stop 
                    self.close(flag=Order.FLAG_TAKEPROFIT)            
                else:
                    #Venta con Trail Stop
                    max_price = self.price
                    trl_stop_price = max_price * (1-(self.trail/100))
                    buyed_qty = self.wallet_base
                    trl_order = self.get_order_by_tag(tag='STOP_LOSS')
                    if trl_order:
                        if trl_order.limit_price < trl_stop_price:
                            self.update_order_by_tag('STOP_LOSS',limit_price=round_down(trl_stop_price,self.qd_price))  
                    else:
                        self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,trl_stop_price,tag="STOP_LOSS")
                
    def on_order_execute(self, order):
        if order.side == Order.SIDE_SELL:
            self.cancel_orders()

