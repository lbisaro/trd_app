from bot.model_kline import *
import numpy as np
from scripts.Bot_Core import Bot_Core
from scripts.indicators import fibonacci_levels,zigzag
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class BotFibonacci(Bot_Core):

    symbol = ''
    quote_perc = 0.0
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
        self.deviation = 0
        self.interes = 's'  

        #Gestion de ordenes y posicion tomada
        self.position = False #Define si existe una posicion abierta
        self.orderid_sl = 0 #id de la orden de Stop-Loss
        self.orderid_tp = 0 #id de la orden de Take-Profit

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra y Venta por retroceso de Fibonacci, con stoploss en nivel 0.0 , '\
                  'Cierra la operación por Stop Loss o Señal de venta.'\
                  'El parametro -Desvio para Pivotes- se utiliza para definir los pivotes de precio con los que se calculan los retrocesos. '
    
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
                 'deviation': {
                        'c' :'deviation',
                        'd' :'Desvio para Pivotes',
                        'v' :'2',
                        't' :'perc',
                        'pub': True,
                        'sn':'Dev', },
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
        if self.deviation < 0.5 or self.deviation > 100:
            err.append("El Desvio para Pivotes debe ser un porcentaje entre 0.5 y 100")

        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        self.klines = zigzag(self.klines, deviation = self.deviation)

        self.klines['signal'] = ''
        #Obteniendo los keys de los niveles de Fibo con maximo y minimo al azar
        fib_levels = fibonacci_levels(1,0.5)
        for key in fib_levels.keys():
            self.klines[f'fl_{key}'] = np.nan

        last_zz = [0,0,0]
        buy_last_low = None
        buy_last_high = None
        sell_last_low = None
        sell_last_high = None

        for index, row in self.klines.iterrows():
            if row['ZigZag'] is not None and row['ZigZag'] > 0:
                                
                last_zz[2] = last_zz[1]
                last_zz[1] = last_zz[0]
                last_zz[0] = row['ZigZag']

                if last_zz[1] > last_zz[0] > last_zz[2]:
                    buy_last_low = last_zz[0]
                    buy_last_high = last_zz[1]
                
                if last_zz[1] < last_zz[0] < last_zz[2]:
                    sell_last_low = last_zz[1]
                    sell_last_high = last_zz[0]
                        
            if buy_last_low is not None and buy_last_high is not None:
                fib_levels = fibonacci_levels(buy_last_high,buy_last_low)
                for key in fib_levels.keys():
                    self.klines.at[index, f'fl_{key}'] = fib_levels[key]
                #if fib_levels['23.6%'] <= row['close'] <= fib_levels['38.2%']:
                if fib_levels['23.6%'] <= row['close'] <= fib_levels['38.2%']:
                    self.klines.at[index, 'signal'] = 'COMPRA'
                    buy_last_low = None
                    buy_last_high = None

            if sell_last_low is not None and sell_last_high is not None:
                fib_levels = fibonacci_levels(sell_last_low,sell_last_high)
                for key in fib_levels.keys():
                    self.klines.at[index, f'fl_{key}'] = fib_levels[key]
                if fib_levels['23.6%'] >= row['close'] >= fib_levels['38.2%']:
                    self.klines.at[index, 'signal'] = 'VENTA'
                    sell_last_low = None
                    sell_last_high = None

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
                stop_loss_price = round(self.row['fl_0.0%'] , self.qd_price)
                self.stop_loss = round((1-(stop_loss_price/self.price))*100,2)

                take_profit_price = round(self.row['fl_100.0%'] , self.qd_price)
                self.take_profit = round(((take_profit_price/self.price)-1)*100,2)
                
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
                    self.orderid_sl = self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price)
                    #self.orderid_tp = self.sell_limit(buyed_qty,Order.FLAG_TAKEPROFIT,take_profit_price) 
                
                    if self.orderid_sl == 0:
                        print('\033[31mERROR\033[0m',self.row['datetime'],'STOP-LOSS',buyed_qty,' ',quote_to_sell,self.wallet_quote)  
                    #if self.orderid_tp == 0:
                    #    print('\033[31mERROR\033[0m',self.row['datetime'],'TAKE-PROFIT',buyed_qty,' ',quote_to_sell,self.wallet_quote) 
                
                else:
                    print('\033[31mERROR\033[0m',self.row['datetime'],'BUY price',self.price,'USD',quote_to_sell,self.wallet_quote)

        if signal == 'VENTA':
            self.close(Order.FLAG_SIGNAL)
            self.cancel_orders()
            self.position = False
