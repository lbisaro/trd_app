from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *

class BotLiveTest(Bot_Core):

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
        
        self.last_order_id = -1
        self.trail_b = 2
        self.trail_s = 2
    
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
        self.graph_open_orders = False
    
    def next(self):
        #self.alterna_compra_venta_market()
        self.compra_sl_tp()
    
    def on_order_execute(self,order):
        self.cancel_orders()

    def compra_sl_tp(self):
        wallet_base_in_quote = self.wallet_base*self.price
        if wallet_base_in_quote < 10:
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / self.price , self.qd_qty)
            self.last_order_id = self.buy(qty=qty,flag=Order.FLAG_SIGNAL)

            buy_order = self._trades[self.last_order_id]
            buy_price = buy_order.price
            
            limit_price = round(buy_price*1.01,self.qd_price)
            self.sell_limit(qty,Order.FLAG_TAKEPROFIT,limit_price)
            limit_price = round(buy_price*0.99,self.qd_price)
            self.sell_limit(qty,Order.FLAG_STOPLOSS,limit_price)
    
    def alterna_compra_venta_market(self):
        wallet_base_in_quote = self.wallet_base*self.price
        if wallet_base_in_quote < 10:
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / self.price , self.qd_qty)
            self.last_order_id = self.buy(qty=qty,flag=Order.FLAG_TAKEPROFIT)
            print('BUY  qty: ',qty,' order_id: ',self.last_order_id)
            #self.last_order_id = self.buy_trail(qty=qty,
            #                                    flag=Order.FLAG_TAKEPROFIT,
            #                                    limit_price=self.price * (1+(self.trail_b/3/100)),
            #                                    activation_price=0,
            #                                    trail_perc = self.trail_b)
        else:
            qty = self.wallet_base
            self.last_order_id = self.sell(qty=qty,flag=Order.FLAG_SIGNAL)
            print('SELL qty: ',qty,' order_id: ',self.last_order_id)
            #self.last_order_id = self.sell_trail(qty=qty,
            #                                    flag=Order.FLAG_TAKEPROFIT,
            #                                    limit_price=self.price * (1-(self.trail_s/3/100)),
            #                                    activation_price=0,
            #                                    trail_perc = self.trail_s)
            
            