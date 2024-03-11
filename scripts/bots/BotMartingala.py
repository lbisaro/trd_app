from bot.model_kline import *
import pandas as pd
import numpy as np
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *
import datetime as dt
from scripts.functions import round_down
from scripts.indicators import find_pivots

class BotMartingala(Bot_Core):

    symbol = ''
    qty_pos = 0
    mult_pos = 0.0
    mult_perc = 0.0
    stop_loss = 0.0
    take_profit = 0.0

    sell_bt_orderid = 0
    sell_tp_orderid = 0
    stop_loss_over_quote = 0
    block_by_stop_loss = False


    descripcion = 'Bot Core v2 \n'\
                  'Bot de Martingala.'
        
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Sym',},
                 'qty_pos': {
                        'c' :'qty_pos',
                        'd' :'Cantidad de posiciones',
                        'v' :'5',
                        't' :'int',
                        'pub': True,
                        'sn':'Pos', },
                 'mult_pos': {
                        'c' :'mult_pos',
                        'd' :'Multiplicador de compra',
                        'v' :'2',
                        't' :'float',
                        'pub': True,
                        'sn':'Mult.Pos', },
                 'mult_perc': {
                        'c' :'mult_perc',
                        'd' :'Multiplicador Porcentaje',
                        'v' :'0.5',
                        't' :'float',
                        'pub': True,
                        'sn':'Mult.Perc', },
                'take_profit': {
                        'c' :'take_profit',
                        'd' :'Take Profit',
                        'v' :'1',
                        't' :'perc',
                        'pub': True,
                        'sn':'TP', },
                 'stop_loss': {
                        'c' :'stop_loss',
                        'd' :'Stop Loss',
                        'v' :'4',
                        't' :'perc',
                        'pub': True,
                        'sn':'SL', },

                }
    
    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.qty_pos <= 2 or self.qty_pos > 10:
            err.append("La cantidad de posiciones debe ser un valor entre 2 y 10")
        if self.mult_pos < 1 or self.mult_pos > 5:
            err.append("Multiplicador de compra debe ser un valor entre 1 y 5")
        if self.mult_perc <= 0 or self.mult_perc > 10:
            err.append("Multiplicador de porcentaje debe ser un valor entre 0.01 y 10")
        if self.stop_loss < 0 or self.stop_loss > 100:
            err.append("El Stop Loss debe ser un valor entre 0 y 100")
        if self.take_profit < 0 or self.take_profit > 100:
            err.append("El Take Profit debe ser un valor entre 0 y 100")
        
        if len(err):
            raise Exception("\n".join(err))

    def calculate_pos(self,quote, qty_pos, mult):
        pos = []
        for i in range(qty_pos):
            pos_amount = quote * (1 - (1 / mult)) / (1 - 1 / mult**(qty_pos - i))
            pos.append(round(pos_amount, 2))
            quote -= pos_amount
        return pos[::-1]  # Invierte la lista
    
    def start(self):
        self.klines = find_pivots(self.klines)
        self.klines['signal'] = np.where(self.klines['max_pivots']>0,'VENTA','NEUTRO')
        self.klines['signal'] = np.where(self.klines['min_pivots']>0,'COMPRA',self.klines['signal'])
        self.print_orders = False
        self.block_by_stop_loss = False
        self.graph_open_orders = False
        self.graph_signals = True
        
        self.reset_pos()

    
    def reset_pos(self):
        self.cancel_orders()
        self.sell_tp_orderid = 0
        self.sell_sl_orderid = 0
        self.compras = {}
        self.stop_loss_over_quote = 0

    def next(self):
         
        price = self.price

        if len(self.compras) == 0 and self.row['min_trend'] > 0:  #Inicia la posicion
            if not self.block_by_stop_loss:
                self.quote_pos = self.calculate_pos((self.quote_qty*0.7), self.qty_pos, self.mult_pos)
                            
                quote_to_sell = round_down(self.quote_pos[0] , self.qd_quote ) 
                base_to_buy = round_down((quote_to_sell/price) , self.qd_qty) 
                buy_orderid = self.buy(base_to_buy,Order.FLAG_SIGNAL)
                if buy_orderid>0:
                    self.compras[0] = {'orderid':buy_orderid}
                    order = self.get_order(buy_orderid)
                    buyed_qty = order.qty
                    
                    if self.stop_loss>0:
                        self.stop_loss_over_quote = self.wallet_quote * (self.stop_loss/100)
                        if self.stop_loss_over_quote < quote_to_sell:
                            stop_loss_quote = quote_to_sell-self.stop_loss_over_quote
                            stop_loss_price = round(stop_loss_quote/base_to_buy , self.qd_price)
                            self.sell_sl_orderid = self.sell_limit(buyed_qty,Order.FLAG_STOPLOSS,stop_loss_price)
                            
                    
                    take_profit_price = round(self.price + self.price*(self.take_profit/100) , self.qd_price)
                    self.sell_tp_orderid = self.sell_limit(buyed_qty,Order.FLAG_TAKEPROFIT,take_profit_price)                

                    o_price = self.price
                    for compra in range(1, self.qty_pos):
                        o_price = o_price - self.price*((self.mult_perc*compra)/100)
                        palanca_price = round(o_price,self.qd_price)
                        quote_to_sell = round(self.quote_pos[compra] , self.qd_quote ) 
                        base_to_buy = round_down((quote_to_sell/palanca_price) , self.qd_qty) 
                        buy_orderid = self.buy_limit(base_to_buy,Order.FLAG_SIGNAL,palanca_price) 
                        self.compras[compra] = {'orderid':buy_orderid}
                
        elif len(self.compras) > 0 and self.signal == 'VENTA':
            self.close(Order.FLAG_SIGNAL)
            

        return round(self.wallet_base*price + self.wallet_quote,2)


    def on_order_execute(self,order):
        #Venta por stop-loss
        if self.stop_loss>0 and self.order_status(self.sell_sl_orderid) == Order.STATE_COMPLETE:
            self.block_by_stop_loss = True
            self.reset_pos()
        
        #Venta por take-profit
        elif self.take_profit>0 and self.order_status(self.sell_tp_orderid) == Order.STATE_COMPLETE:
            self.reset_pos()
        
        #Ejecuto una compra
        else:
            tot_quote = 0
            tot_base = 0
            for i in self.compras:
                orderid = self.compras[i]['orderid']
                if self.order_status(orderid) == Order.STATE_COMPLETE:
                    order = self.get_order(orderid)
                    tot_quote += (order.qty * order.price)
                    tot_base += order.qty
            
            if tot_base>0:
                
                avg_price = tot_quote/tot_base
                #Recalcular STOP-LOSS y TAKE-PROFIT
                quote_to_sell = round_down(tot_quote , self.qd_quote ) 
                if self.stop_loss:
                    if self.stop_loss_over_quote < quote_to_sell:
                        stop_loss_quote = quote_to_sell-self.stop_loss_over_quote
                        stop_loss_price = round(stop_loss_quote/tot_base , self.qd_price)
                        self.cancel_order(self.sell_sl_orderid)
                        self.sell_sl_orderid = self.sell_limit(tot_base,Order.FLAG_STOPLOSS,stop_loss_price)

                take_profit_price = round(avg_price + avg_price*(self.take_profit/100) , self.qd_price)
                self.cancel_order(self.sell_tp_orderid)
                self.sell_tp_orderid = self.sell_limit(tot_base,Order.FLAG_TAKEPROFIT,take_profit_price) 