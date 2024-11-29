from bot.model_kline import *
import numpy as np
import datetime as dt
from scripts.Bot_Core import Bot_Core
from scripts.indicators import zigzag, fibonacci_extension
from scripts.functions import round_down
from scripts.Bot_Core_utils import *

class BotFibonacci(Bot_Core):

    short_name = 'Fibo'
    symbol = ''
    quote_perc = 0.0
    interes = ''
    rsmpl = 0
    trail = 0

    indicadores = [
            {'col': 'ZigZag', 'name': 'ZigZag', 'color': 'white', 'row': 1,  'mode':'lines',},             
            ]
    
    fb_levels = [0.0,        
                 0.236,      
                 0.382, 
                 0.5, 
                 0.618, 
                 0.786,
                 1.0, 
                 1.272, 
                 1.618, 
                 2.0, 
                 2.618
                 ]

    def __init__(self):
        self.symbol = ''
        self.quote_perc = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.interes = 's'  
        self.rsmpl = 0
        self.trail = 0

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra por Extension de Fibonacci, con stoploss en nivel 0.0 , '\
                  'Cierra la operación por Stop Loss o Señal de venta.'
    
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
                        'l' :'[10,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'Quote', },
                 'interes': {
                        'c' :'interes',
                        'd' :'Tipo de interes',
                        'v' :'s',
                        't' :'t_int',
                        'pub': True,
                        'sn':'Int', },
                 'rsmpl': {
                        'c' :'rsmpl',
                        'd' :'Resample para Pivots',
                        'v' : '4',
                        'l' :'[1,100]',
                        't' :'int',
                        'pub': True,
                        'sn':'Rsmp', },
                 'trail': {
                        'c' :'trail',
                        'd' :'Trail para posicion',
                        'v' : '4',
                        'l' :'(0,100]',
                        't' :'perc',
                        'pub': True,
                        'sn':'TRL', },
                }

    def valid(self):
        err = []
        if len(self.symbol) < 1:
            err.append("Se debe especificar el Par")
        if self.quote_perc <= 0 or self.quote_perc > 100:
            err.append("El Porcentaje de capital por operacion debe ser un valor entre 0.01 y 100")
        if self.rsmpl < 1:
            err.append("Se debe especificar el Resample >= 1")
        if self.trail < 1:
            err.append("Se debe especificar el Trail >= 1")
        if len(err):
            raise Exception("\n".join(err))
        
    def start(self):
        
        self.klines = zigzag(self.klines, resample_periods=self.rsmpl)
 
        #Detectando pivots para analisis de fibonacci
        pivots = self.klines[self.klines['ZigZag']>0].copy()
        pivots['pivots'] = pivots['ZigZag'].copy()
        pivots['fb_0'] = pivots['ZigZag'].copy()
        pivots['fb_1'] = pivots['ZigZag'].shift(1)
        pivots['fb_2'] = pivots['ZigZag'].shift(2)

        #Cambios de tendencia
        pivots['trend'] = np.where((pivots['fb_0']>pivots['fb_2']) & (pivots['fb_1']>pivots['fb_0']), 2,0)
        pivots['trend'] = np.where((pivots['fb_0']>pivots['fb_2']) & (pivots['fb_1']<pivots['fb_0']), 1,pivots['trend'])
        pivots['trend'] = np.where((pivots['fb_0']<pivots['fb_2']) & (pivots['fb_1']<pivots['fb_0']),-2,pivots['trend'])
        pivots['trend'] = np.where((pivots['fb_0']<pivots['fb_2']) & (pivots['fb_1']>pivots['fb_0']),-1,pivots['trend'])
        first_pivot_index = pivots.index[0]
        pivots.at[first_pivot_index,'trend'] = 0 #El primer pivot no se puede definir por lo tanto queda neutro

        #Completando el datafame principal con los datos de pivots
        df_cols = self.klines.columns.copy()
        for col in pivots.columns:
            if not col in df_cols:
                self.klines[col]=None
        for index, row in pivots.iterrows():
            for col in pivots.columns:
                if not col in df_cols:
                    self.klines.at[index,col] = row[col]

        self.klines['signal'] = np.where(self.klines['trend'] ==  2, 'COMPRA' , 'NEUTRO')
        self.klines['signal'] = np.where(self.klines['trend'] == -2, 'VENTA' , self.klines['signal'])

        self.klines['trend'].ffill(inplace=True)
        self.klines['fb_0'].ffill(inplace=True)
        self.klines['fb_1'].ffill(inplace=True)
        self.klines['fb_2'].ffill(inplace=True)

        self.klines['long_fbe_0'] = np.where(self.klines['trend']==2, self.klines['fb_0'] , None)
        self.klines['long_fbe_1'] = np.where(self.klines['trend']==2, self.klines['fb_1'] , None)
        self.klines['long_fbe_2'] = np.where(self.klines['trend']==2, self.klines['fb_2'] , None)

        self.print_orders = False
        self.graph_open_orders = True

    def get_status(self):
        status_datetime = dt.datetime.now()
        status = super().get_status()
        
        if 'trend' in self.row:
            if self.row['trend'] >= 2:
                cls = 'text-success'
                trend = 'Alza+'
            elif self.row['trend'] == 1:
                cls = 'text-success'
                trend = 'Alza'
            elif self.row['trend'] == -1:
                cls = 'text-danger'
                trend = 'Baja'
            elif self.row['trend'] <= -2:
                cls = 'text-danger'
                trend = 'Baja+'
            else: 
                cls = ''
                trend = 'Neutral'
            status['trend'] = {'l': 'Tendencia','v': trend+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 'r': self.row['trend'], 'cls': cls}

        if 'fb_0' in self.row or 'fb_1' in self.row or 'fb_2' in self.row:
            pivots = ''
            if 'fb_0' in self.row:
                pvt = self.row['fb_0']
                pivots += f'[0: {pvt}] '

            if 'fb_1' in self.row:
                pvt = self.row['fb_1']
                pivots += f'[1: {pvt}] '

            if 'fb_2' in self.row:
                pvt = self.row['fb_2']
                pivots += f'[2: {pvt}] '

            status['pivots'] = {'l': 'Pivots','v': pivots, 'r': self.row['fb_0']}

        return status    
    
    def next(self):
        signal = self.signal
        price = self.price

        self.position = False
        if 'pos___base_qty' in self.status:
            if self.status['pos___base_qty']['r'] > 0:
                self.position = True
            
        if not self.position:
            if signal == 'COMPRA':

                take_profit_price = 0
                stop_loss_price = 0
                pre_level = -1.0
                max_i = len(self.fb_levels)-1
                for i, level in enumerate(self.fb_levels):
                    if level > 0:
                        level_price = fibonacci_extension(self.row['long_fbe_0'],self.row['long_fbe_1'],self.row['long_fbe_2'],level)
                        pre_level_price = fibonacci_extension(self.row['long_fbe_0'],self.row['long_fbe_1'],self.row['long_fbe_2'],pre_level)
                        if level_price > self.price > pre_level_price:
                            if i<max_i:
                                take_profit_price = fibonacci_extension(self.row['long_fbe_0'],self.row['long_fbe_1'],self.row['long_fbe_2'],self.fb_levels[i+1])
                            else:
                                take_profit_price = level_price
                            #stop_loss_price = pre_level_price
                            stop_loss_price = fibonacci_extension(self.row['long_fbe_0'],self.row['long_fbe_1'],self.row['long_fbe_2'],level=0.0)
                    pre_level = level

                if take_profit_price>0 and stop_loss_price>0:

                    #PENDIENTE - Analisis del riesgo a tomar
                    stop_loss_price = round_down(stop_loss_price , self.qd_price)
                    self.stop_loss = round((1-(stop_loss_price/self.price))*100,2)

                    take_profit_price = round(take_profit_price , self.qd_price)
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

        if self.position and signal == 'VENTA':
            self.close(Order.FLAG_SIGNAL)
            self.cancel_orders()
            self.position = False

        mddpos = self.trail
        if 'pos___pnl_max' in self.status:
            if self.status['pos___pnl_max']['r'] > mddpos*4:
                mddpos = self.status['pos___pnl_max']['r']/4
        if 'pos___pnl' in self.status and self.status['pos___pnl_max']['r']> mddpos:
            if self.status['pos___pnl_max']['r']-self.status['pos___pnl']['r'] > mddpos:
                self.close(flag=Order.FLAG_TAKEPROFIT)
                self.cancel_orders()

    def on_order_execute(self, order):
        if order.side == Order.SIDE_SELL:
            self.cancel_orders()