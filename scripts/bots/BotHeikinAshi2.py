from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *
import datetime as dt
from scripts.indicators import HeikinAshi


class BotHeikinAshi2(Bot_Core):

    short_name = 'HAL'
    symbol = ''
    quote_perc =  0 
    quote_perc_down = 0 
    interes = 's'


    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.interes = 's'


    
    descripcion = 'Bot basado en velas Heikin Ashi\n'\
                  'Genera señales de compra con los cambios de tendencia\n'\
                  'Cierra la operación por Stop Loss dinamico'
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par',},
                'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Lote de compras (%)',
                        'v' :'50',
                        't' :'perc',
                        'pub': True,
                        'sn':'Compra', },
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
        if self.quote_perc <= 0:
            err.append("El Porcentaje de Lote Compra debe ser mayor a 0")


        
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):

        df = HeikinAshi(self.klines)
        df['ma_vol'] = df['volume'].rolling(window=100).mean()
        
        #V2 mejorada
        df['HA_sl'] =  np.where((df['HA_side']==1) & (df['HA_side'].shift(1)==1),df['HA_low'].shift(2),None)
        df['HA_tp'] =  np.where((df['HA_side']==-1) & (df['HA_side'].shift(1)==-1),df['HA_high'].shift(2),None)
        df['HA_sl'].ffill(inplace=True)
        df['HA_tp'].ffill(inplace=True)
        buy_cond = (
                     (df['HA_low']>df['HA_tp'])
                   & (df['HA_sl'].shift(1)<df['HA_tp'].shift(1)) 
                   & (df['HA_sl']!=df['HA_sl'].shift(1))
                   #& (df['volume'] > df['ma_vol']) #Volumen por sobre la media de 100
                   )
        df['buy'] = np.where(buy_cond,1,None)
        self.klines['HA_side'] = df['HA_side']
        self.klines['buy'] = df['buy']
        self.klines['stop_loss'] = df['HA_tp']
        self.klines['signal'] = np.where(self.klines['buy']==1,'COMPRA','NEUTRO')   


        #V3 testing
        #df['HA_sl'] =  np.where((df['HA_side']>=0)  & (df['HA_side'].shift(1)>=0),df['HA_low'].shift(2),None)
        #df['HA_sl'] = np.where((df['HA_sl'].isnull()) & (df['close'])>df['open'],df['HA_sl'].shift(1),df['HA_sl'])
        #df['buy'] = np.where((df['HA_sl']>df['HA_tp']) & (df['HA_sl'].shift(1)<df['HA_tp'].shift(1)) & (df['HA_sl']!=df['HA_sl'].shift(1)),1,None)
        #self.klines['HA_side'] = df['HA_side']
        #self.klines['buy'] = df['buy']
        #self.klines['stop_loss'] = df['HA_tp']
        #self.klines['signal'] = np.where(self.klines['buy']==1,'COMPRA','NEUTRO')   

        self.print_orders = False
        self.graph_open_orders = True
        self.graph_signals = False
        
    def get_status(self):
        status_datetime = dt.datetime.now()
        status = super().get_status()
        
        if self.signal != 'NEUTRO':
            if self.signal == 'COMPRA':
                cls = 'text-success'
            else: 
                cls = 'text-danger'
            status['signal'] = {'l': 'Ultima señal','v': self.signal+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.signal, 'cls': cls}
        
        if 'HA_side' in self.row:
            if self.row['HA_side'] > 0:
                cls = 'text-success'
                trend = 'Alza'
            else: 
                cls = 'text-danger'
                trend = 'Baja'
            status['trend'] = {'l': 'Tendencia','v': trend+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.row['HA_side'], 'cls': cls}

        return status    

    def next(self):
        last_buy = 0.0
        if 'last_buy' in self.status:
            last_buy = self.status['last_buy']['r']
    
        price = self.price
        start_cash = round(self.quote_qty ,self.qd_quote)
        
        if self.signal == 'COMPRA' and price > last_buy*1.01:
            if self.interes == 's': #Interes Simple
                cash = start_cash if start_cash <= self.wallet_quote else self.wallet_quote
            else: #Interes Compuesto
                cash = self.wallet_quote

            lot_to_buy = cash * (self.quote_perc/100)
            if lot_to_buy <= self.wallet_quote and lot_to_buy > 12:
                qty = round_down(lot_to_buy/self.price,self.qd_qty)
                buy_order_id = self.buy(qty,Order.FLAG_SIGNAL)
                if buy_order_id:
                    sell_order = self.get_order_by_tag(tag='STOP_LOSS')
                    limit_price = round(self.row['stop_loss'],self.qd_price)
                    buy_order = self._trades[buy_order_id]
                    self.status['last_buy'] = {'l': 'Ultima compra','r': buy_order.price,'v': buy_order.price}
                    if sell_order:
                        self.update_order_by_tag(tag="STOP_LOSS",limit_price=limit_price,qty=self.wallet_base)
                    else:
                        self.sell_limit(qty, Order.FLAG_STOPLOSS, limit_price = limit_price,tag="STOP_LOSS")
                    
        elif price*self.wallet_base > 10:
            limit_price = round(self.row['stop_loss'],self.qd_price)
            self.update_order_by_tag(tag="STOP_LOSS",limit_price=limit_price,qty=self.wallet_base)
        
    def on_order_execute(self, order):
        if order.side == Order.SIDE_SELL and 'last_buy' in self.status:
            del self.status['last_buy']
            
            