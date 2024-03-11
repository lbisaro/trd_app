from bot.model_kline import *
import numpy as np
from scripts.Bot_Core import Bot_Core
from scripts.indicators import Fibonacci
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class BotFibonacci(Bot_Core):

    symbol = ''
    quote_perc = 0.0
    interes = ''
    trail = 1

    #Gestion de ordenes y posicion tomada
    position = False #Define si existe una posicion abierta
    orderid_sl = 0 #id de la orden de Stop-Loss
    orderid_tp = 0 #id de la orden de Take-Profit

    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.interes = '' 
        self.trail = 0       

        #Gestion de ordenes y posicion tomada
        self.position = False #Define si existe una posicion abierta
        self.orderid_sl = 0 #id de la orden de Stop-Loss
        self.orderid_tp = 0 #id de la orden de Take-Profit

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra por nivel de Fibonacci, con stoploss en nivel 0.0 y take-profit en nivel 0.1, '\
                  'Cierra la operación por Stop Loss o Take Profit (Si se definen con un % mayor a cero) '\
                  'Opcionalmente opera con trailing para SL y TP '
    
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
                        't' :'perc',
                        'pub': True,
                        'sn':'Quote', },
                 'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'c',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },
                'trail': {
                        'c' :'trail',
                        'd' :'Trail',
                        'v' : 1,
                        't' :'bin',
                        'pub': True,
                        'sn':'Trail', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.interes != 'c' and self.interes != 's':
            err.append("Se debe establecer el tipo de interes. (Simple o Compuesto)")

        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        
        self.klines = Fibonacci().long(self.klines)
        self.klines['signal'] = np.where(self.klines['fibo']==1,'COMPRA','NEUTRO')
        self.print_orders = False
        self.graph_open_orders = True


    def next(self):
        signal = self.signal
        price = self.price

        #Si no existe la orden de SL o TP es porque se ejecuto, entonces se cancelan las ordenes abiertas y se resetea la posicion
        if (self.orderid_sl > 0 and self.orderid_sl not in self._orders) or (self.orderid_tp > 0 and self.orderid_tp not in self._orders) :
            self.cancel_orders()
            self.position = False
            
        if not self.position:
            if signal == 'COMPRA':
                #Analisis del riesgo a tomar

                stop_loss_price = round(self.row['fibo_1.000'] , self.qd_price)
                self.stop_loss = round((1-(stop_loss_price/self.price))*100,2)

                take_profit_price = round(self.row['fibo_0.000'] , self.qd_price)
                self.take_profit = round(((take_profit_price/self.price)-1)*100,2)

                quote_perc = self.quote_perc
                if self.stop_loss > 3:
                    quote_perc = self.quote_perc/2
                elif self.stop_loss > 8:
                    quote_perc = self.quote_perc/3

                if self.take_profit/self.stop_loss > 1.5:
                
                    if self.interes == 's': #Interes Simple
                        quote_qty = self.quote_qty if self.wallet_quote >= self.quote_qty else self.wallet_quote
                        quote_to_sell = round_down(quote_qty*(quote_perc/100) , self.qd_quote )
                    elif self.interes == 'c': #Interes Compuesto
                        quote_to_sell = round_down(self.wallet_quote*(quote_perc/100) , self.qd_quote ) 
                    
                    quote_to_sell = round_down(quote_to_sell , self.qd_quote ) 
                    base_to_buy = round_down((quote_to_sell/price) , self.qd_qty) 
                
                    orderid_buy = self.buy(base_to_buy,Order.FLAG_SIGNAL)
                    if orderid_buy > 0:

                        buyed_qty = self._trades[orderid_buy].qty
                        
                        self.position = True
                        if self.trail > 0:
                            trail_stop = self.stop_loss# if self.stop_loss <= 2 else 2 
                            self.orderid_sl = self.sell_trail(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price,0,trail_stop)
                            #self.orderid_tp = self.sell_trail(buyed_qty,Order.FLAG_TAKEPROFIT,take_profit_price,self.price,self.take_profit) 
                       
                        else:
                            self.orderid_sl = self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price)
                            self.orderid_tp = self.sell_limit(buyed_qty,Order.FLAG_TAKEPROFIT,take_profit_price) 
                        
                        if self.orderid_sl == 0:
                            print('\033[31mERROR\033[0m',self.row['datetime'],'STOP-LOSS',buyed_qty,' ',quote_to_sell,self.wallet_quote)  
                        if self.trail == 0 and self.orderid_tp == 0:
                            print('\033[31mERROR\033[0m',self.row['datetime'],'TAKE-PROFIT',buyed_qty,' ',quote_to_sell,self.wallet_quote) 
                    
                    else:
                        print('\033[31mERROR\033[0m',self.row['datetime'],'BUY price',self.price,'USD',quote_to_sell,self.wallet_quote)
            
