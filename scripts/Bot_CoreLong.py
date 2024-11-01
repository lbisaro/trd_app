from bot.model_kline import *
import pandas as pd
from scripts.Bot_Core import Bot_Core
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class Bot_CoreLong(Bot_Core):

    symbol = ''
    quote_perc = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    interes = ''

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

        #Gestion de ordenes y posicion tomada
        self.position = False #Define si existe una posicion abierta
        self.orderid_sl = 0 #id de la orden de Stop-Loss
        self.orderid_tp = 0 #id de la orden de Take-Profit

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra, '\
                  'y cierra la operación por Stop Loss o Take Profit (Si se definen con un % mayor a cero) '\
                  'o cuando recibe una señal de Venta.'
    
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
                        't' :'perc',
                        'pub': True,
                        'sn':'Quote', },
                'stop_loss': {
                        'c' :'stop_loss',
                        'd' :'Stop Loss',
                        'v' :'3',
                        't' :'perc',
                        'pub': True,
                        'sn':'SL', },
                'take_profit': {
                        'c' :'take_profit',
                        'd' :'Take Profit',
                        'v' :'6',
                        't' :'perc',
                        'pub': True,
                        'sn':'TP', },
                'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'c',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },

                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.stop_loss < 0 or self.stop_loss > 100:
            err.append("El Stop Loss debe ser un valor entre 0 y 100")
        if self.take_profit < 0 or self.take_profit > 100:
            err.append("El Take Profit debe ser un valor entre 0 y 100")
        if self.interes != 'c' and self.interes != 's':
            err.append("Se debe establecer el tipo de interes. (Simple o Compuesto)")

        if len(err):
            raise Exception("\n".join(err))

    def next(self):
        signal = self.signal
        price = self.price

        #Si no existe la orden de SL o TP es porque se ejecuto, entonces se cancelan las ordenes abiertas y se resetea la posicion
        if (self.orderid_sl > 0 and self.orderid_sl not in self._orders) or (self.orderid_tp > 0 and self.orderid_tp not in self._orders) :
            self.cancel_orders()
            self.position = False
            
        if not self.position:
            if signal == 'COMPRA':
                if self.interes == 's': #Interes Simple
                    quote_qty = self.quote_qty if self.wallet_quote >= self.quote_qty else self.wallet_quote
                    quote_to_sell = round_down(quote_qty*(self.quote_perc/100) , self.qd_quote )
                elif self.interes == 'c': #Interes Compuesto
                    quote_to_sell = round_down(self.wallet_quote*(self.quote_perc/100) , self.qd_quote ) 
                
                quote_to_sell = round_down(quote_to_sell , self.qd_quote ) 
                base_to_buy = round_down((quote_to_sell/price) , self.qd_qty) 
                
                orderid_buy = self.buy(base_to_buy,Order.FLAG_SIGNAL)
                if orderid_buy > 0:

                    buyed_qty = self._trades[orderid_buy].qty
                    
                    self.position = True
                    if self.stop_loss:
                        stop_loss_price = round(self.price - self.price*(self.stop_loss/100) , self.qd_price)
                        self.orderid_sl = self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price)
                        if self.orderid_sl == 0:
                            print('\033[31mERROR\033[0m',self.row['datetime'],'STOP-LOSS',buyed_qty,' ',quote_to_sell,self.wallet_quote)  

                    if self.take_profit:
                        take_profit_price = round(self.price + self.price*(self.take_profit/100) , self.qd_price)
                        self.orderid_tp = self.sell_limit(buyed_qty,Order.FLAG_TAKEPROFIT,take_profit_price) 
                        if self.orderid_tp == 0:
                            print('\033[31mERROR\033[0m',self.row['datetime'],'TAKE-PROFIT',buyed_qty,' ',quote_to_sell,self.wallet_quote) 
                else:
                    print('\033[31mERROR\033[0m',self.row['datetime'],'BUY price',self.price,'USD',quote_to_sell,self.wallet_quote)
            
        else:
            if signal == 'VENTA':
                base_to_sell = self.wallet_base
                orderid_sell = self.close(Order.FLAG_SIGNAL)
                if orderid_sell > 0:
                    self.cancel_orders()
                    self.position = False
                else:
                    print(self.row['datetime'],'SELL price',self.price,'USD',base_to_sell*self.price)
                    print('ERROR')




