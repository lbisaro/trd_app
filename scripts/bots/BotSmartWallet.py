from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotSmartWallet(Bot_Core):

    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock
    re_buy_perc = 0 #% para recompra luego de una venta
    lot_to_safe = 0 #% a resguardar si supera start_cash

    op_last_price = 0
    
    start_cash = 0.0  #Cash correspondiente a la compra inicial
    pre_start = False #Controla que en la primera vela se compren la sunidades para stock 

    def __init__(self):
        self.symbol = ''
        self.ma = 0
        self.quote_perc = 0.0
        self.re_buy_perc = 0.0
        self.lot_to_safe = 0.0  
    
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
                        'v' :'3',
                        't' :'perc',
                        'pub': True,
                        'sn':'Resguardo', },
                're_buy_perc': {
                        'c' :'re_buy_perc',
                        'd' :'Recompra luego de una venta',
                        'v' :'3',
                        't' :'perc',
                        'pub': True,
                        'sn':'Recompra', },
                'ma': {
                        'c' :'ma',
                        'd' :'Periodo de la Media Simple',
                        'v' :'14',
                        't' :'int',
                        'pub': True,
                        'sn':'MA', },

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
        if self.ma <= 0:
            err.append("Se debe establecer un periodo de MA mayor a 0")
        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        self.klines['sma'] = self.klines['close'].rolling(self.ma).mean()  
        self.klines['signal'] = 'NEUTRO'   

        self.print_orders = False 
        self.graph_open_orders = False
    
    def next(self):
        price = self.price
        avg_price = (self.row['high']+self.row['low'])/2
        sma = self.row['sma']
        
        #Ajusta la billetera inicial para estockearse de Monedas
        #No hace operacion de Buy para que se puedan interpretar las ordenes
        if not self.pre_start:
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / price , self.qd_qty)
            self.wallet_base = qty
            self.wallet_quote = round(self.wallet_quote - price*qty,self.qd_quote)
            
            self.start_cash = round(price*qty,self.qd_quote)
            self.pre_start = True 

        #Estrategia
        else:
            hold = round(self.wallet_base*price,self.qd_quote)

            if avg_price > sma and hold > self.start_cash*(1+(self.lot_to_safe/100)):
                qty = round_down((hold - self.start_cash)/price, self.qd_qty)
                limit_price = price*(1-(self.re_buy_perc*2/100))
                self.sell(qty,Order.FLAG_TAKEPROFIT)
                self.buy_limit(qty,Order.FLAG_SIGNAL,limit_price)


            elif avg_price < sma and hold < self.start_cash*(1-(self.lot_to_safe/100)):
                qty = self.wallet_base*(self.lot_to_safe*2/100)
                if qty*price > 12 : #Intenta recomprar solo si la compra es por las de 12 dolares
                    self.op_last_price = avg_price
                    limit_price = price*(1-(self.re_buy_perc/100))
                    self.sell(qty,Order.FLAG_STOPLOSS)
                    self.buy_limit(qty,Order.FLAG_SIGNAL,limit_price)