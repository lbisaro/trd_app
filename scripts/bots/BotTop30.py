from bot.model_kline import *
import numpy as np
import datetime as dt
import pickle
from scripts.Bot_Core import Bot_Core
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class BotTop30(Bot_Core):

    top30_file = './backtest/klines/1h01/top30_TOP30_1h01_2024-05-01_2025-05-31.DataFrame'
    valid_timeframe = '1h01'
    short_name = 'Top30'
    symbol = ''
    quote_perc = 0.0
    interes = ''
    rsmpl = 0
    trail = 0

    indicadores = [
            #{'col': 'ZigZag', 'name': 'ZigZag', 'color': 'gray', 'row': 1,  'mode':'lines',},             
            #{'col': 'long_fbe_0', 'name': 'Fibonacci Signal', 'color': 'gray', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
            #{'col': 'long_fbe_1', 'name': 'Fibonacci TakeProfit', 'color': 'green', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
            #{'col': 'long_fbe_2', 'name': 'Fibonacci StopLoss', 'color': 'red', 'row': 1,  'mode':'markers','symbol':'circle-dot',},             
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
                  'Ejecuta la compra al recibir una señal de Compra por Extension de Fibonacci, con stoploss en nivel 0.0 , '\
                  'Cierra la operación por Stop Loss o Señal de venta.'
    
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
                        'v' :'100',
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
                 'stop_loss': {
                        'c' :'stop_loss',
                        'd' :'Stop Loss',
                        'v' :'2',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'SL', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.stop_loss < 0:
            err.append("El Stop Loss debe ser mayor o igual a 0")
        if len(err):
            raise Exception("\n".join(err))
        if self.interval_id != '1h01':
            err.append("El timeframe solo puede ser de 1h")
        
    def start(self):
        
        self.klines['signal'] = 'NEUTRO'
        #Cargando data del indicador Top30 1h
        with open(self.top30_file, 'rb') as file:
            top30 = pickle.load(file)
            self.klines['breadth'] = top30['breadth']
            self.klines['signal'] = np.where((self.klines['breadth']!=0) & (self.klines['breadth'].shift()==0),'COMPRA',self.klines['signal'])
            self.klines['signal'] = np.where((self.klines['breadth']!=100) & (self.klines['breadth'].shift()==100),'VENTA',self.klines['signal'])
        
        self.print_orders = False
        self.graph_open_orders = True

    """
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
            status['trend'] = {'l': 'Tendencia','v': trend+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.row['trend'], 'cls': cls}

            status['pivots'] = None
        return status    
    """

    def next(self):

        open_orders = len(self._orders)
        if self.row['signal'] == 'COMPRA' and open_orders < 1: 
            start_cash = round(self.quote_qty * (self.quote_perc/100),self.qd_quote)
            if self.interes == 's': #Interes Simple
                cash = start_cash if start_cash <= self.wallet_quote else self.wallet_quote
            else: #Interes Compuesto
                cash = self.wallet_quote

            qty = round_down(cash/self.price,self.qd_qty)
            buy_order_id = self.buy(qty=qty,flag=Order.FLAG_SIGNAL,tag='BUY')
            if buy_order_id:
                buy_order = self.get_order(buy_order_id)
                buyed_usd = round(buy_order.price*buy_order.qty,self.qd_quote)
                
                #Stop-loss price
                if self.stop_loss > 0:
                    limit_price = round(buy_order.price * (1-(self.stop_loss/100)) ,self.qd_price)
                    self.sell_limit(qty,Order.FLAG_STOPLOSS,limit_price,tag='STOP_LOSS')

        elif self.row['signal'] == 'VENTA' and open_orders > 0:
            self.close(flag=Order.FLAG_TAKEPROFIT)
        

        
    def on_order_execute(self, order):
        if order.side == Order.SIDE_SELL:
            self.cancel_orders()
