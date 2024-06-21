from bot.model_kline import *
import numpy as np
from ..Bot_CoreLong import Bot_CoreLong
from scripts.functions import round_down
from scripts.Bot_Core_utils import Order
from scripts.indicators import supertrend


class BotLongVolatility(Bot_CoreLong):

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
                        'sn':'Par',},
                'buy_lot': {
                        'c' :'buy_lot',
                        'd' :'Compra %',
                        'v' :'10',
                        't' :'perc',
                        'pub': True,
                        'sn':'Compra', },
                'sell_lot': {
                        'c' :'sell_lot',
                        'd' :'Venta %',
                        'v' :'50',
                        't' :'perc',
                        'pub': True,
                        'sn':'Venta', },
                #'interes': {
                #        'c' :'interes',
                #        'd' :'Tipo de interes',
                #        'v' :'s',
                #        't' :'t_int',
                #        'pub': True,
                #        'sn':'Int', },

                }
    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.buy_lot <= 0 or self.buy_lot > 100:
            err.append("La compra debe ser un valor mayor a 0 y menor o igual a 100")
        if self.sell_lot <= 0 or self.sell_lot > 100:
            err.append("La venta debe ser un valor mayor a 0 y menor o igual a 100")
        
        if len(err):
            raise Exception("\n".join(err))
    
    def start(self):
        periods = 21
        self.klines['pnl'] = None
        self.klines['hl_perc'] = (self.klines['high']-self.klines['low'])/((self.klines['high']+self.klines['low']/2))*100
        self.klines['oc_perc'] = (abs(self.klines['open']-self.klines['close']))/((self.klines['open']+self.klines['close']/2))*100
        self.klines['volat'] = (self.klines['hl_perc']+self.klines['oc_perc'])/2

        self.klines['vlt_mean'] = self.klines['volat'].rolling(window=periods).mean()
        self.klines['vlt_std'] = self.klines['volat'].rolling(window=periods).std()
        self.klines['vlt_high'] = self.klines['vlt_mean']+(self.klines['vlt_std']/2)
        self.klines['vlt_low'] = self.klines['vlt_mean']#-(self.klines['vlt_std'])

        self.klines['signal'] = np.where((self.klines['volat']>self.klines['vlt_high'])&(self.klines['open']>self.klines['close']),'COMPRA',None)
        self.klines['signal'] = np.where((self.klines['volat']>self.klines['vlt_high'])&(self.klines['close']>self.klines['open']),'VENTA',self.klines['signal'])
        
        self.klines = supertrend(self.klines,length=7,multiplier=3)  

    def next(self):
        price = self.price

        hold = round(self.wallet_base*price,self.qd_quote)
        """
        if 'signal' in self.row and self.signal == 'COMPRA' and self.row['st_trend'] < 0:
            
            cash_to_buy = self.wallet_quote*(self.buy_lot/100)

            qty = round_down(cash_to_buy/self.price,self.qd_qty)
            self.buy(qty,Order.FLAG_SIGNAL)
        
        if 'signal' in self.row and self.signal == 'VENTA' and self.row['st_trend'] > 0:
            
            base_to_sell = self.wallet_base*(self.sell_lot/100)

            qty = round_down(base_to_sell,self.qd_qty)
            self.sell(qty,Order.FLAG_TAKEPROFIT)
        
        if 'signal' in self.row and self.wallet_base and self.row['st_trend'] < 0:
            self.close(Order.FLAG_SIGNAL)
        """
                
