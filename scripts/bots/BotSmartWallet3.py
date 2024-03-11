from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotSmartWallet3(Bot_Core):

    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock
    re_buy_perc = 0 #% para recompra luego de una venta
    lot_to_safe = 0 #% a resguardar si supera start_cash

    op_last_price = 0
    
    start_cash = 0.0  #Cash correspondiente a la compra inicial
    start_base = 0.0  #Base correspondiente a la compra inicial 
    pre_start = False #Controla que en la primera vela se compren la sunidades para stock 
    quote_up = 0.0
    quote_down = 0.0

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
                        'sn':'Par',},
                'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Compra inicial para stock',
                        'v' :'50',
                        't' :'perc',
                        'pub': True,
                        'sn':'Inicio', },
                'lot_to_safe': {
                        'c' :'lot_to_safe',
                        'd' :'Resguardo si supera la compra inicial',
                        'v' :'4',
                        't' :'perc',
                        'pub': True,
                        'sn':'Resguardo', },
                're_buy_perc': {
                        'c' :'re_buy_perc',
                        'd' :'Recompra luego de una venta',
                        'v' :'8',
                        't' :'perc',
                        'pub': True,
                        'sn':'Recompra', },

                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0:
            err.append("El Porcentaje de capital por operacion debe ser mayor a 0")
        if self.re_buy_perc <= 0 or self.re_buy_perc > 100:
            err.append("La recompra debe ser un valor mayor a 0 y menor o igual a 100")
        if self.lot_to_safe <= 0 or self.lot_to_safe > 100:
            err.append("El Resguardo debe ser un valor mayor a 0 y menor o igual a 100")

        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        self.klines['signal'] = 'NEUTRO'   
        self.print_orders = False
        self.graph_open_orders = True
    
    def next(self):
        price = self.price
        
        
        #Ajusta la billetera inicial para estockearse de Monedas
        #No hace operacion de Buy para que se puedan interpretar las ordenes
        if not self.pre_start:
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / price , self.qd_qty)
            self.wallet_base = qty
            self.wallet_quote = round(self.wallet_quote - price*qty,self.qd_quote)
            
            self.start_cash = round(price*qty , self.qd_quote)
            self.start_base = qty
            self.quote_up   = round_down(self.start_cash * (self.lot_to_safe/100) , self.qd_quote)
            self.quote_down = round_down(self.start_cash * (self.re_buy_perc/100) , self.qd_quote)
            if self.quote_up<12:
                raise "La orden debe ser mayor o igual a 12 USD. Incrementar el parametro [Resguardo si supera la compra inicial]"
            if self.quote_down<12:
                raise "La orden debe ser mayor o igual a 12 USD. Incrementar el parametro [Recompra luego de una venta]"
            self.pre_start = True 

        #Estrategia
        else:
            base_in_quote = round(self.wallet_base*price,self.qd_quote)            
        
            if base_in_quote > self.start_cash+self.quote_up:
                qty = round_down(self.quote_up/price, self.qd_qty)
                sell_order = self.sell(qty,Order.FLAG_TAKEPROFIT)
                    
            elif base_in_quote < self.start_cash-self.quote_down:
                qty = round_down((self.quote_down)/price, self.qd_qty)
                buy_order = self.buy(qty,Order.FLAG_STOPLOSS)

                
            