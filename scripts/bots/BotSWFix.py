from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotSWFix(Bot_Core):

    symbol = ''
    quote_perc =  0 
    quote_perc_down = 0 
    quote_perc_up = 0 
    sma_period = 0

    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.quote_perc_down = 0.0
        self.quote_perc_up = 0.0  
        self.sma_period = 200
    
    descripcion = 'Bot de Balanceo de Billetera \n'\
                  'Realiza una compra al inicio, \n'\
                  'Sobre la MA, Vende parcial para tomar ganancias cuando el capital es mayor a la compra inicial, \n'\
                  'Bajo la MA, Vende parcial a medida que va perdiendo capital, \n'\
                  'Luego de cada venta recompra a un valor mas bajo.'
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par',},
                'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Capital a mantener en stock',
                        'v' :'50',
                        't' :'perc',
                        'pub': True,
                        'sn':'Compra', },
                'quote_perc_up': {
                        'c' :'quote_perc_up',
                        'd' :'Porcentaje para resguardo',
                        'v' :'5',
                        't' :'perc',
                        'pub': True,
                        'sn':'Resguardo', },
                'quote_perc_down': {
                        'c' :'quote_perc_down',
                        'd' :'Porcentaje para recompra',
                        'v' :'10',
                        't' :'perc',
                        'pub': True,
                        'sn':'Recompra', },

                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de Compra debe ser mayor a 0")
        if self.quote_perc_down <= 0 or self.quote_perc_down > 100:
            err.append("La Recompra debe ser un valor mayor a 0 y menor o igual a 100")
        if self.quote_perc_up <= 0 or self.quote_perc_up > 100:
            err.append("El Resguardo debe ser un valor mayor a 0 y menor o igual a 100")

        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        self.klines['SMA'] = self.klines['close'].rolling(window=200).mean()
        self.klines['EMA_7'] = self.klines['close'].ewm(span=7, adjust=False).mean()
        self.klines['signal'] = 'NEUTRO'   
        self.print_orders = False
        self.graph_open_orders = True
    
    def next(self):
        price = self.price

        to_stock = self.quote_qty * (self.quote_perc/100)
        to_stock_limit_up   = to_stock * (1 + self.quote_perc_up/100 )
        to_stock_limit_down = to_stock * (1 - self.quote_perc_down/100 )
        
        in_stock = self.wallet_base * price

        if in_stock > to_stock_limit_up:

            op_usd = in_stock - to_stock
            qty = round_down(op_usd/price, self.qd_qty)
            self.sell(qty,Order.FLAG_SIGNAL)

        elif in_stock < to_stock_limit_down:        
            if self.wallet_base == 0 or self.row['EMA_7'] < self.row['SMA']: # 
                op_usd = to_stock - in_stock

                if self.wallet_quote >= op_usd:
                    qty = round_down(op_usd/price, self.qd_qty)
                    self.buy(qty,Order.FLAG_SIGNAL)

        
                
            