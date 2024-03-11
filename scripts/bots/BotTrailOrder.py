from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotTrailOrder(Bot_Core):

    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock


    last_order_id = 0
    
    def __init__(self):
        self.symbol = ''
        self.ma = 0
        self.quote_perc = 0.0
        self.re_buy_perc = 0.0
        self.lot_to_safe = 0.0  
        self.quote_up = 0.0
        self.quote_down = 0.0
        self.start_cash = 0.0
        self.start_base = 0.0
    
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
                        'sn':'Par', },
                  'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Compra inicial para stock',
                        'v' :'50',
                        't' :'perc',
                        'pub': True,
                        'sn':'Inicio', },
                  'trail_b': {
                        'c' :'trail_b',
                        'd' :'Trail Compra',
                        'v' :'20',
                        't' :'perc',
                        'pub': True,
                        'sn':'Trl C', },
                  'trail_s': {
                        'c' :'trail_s',
                        'd' :'Trail Venta',
                        'v' :'30',
                        't' :'perc',
                        'pub': True,
                        'sn':'Trl V', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de capital por operacion debe ser mayor a 0")


        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        self.klines['signal'] = 'NEUTRO'   
        self.print_orders = False
        self.graph_open_orders = True
        self.last_order_id = -1
    
    def next(self):
        if self.last_order_id == -1:
            self.actuar()
    
    def on_order_execute(self,order):
        self.actuar()
    
    def actuar(self):

        if self.wallet_base == 0:
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / self.price , self.qd_qty)
            self.last_order_id = self.buy_trail(qty=qty,
                                                flag=Order.FLAG_TAKEPROFIT,
                                                limit_price=self.price * (1+(self.trail_b/100)),
                                                activation_price=0,
                                                trail_perc = self.trail_b)
        else:
            qty = self.wallet_base
            self.last_order_id = self.sell_trail(qty=qty,
                                                flag=Order.FLAG_TAKEPROFIT,
                                                limit_price=self.price * (1-(self.trail_s/100)),
                                                activation_price=0,
                                                trail_perc = self.trail_s)
            
            