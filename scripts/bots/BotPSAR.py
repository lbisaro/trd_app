from bot.model_kline import *
import pandas as pd
from scripts.functions import round_down
from scripts.Bot_Core import Bot_Core
from scripts.Bot_Core_utils import *
import scripts.indicators as ind

class BotPSAR(Bot_Core):

    short_name = 'PSAR'
    symbol = ''
    ma = 0          #Periodos para Media movil simple 
    quote_perc =  0 #% de compra inicial, para stock


    last_order_id = 0
    
    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        
    
    descripcion = 'Bot PSAR'
    
    parametros = {'symbol':  {  
                        'c' :'symbol',
                        'd' :'Par',
                        'v' :'BTCUSDT',
                        't' :'symbol',
                        'pub': True,
                        'sn':'Par', },
                  'quote_perc': {
                        'c' :'quote_perc',
                        'd' :'Compra',
                        'v' :'95',
                        'l' :'[10,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'Inicio', },
                'stop_loss': {
                        'c' :'stop_loss',
                        'd' :'Stop Loss',
                        'v' :'0.5',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'SL', },
                'take_profit': {
                        'c' :'take_profit',
                        'd' :'Take Profit',
                        'v' :'10',
                        'l' :'[0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'TP', },
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
        self.klines['ema'] = self.klines['close'].ewm(span=10).mean()
        self.klines = ind.psar(self.klines,af0=0.02,af=0.2)
        self.klines = ind.supertrend(self.klines)
        
        self.klines['signal'] = np.where((self.klines['psar_low']>0) 
                                         & (self.klines['psar_high'].shift(1)>0)
                                         #& (self.klines['st_low']>0)
                                         ,'COMPRA','NEUTRO')
              
        self.print_orders = False
        self.graph_open_orders = True
        self.graph_signals = True


    
    def next(self):
        open_orders = len(self._orders)
        if self.row['signal'] == 'COMPRA' and open_orders < 1: 
            qty = round_down((self.wallet_quote * (self.quote_perc/100)) / self.price , self.qd_qty)
            #self.buy_limit(qty=qty,limit_price = self.row['ema'],flag=Order.FLAG_TAKEPROFIT,tag='BUY')
            self.buy(qty=qty,flag=Order.FLAG_SIGNAL,tag='BUY')

        mddpos = 4
        if 'pos___pnl_max' in self.status:
            if self.status['pos___pnl_max']['r'] > mddpos:
                mddpos = self.status['pos___pnl_max']['r']/4
        if 'pos___pnl' in self.status and self.status['pos___pnl_max']['r']> mddpos:
            if self.status['pos___pnl_max']['r']-self.status['pos___pnl']['r'] > mddpos:
                self.close(flag=Order.FLAG_TAKEPROFIT)
                self.cancel_orders()


    def on_order_execute(self,order):
        if order.tag == 'BUY':
            qty = order.qty
            #sl_price = round(order.price*(1-self.stop_loss/100) , self.qd_price)
            sl_price = round(order.price*(1-self.stop_loss/100) , self.qd_price)
            tp_price = round(order.price*(1+self.take_profit/100) , self.qd_price)
            self.sell_limit(qty=qty,flag=Order.FLAG_STOPLOSS,limit_price=sl_price,tag='STOP_LOSS')
            self.sell_limit(qty=qty,flag=Order.FLAG_TAKEPROFIT,limit_price=tp_price,tag='TAKE_PROFIT')

        if order.tag == 'TAKE_PROFIT' or order.tag == 'STOP_LOSS':
            self.cancel_orders()

            
            