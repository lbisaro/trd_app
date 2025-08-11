import pandas as pd
import numpy as np
import datetime as dt
import pickle

from scripts.Bot_Core_utils import *
from scripts.Exchange import Exchange
import scripts.functions as fn

class Bot_Core_backtest:
    
    def backtest(self,klines_1m,from_date,rsp_mode):
        print('Iniciando Backtest')
        
        klines = self.resample_klines(klines_1m,self.interval_id)
        sub_klines = self.resample_sub_klines(klines_1m,self.interval_id)

        self.backtesting = True
        self.order_id = 0
        self.graph_open_orders = True
        self.graph_signals = True

        self.open_orders_data = {}
        
        #Trades y Orders para gestion de resultados
        self._orders = {}
        self._trades = {}
        self.executed_order = False
                
        exch = Exchange(type='info',exchange='bnc',prms=None)
        symbol_info = exch.get_symbol_info(self.symbol)
        self.base_asset = symbol_info['base_asset']
        self.quote_asset = symbol_info['quote_asset']
        self.qd_price = symbol_info['qty_decs_price']
        self.qd_qty = symbol_info['qty_decs_qty']
        self.qd_quote = symbol_info['qty_decs_quote']

        self.wallet_base = 0.0
        self.wallet_quote = self.quote_qty

        self.klines = klines
        self.sub_klines = sub_klines

        #Aplicar la señal de compra/venta
        self.start()

        #quitando las velas previas a la fecha de start
        self.klines = self.klines[self.klines['datetime'] >= pd.to_datetime(from_date)]
        self.klines = self.klines.reset_index(drop=True)

        #Calculando el timeframe de las velas
        self.timeframe_length = self.klines['datetime'].values[1] - self.klines['datetime'].values[0]

        #Limitando el backtest a un maximo de velas para periodos inferiores a 15 minutos (1 hora / 4)
        if int(self.timeframe_length) <= 3600000000000/4:  
            self.klines = self.klines[-40000:]
        print('Total de registros a analizar:',len(self.klines))
        #Carga la vela anterior al inicio del ciclo
        #self.row = self.klines[self.klines['datetime'] == pd.to_datetime(from_date)-self.timeframe_length ].iloc[0]
        first_datetime = self.klines['datetime'].min()
        last_datetime  = self.klines['datetime'].max()
        self.row = self.klines[self.klines['datetime'] == first_datetime].to_dict(orient='records')[0]
        
        #Limitando el contenido de las sub_klines
        self.sub_klines = self.sub_klines[self.sub_klines['datetime'] >= first_datetime]
        self.sub_klines = self.sub_klines[self.sub_klines['datetime'] <= last_datetime]
        self.sub_klines = self.sub_klines.set_index('datetime')

        velas = int(self.klines['datetime'].count())
        if velas<50:
            res = {
                'OK': False,
                'error': 'El intervalo y rango de fechas solicitado genera un total de '+str(velas)+' velas'+\
                    '<br>Se requiere un minimo de '+str(self.VELAS_PREVIAS)+' velas para poder realizar el Backtesting',
                }
            return res
        
        
        #Se ejecuta la funcion next para cada registro del dataframe
        proc_start = dt.datetime.now()
        self.klines['usd_strat'] = self.klines.apply(self._next, axis=1)

        #Calculando HOLD para comparar contra la operacion
        # El hold es la compra del capital a invertir al precio open al inicio + el saldo que queda en USD
        price_to_hold = self.klines['open'].values[0]
        quote_to_hold = round( self.quote_qty, self.qd_quote )
        qty_to_hold = round( ( quote_to_hold / price_to_hold ) , self.qd_qty ) 
        self.klines['usd_hold'] = round( self.klines['open'] * qty_to_hold , self.qd_quote )
        
        #Procesando eventos de Señanes de compra/venta y ordenes
        ohlc = self.klines[['datetime','close','usd_strat']].values.tolist()
        
        self.make_trades()
        if rsp_mode=='ind':
            return self.get_resultados()
        
        elif rsp_mode=='complete':

            res = {'ok': True,
                'error': False,
                'order_side': { 
                        Order.SIDE_BUY:'BUY',
                        Order.SIDE_SELL:'SELL',
                        },
                'order_flag': { 
                        Order.FLAG_SIGNAL:'SIGNAL',
                        Order.FLAG_STOPLOSS:'STOP-LOSS',
                        Order.FLAG_TAKEPROFIT:'TAKE-PROFIT',
                        },
                'order_type': { 
                        Order.TYPE_MARKET:'',
                        Order.TYPE_LIMIT:'LIMIT',
                        },
                'qd_price': self.qd_price, 
                'qd_qty': self.qd_qty, 
                'qd_quote': self.qd_quote, 
                'data': [], 
                'signals': [], 
                'trade_orders': [],
                'orders_hst': [],
                'trades': [], 
                }
            
            #Trades (Lista de trades y ordersData)
            for i,trade in self.df_trades.iterrows():
                
                trd = [
                    trade['start'].strftime('%d/%m/%Y %H:%M'),
                    trade['buy_price'],
                    trade['qty'],
                    trade['end'].strftime('%d/%m/%Y %H:%M'),
                    trade['sell_price'],
                    trade['flag'],
                    trade['days'],
                    trade['result_usd'],
                    trade['result_perc'],
                    trade['type'],
                    trade['orders'],
                    ]
                res['trades'].append(trd)
           
            signals = []
            if self.graph_signals:
                df_signals = self.klines[(self.klines['signal']=='COMPRA')|(self.klines['signal']=='VENTA')]
                df_signals['side'] = np.where(df_signals['signal']=='COMPRA',0,1)
                df_signals['value'] = np.where(df_signals['side']==0,df_signals['low'],df_signals['high'])
                signals = df_signals[['datetime','value','side']].values.tolist()
            
            trade_orders = []
            df_trade_orders = pd.DataFrame(columns=["datetime", "value", "side"])
            for order_id in self._trades:
                order = self._trades[order_id]
                df_trade_orders.loc[len(df_trade_orders)] = [order.datetime,order.price,order.side]
                trade_orders = df_trade_orders.values.tolist()

            orders_hst = []
            if self.graph_open_orders:
                orders_hst = self.open_orders_data     
            
            res['data'] = ohlc
            res['signals'] = signals
            res['orders_hst'] = orders_hst
            res['trade_orders'] = trade_orders
            
            res['brief'] = self.get_brief()

            #Unificando operaciones con data de klines
            self.klines['datetime'] = pd.to_datetime(self.klines['datetime'])
            self.df_trades['start'] = pd.to_datetime(self.df_trades['start'])
            df_full = pd.merge(self.klines, self.df_trades, left_on='datetime', right_on='start', how='left')

            file_dump = f'backtest/results/bt_bot_{self.__class__.__name__}_{self.interval_id}.DataFrame'
            with open(file_dump, 'wb') as f:
                pickle.dump(df_full, f)

            proc_end = dt.datetime.now()
            proc_diff = proc_end-proc_start
            print('Completo',f"El proceso demoro {proc_diff.total_seconds():.4f} segundos.")
            return res
    
    def _next(self,row):
        #El primer self.row fue precargado con la vela anterior al inicio del ciclo
        self.signal = self.row['signal']
        self.price = self.row['close']
        self.datetime = self.row['datetime']+self.timeframe_length   

        self.next()

        #Gestion de stoploss y takeprofit price
        if self.graph_open_orders:
            for i in self._orders: #Ordenes abiertas
                order = self._orders[i]
                if ( order.type == Order.TYPE_LIMIT ) :
                    if i not in self.open_orders_data:
                        self.open_orders_data[i] = []
                    self.open_orders_data[i].append([self.datetime,
                                                     order.limit_price,
                                                     order.side,
                                                    ])
        self.executed_order = self.backtest_check_orders()

        if row.name == self.klines.iloc[-1].name: #Se esta ejecutando la ultima vela
            if self.wallet_base > 0:
                self.close(Order.FLAG_SIGNAL)
            self.cancel_orders()

        usd_strat = round( self.price * self.wallet_base + self.wallet_quote, self.qd_quote )
        
        self.row = row
        self.get_status()
        return usd_strat

    def backtest_check_orders(self):
        
        executed = False
        start_d = self.datetime #+ self.timeframe_length
        end_d = self.datetime + self.timeframe_length #* 2

        
        if len(self._orders) > 0:
            _orders = self._orders.copy().items()

            self.wallet_base_block = 0.0
            self.wallet_quote_block = 0.0

            #Recorre las sub_velas correspondientes a la vela actual
            #para optimizar la ejecucion de las ordenes
            sub_k = self.sub_klines[(self.sub_klines.index>=start_d) & (self.sub_klines.index<end_d)] 
            for sub_i,sub_row in sub_k.iterrows():
                self.datetime = sub_row.name
                for i,order in _orders:
                    
                    if i in self._orders: #Se consulta si esta o no porque puede que se ejecute mas de una orden en la misma vela
                        order  = self._orders[i]
                        if order.type == Order.TYPE_LIMIT:
                            if order.side == Order.SIDE_BUY and order.flag == Order.FLAG_TAKEPROFIT:
                                if sub_row['low'] <= order.limit_price:
                                    if order.limit_price > sub_row['high']:
                                        self._orders[order.id].limit_price = sub_row['open']
                                    executed =  self.execute_order(order.id)
                                    
                            if order.side == Order.SIDE_BUY and order.flag == Order.FLAG_STOPLOSS:
                                if sub_row['high'] >= order.limit_price:
                                    if order.limit_price < sub_row['low']:
                                        self._orders[order.id].limit_price = sub_row['open']
                                    executed =  self.execute_order(order.id)
                                    
                            if order.side == Order.SIDE_SELL and order.flag == Order.FLAG_TAKEPROFIT:
                                if sub_row['high'] >= order.limit_price:
                                    if order.limit_price < sub_row['low']:
                                        #print('Change Limit Price',order.limit_price,' -> ',sub_row['open'],' [',self.datetime,' ',self.row['high'],'-',self.row['low'],'] - [',sub_i,' ',sub_row['high'],'-',sub_row['low'],']')
                                        self._orders[order.id].limit_price = sub_row['open']
                                    executed = self.execute_order(order.id)

                            if order.side == Order.SIDE_SELL and order.flag == Order.FLAG_STOPLOSS:
                                if sub_row['low'] <= order.limit_price:
                                    if order.limit_price > sub_row['high']:
                                        #print('Change Limit Price',order.limit_price,' -> ',sub_row['open'],' [',self.datetime,' ',self.row['high'],'-',self.row['low'],'] - [',sub_i,' ',sub_row['high'],'-',sub_row['low'],']')
                                        self._orders[order.id].limit_price = sub_row['open']
                                    executed = self.execute_order(order.id)
                                    
                        #Establece la cantidad de Base y Quote bloqueadas en ordenes
                        if i in self._orders: #La orden no fue ejecutada
                            if order.side == Order.SIDE_BUY:
                                self.wallet_quote_block += round(order.qty*order.limit_price,self.qd_quote)
                            if order.side == Order.SIDE_SELL:
                                self.wallet_base_block += round(order.qty,self.qd_qty)

        return executed
        
    def backtest_execute_order(self,orderid):
        if not( orderid in self._orders):
            return False

        order = self._orders[orderid]
        order.price = order.limit_price
        order.datetime = self.datetime  
        
        if self.print_orders:
            if order.side == Order.SIDE_SELL:
                print(f'\033[31m{order}\033[0m',end=' -> ')
            else:
                print(f'\033[32m{order}\033[0m',end=' -> ')

        execute = False
        if order.side == Order.SIDE_BUY:
            quote_to_sell = round(order.qty*order.price,self.qd_quote)
            comision = round(quote_to_sell*(Order.test_exch_comision_perc/100),4)
            new_wallet_base = round(self.wallet_base + order.qty,self.qd_qty)
            new_wallet_quote = round(self.wallet_quote - quote_to_sell ,self.qd_quote)
            if new_wallet_base >= 0 and new_wallet_quote >= 0:
                self.wallet_base = new_wallet_base 
                self.wallet_quote = round(new_wallet_quote - comision,self.qd_quote)
                execute = True

        elif order.side == Order.SIDE_SELL:
            quote_to_buy = round(order.qty*order.price,self.qd_quote)
            comision = round(quote_to_buy*(Order.test_exch_comision_perc/100),4)
            new_wallet_base = round(self.wallet_base - order.qty,self.qd_qty)
            new_wallet_quote = round(self.wallet_quote + quote_to_buy,self.qd_quote)
            if new_wallet_base >= 0 and new_wallet_quote >= 0:
                self.wallet_base = new_wallet_base
                
                #Cuando se ejecuta una venta, ajusta el saldo para evitar errores de decimales
                if self.wallet_base*self.price < 2:
                    self.wallet_base = 0
                self.wallet_quote = round(new_wallet_quote - comision,self.qd_quote)
                execute = True

        del self._orders[orderid] 
        if execute:
            
            self._trades[order.id] = order
            if self.print_orders:
                print(f' {self.wallet_base} {self.wallet_quote} \033[32mOK\033[0m')
            self.on_order_execute(order)

        else:
            if self.print_orders:
                print(f' {self.wallet_base} {self.wallet_quote} \033[31mCANCELED\033[0m')
        
        
        return execute

    def make_trades(self):
        trade = {}
        self.df_trades = pd.DataFrame(columns=self.df_trades_columns)
        for i in self._trades:
            order = self._trades[i]
            order.comision = round((order.price*order.qty)*(Order.test_exch_comision_perc/100),4)
            self._trades[i].comision = order.comision
            
            if trade == {}: # Open Trade
                trade['start'] = order.datetime
                trade['flag'] = order.flag
                trade['type'] = order.type
                trade['comision'] = order.comision
                trade['orders']  = 1
                if order.side == Order.SIDE_BUY:
                    trade['buy_qty'] = order.qty
                    trade['buy_quote'] = round(order.qty*order.price,self.qd_quote)
                    trade['sell_qty'] = 0.0
                    trade['sell_quote'] = 0.0
                elif order.side == Order.SIDE_SELL:
                    trade['buy_qty'] = 0.0
                    trade['buy_quote'] = 0.0
                    trade['sell_qty'] = order.qty
                    trade['sell_quote'] = round(order.qty*order.price,self.qd_quote)
                trade['price_start'] = order.price

            else:
                trade['orders'] += 1
                trade['end'] = order.datetime
                trade['flag'] = order.flag
                trade['type'] = order.type
                trade['comision'] = trade['comision']+order.comision
                if order.side == Order.SIDE_BUY:
                    trade['buy_qty'] = trade['buy_qty']+order.qty
                    trade['buy_quote'] = trade['buy_quote']+round(order.qty*order.price,self.qd_quote)
                elif order.side == Order.SIDE_SELL:
                    trade['sell_qty'] = trade['sell_qty']+order.qty
                    trade['sell_quote'] = trade['sell_quote']+round(order.qty*order.price,self.qd_quote)            
            
            saldo_qty = round(trade['buy_qty'] - trade['sell_qty'],self.qd_qty) 
            saldo_quote  = round(trade['buy_quote'] - trade['sell_quote'],self.qd_quote)
            
            #Cuando se ejecuta una venta, ajusta el saldo para evitar errores de decimales
            if order.side == Order.SIDE_SELL:
                if -2 < saldo_qty * order.price < 2:
                    saldo_qty = 0.0
                if -2 < saldo_quote < 2:
                    saldo_quote = 0.0

            if ( (saldo_qty== 0) or (saldo_quote == 0) ) and (trade['buy_qty']) and (trade['sell_qty']):
                start = trade['start']
                buy_price = round(trade['buy_quote']/trade['buy_qty'],self.qd_price)
                qty = trade['buy_qty']
                end = trade['end']
                sell_price = round(trade['sell_quote']/trade['sell_qty'],self.qd_price)
                flag = trade['flag']
                type = trade['type']
                orders = trade['orders']
                dif = trade['end'].to_pydatetime() - trade['start'].to_pydatetime()
                days = dif.total_seconds() / 60 / 60 / 24
                result_usd = trade['sell_quote'] - trade['buy_quote'] - trade['comision']
                result_perc = round((((sell_price/buy_price)-1)*100) - ((Order.test_exch_comision_perc) * 2) , 2)
                trade = pd.DataFrame([[start,buy_price,qty,end,sell_price,flag,type,days,result_usd,result_perc,orders]], columns=self.df_trades_columns) 
                self.df_trades = pd.concat([self.df_trades, trade], ignore_index=True) 
                trade = {}

    def resample_klines(self,klines,interval_id):
        resample_minutes = fn.get_intervals(interval_id,'minutes')
        rsmpl_klines = self.resample_df(klines,resample_minutes)
        return rsmpl_klines

    def resample_sub_klines(self,klines,interval_id):
        resample_minutes = fn.get_intervals(interval_id,'sub_klines_minutes')
        rsmpl_klines = self.resample_df(klines,resample_minutes)
        return rsmpl_klines



    def resample_df(self,df,periods):
        """
        Genera un dataframe resampleado de acuerdo a la cantidad de periodos establecidos
        Ej.: Si df es tiene un timeframe de 15m, y periods = 4, el resample se hace en 1h

        Ejemplo de uso de resample y join_after_resample:

        dfx4 = resample(df,4)
        rsi_x4 = ta.rsi(dfx4['close'], length=21)
        df = join_after_resample(df,rsi_x4,'rsi')
        df['rsi_sma'] = df['rsi'].rolling(14).mean()

        """

        timeframe = df['datetime'].iloc[1]-df['datetime'].iloc[0]
        resample = timeframe * periods

        # Resamplear el dataframe
        dfx = df.resample(resample, on="datetime").agg({
            'datetime': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        dfx.reset_index(inplace=True,drop=True)
        return dfx