import pandas as pd
import numpy as np
import datetime as dt

import scripts.functions as fn
from scripts.Bot_Core_utils import Order
    
class Bot_Core_stats:
    status = {}

    def get_status(self):

        status_datetime = dt.datetime.now()
        self.status['signal'] = {'l': 'Ultima señal',
                                 'v': self.signal+' '+status_datetime.strftime('%d-%m-%Y %H:%M'), 
                                 'r': self.signal, 
                                 }

        last_exec = dt.datetime.now()
        self.status['last_exec'] = {'l': 'Ultima ejecucion',
                                    'v': last_exec.strftime('%d-%m-%Y %H:%M'), 
                                    'r': last_exec.strftime('%d-%m-%Y %H:%M'),
                                    's': True}
        
        price = round(self.price,self.qd_price)
        self.status['price'] = {'l': 'Ultimo precio',
                                'v': f'{price}', 
                                'r': price,
                                's': True}

        wallet_base = round(self.wallet_base,self.qd_qty)
        wallet_base_in_quote = round(self.wallet_base*self.price,self.qd_quote+3)
        v = f'{wallet_base} {self.base_asset} ({wallet_base_in_quote:.2f} {self.quote_asset})'
        self.status['wallet_base'] = {'l': 'Comprado',
                                      'v': v,
                                      'r':wallet_base}
        
        wallet_quote = round(self.wallet_quote,self.qd_quote+3)
        v = f'{wallet_quote:.2f} {self.quote_asset}'
        self.status['wallet_quote'] = {'l': 'Disponible',
                                       'v': v,
                                       'r':wallet_quote}
        
        wallet_tot = round(self.wallet_quote+wallet_base_in_quote,self.qd_quote+3)

        v = f'{wallet_tot:.2f} {self.quote_asset}'
        cls = 'text-danger' if wallet_tot < self.quote_qty else 'text-success'
        self.status['wallet_tot'] = {'l': 'Capital actual',
                                     'v': v,
                                     'r':wallet_tot,
                                     's': True,
                                     'cls': cls,
                                     }

        #self.make_trades()
        pos___base_qty = 0
        pos___quote_qty = 0
        pos___orders_qty = 0
        pos___avg_price = 0
        pos___pnl = 0
        pos___pnl_max = 0

        pos_quote = 0
        pos_order_ids = []
        last_order_id = 0

        for i in self._trades:
            order = self._trades[i]
            sign = -1 if order.side == Order.SIDE_BUY else 1
            pos_quote += order.price * order.qty * sign


            if order.pos_order_id == 0:
                pos_order_ids.append(order.id)
                if order.side == Order.SIDE_BUY:
                    pos___base_qty += order.qty
                    pos___quote_qty += order.qty*order.price
                else:
                    pos___base_qty -= order.qty
                    pos___quote_qty -= order.qty*order.price
                pos___orders_qty += 1
                last_order_id = order.id
        
        if pos___base_qty*self.price <= 2:
            if len(pos_order_ids)>0:
                for oid in pos_order_ids:
                    self._trades[oid].pos_order_id = last_order_id
                    pos_order_ids = []
                    pos___avg_price = 0
            if 'pos___base_qty' in self.status:
                keys_to_reset = [key for key in self.status if key.startswith('pos__')]
                for key in keys_to_reset:
                    self.status[key] = None
        else:
            pos___avg_price = pos___quote_qty/pos___base_qty
            pos___pnl = ((self.price/pos___avg_price)-1)*100
            if 'pos___pnl_max' in self.status and isinstance(self.status['pos___pnl_max'], dict):
                pos___pnl_max = pos___pnl if pos___pnl > self.status['pos___pnl_max']['r'] else self.status['pos___pnl_max']['r']
            else:
                pos___pnl_max = pos___pnl

        pos___max_price = pos___avg_price*(1+(pos___pnl_max/100))


        pos_quote += wallet_base_in_quote
        pos_quote_sign = '' if pos_quote <= 0 else '+'
        v = f'{pos_quote_sign}{pos_quote:.2f}  {self.quote_asset}'
                
        self.status['pos___base_qty']   = {'l':'Pos. Base', 
                                           'v': round(pos___base_qty,self.qd_qty), 
                                           'r': pos___base_qty}
        self.status['pos___quote_qty']  = {'l':'Pos. Quote', 
                                           'v': f'{pos___quote_qty:.2f} {self.quote_asset}', 
                                           'r': pos___quote_qty}
        self.status['pos___orders_qty'] = {'l':'Pos. Ordenes', 
                                           'v': pos___orders_qty, 
                                           'r': pos___orders_qty}
        self.status['pos___avg_price']  = {'l':'Pos. Precio Promedio', 
                                           'v': round(pos___avg_price,self.qd_price), 
                                           'r': pos___avg_price}
        self.status['pos___pnl']        = {'l':'Pos. PNL ',     
                                           'v': f'{pos___pnl:.2f}% ({pos_quote_sign}{pos_quote:.2f} {self.quote_asset})', 
                                           'r': pos___pnl,
                                           's': True,
                                           'cls': 'text-success' if pos___pnl>=0 else 'text-danger'}
        self.status['pos___pnl_max']    = {'l':'Pos. PNL Max.', 
                                           'v': f'{pos___pnl_max:.2f} %', 
                                           'r': pos___pnl_max}
        self.status['pos___max_price']  = {'l':'Pos. Price Max.', 
                                           'v': round(pos___max_price,self.qd_price), 
                                           'r': round(pos___max_price,self.qd_price)}
        return self.status

    def get_brief(self):
        kline_ini = self.klines.loc[self.klines.index[0]]
        kline_end = self.klines.loc[self.klines.index[-1]]
        
        brief = []

        #general
        symbol = self.symbol
        intervalo = fn.get_intervals(self.interval_id,'binance') 
        last_close = float(kline_end['close'])
        usd_final =  self.wallet_quote + self.wallet_base*last_close
        resultado_usd = usd_final-self.quote_qty
        resultado_perc = (resultado_usd/self.quote_qty)*100
        dif_days = kline_end['datetime'] - kline_ini['datetime']
        dias_operando = round(dif_days.total_seconds() / 3600 / 24,1)
        resultado_mensual = (resultado_perc/dias_operando)*self.DIAS_X_MES
        dias_trades = self.df_trades['days'].sum()
        dias_sin_operar = dias_operando - dias_trades

        
        brief.append(['general', 'Par',    
                      f'{symbol} {intervalo}' ])  

        start = kline_ini['datetime'].strftime('%Y-%m-%d %H:%M')
        end = kline_end['datetime'].strftime('%Y-%m-%d %H:%M')
        brief.append(['general', 'Periodo',    
                      f'{start} - {end}' ])   
        brief.append(['general', 'Dias del periodo',    
                      f'{dias_operando:.1f}'])            
        brief.append(['general', 'Dias sin operar',    
                      f'{dias_sin_operar:.1f}'])            
        brief.append(['general', 'Resultado General',    
                      f'{resultado_perc:.2f}%' , 
                      ('text-success' if resultado_perc > 0 else 'text-danger')  ])            
        brief.append(['general', 'Resultado mensual',    
                      f'{resultado_mensual:.2f}%' ,
                      ('text-success' if resultado_perc > 0 else 'text-danger')   ])            

        #Parametros
        for prm in self.parametros:
            if prm != 'symbol':
                str_v = eval('self.'+prm)
                str_d = self.parametros[prm]['d']
                if self.parametros[prm]['t'] == 'perc':
                    str_v = f'{str_v:.2f}%'
                elif self.parametros[prm]['t'] == 'bin':
                    str_v = 'Si' if str_v > 0 else 'No'
                elif self.parametros[prm]['t'] == 't_int':
                    str_v = 'Simple' if str_v == 's' else 'Compuesto'
                else:
                    str_v = f'{str_v}'
                brief.append(['general', str_d, str_v ]) 

        #operaciones
        trades_desc = self.df_trades.describe()
        trades_tot = self.df_trades['start'].count()
        
        if trades_tot > 0:

            trades_pos = np.where(self.df_trades['result_perc'] > 0, 1, 0).sum()
            ratio_trade_pos = (trades_pos/trades_tot)*100 
            max_ganancia = trades_desc.loc['max', 'result_perc']
            max_perdida = trades_desc.loc['min', 'result_perc']
            ratio_perdida_ganancia = self.ind_ratio_ganancia_perdida(self.df_trades)
            ratio_max_perdida_ganancia = ((-max_ganancia) / max_perdida) if max_ganancia != 0 else float('inf')
            trades_x_mes = trades_tot / ( dias_operando / self.DIAS_X_MES)
            maximo_operaciones_negativas_consecutivas = self.ind_maximo_operaciones_negativas_consecutivas(self.df_trades)

            brief.append(['operaciones', 'Total de operaciones',    
                        f'{trades_tot}'])    
            brief.append(['operaciones', 'Operaciones mensuales',    
                        f'{trades_x_mes:.2f}'])    
            brief.append(['operaciones', 'Operaciones positivas',    
                        f'{trades_pos} ( {ratio_trade_pos:.2f}% )'  ])    
            brief.append(['operaciones', 'Comision Exchange',    
                        f'{Order.test_exch_comision_perc}%'  ])    
            brief.append(['operaciones', 'Maxima ganancia',    
                        f'{max_ganancia}%'])    
            brief.append(['operaciones', 'Maxima perdida',    
                        f'{max_perdida}%'])    
            brief.append(['operaciones', 'Ratio Ganancia/Perdida',    
                        f'{ratio_perdida_ganancia:.2f}' ])    
            brief.append(['operaciones', 'Ratio Mayor Ganancia/Perdida',    
                        f'{ratio_max_perdida_ganancia:.2f}'])    
            brief.append(['operaciones', 'Maximo Perdidas consecutivas',    
                        f'{maximo_operaciones_negativas_consecutivas}'])   
   
            

        #indicadores
        volatilidad_cap = self.ind_volatilidad(self.klines,'usd_strat')
        volatilidad_sym = self.ind_volatilidad(self.klines,'usd_hold')
        max_drawdown_cap = self.ind_maximo_drawdown(self.klines,'usd_strat')
        max_drawdown_sym = self.ind_maximo_drawdown(self.klines,'usd_hold')
        max_drawup_cap = self.ind_maximo_drawup(self.klines,'usd_strat')
        max_drawup_sym = self.ind_maximo_drawup(self.klines,'usd_hold')

        cagr = self.ind_cagr(self.klines)
        ratio_sharpe = self.ind_ratio_sharpe(self.klines) if cagr != 0 else 0.0
        risk_free_rate=0.045
        ratio_sortino = self.ind_ratio_sortino(self.klines, risk_free_rate)
        ratio_ulcer = self.ind_ratio_ulcer(self.klines)
        ratio_calmar = self.ind_ratio_calmar(self.klines) if cagr != 0 else 0.0
        modificacion_sharpe = self.ind_indice_modificacion_sharpe(self.klines) if volatilidad_cap > 0 else 0.0
        
        umbral_objetivo_riesgo = 0.02  # Umbral objetivo de riesgo: 2%
        ratio_sortino_modificado = self.ind_ratio_sortino_modificado(self.df_trades,umbral_objetivo_riesgo) if trades_tot > 0 else 0.0


        brief.append(['indicadores', 'CAGR',    
                    f'{cagr:.2f}%'])          
        brief.append(['indicadores', 'Maximo DrawDown Capital',    
                    f'{max_drawdown_cap:.2f}%'])          
        brief.append(['indicadores', 'Maximo DrawDown Par',    
                    f'{max_drawdown_sym:.2f}%'])   
        brief.append(['indicadores', 'Maximo DrawUp Capital',    
                    f'{max_drawup_cap:.2f}%'])          
        brief.append(['indicadores', 'Maximo DrawUp Par',    
                    f'{max_drawup_sym:.2f}%'])   
        brief.append(['indicadores', 'Volatilidad del capital',    
                    f'{volatilidad_cap:.2f}%'])          
        brief.append(['indicadores', 'Volatilidad del par',    
                    f'{volatilidad_sym:.2f}%'])         
        """ 
        brief.append(['indicadores', 'Ratio Sharpe',    
                    f'{ratio_sharpe:.2f}'])          
        brief.append(['indicadores', f'Ratio Sortino ({risk_free_rate})',    
                    f'{ratio_sortino:.2f}'])          
        brief.append(['indicadores', 'Ratio Ulcer',    
                    f'{ratio_ulcer:.2f}'])          
        brief.append(['indicadores', 'Ratio Calmar',    
                    f'{ratio_calmar:.2f}'])          
        brief.append(['indicadores', 'Indice de Modificacion de Sharpe',    
                    f'{modificacion_sharpe:.2f}'])          
        brief.append(['indicadores', f'Ratio Sortino Modificado ({umbral_objetivo_riesgo})',    
                    f'{ratio_sortino_modificado:.2f}'])          
        """
        return brief

    def get_resultados(self):

        kline_ini = self.klines.loc[self.klines.index[0]]
        kline_end = self.klines.loc[self.klines.index[-1]]

        df_trades = self.df_trades
        df_data = self.klines

        dif_days = kline_end['datetime'] - kline_ini['datetime']
        dias_operando = round(dif_days.total_seconds() / 3600 / 24,1)
        dias_trades = df_trades['days'].sum()
        dias_sin_operar = dias_operando - dias_trades
        ratio_dias_sin_operar = (dias_sin_operar/dias_operando)*100 if dias_operando > 0 else 0.0

        trades_desc = df_trades.describe()
        trades_tot = df_trades['start'].count()

        trades_pos = np.where(df_trades['result_perc'] > 0, 1, 0).sum()
        ratio_trade_pos = (trades_pos/trades_tot)*100 if trades_tot > 0 else 0.0
        max_ganancia = trades_desc.loc['max', 'result_perc'] if trades_pos > 0 else 0.0
        max_perdida = trades_desc.loc['min', 'result_perc'] if trades_pos > 0 else 0.0
        ratio_perdida_ganancia = self.ind_ratio_ganancia_perdida(df_trades) if trades_pos > 0 else 0.0
        ratio_max_perdida_ganancia = ((-max_ganancia) / max_perdida) if max_perdida != 0 else 0.0
        trades_x_mes = trades_tot / ( dias_operando / self.DIAS_X_MES) if dias_operando != 0 else 0.0
        maximo_operaciones_negativas_consecutivas = self.ind_maximo_operaciones_negativas_consecutivas(df_trades)

        volatilidad_cap = self.ind_volatilidad(df_data,'usd_strat')
        volatilidad_sym = self.ind_volatilidad(df_data,'usd_hold')
        ratio_volatilidad = (volatilidad_cap/volatilidad_sym)*100 if volatilidad_sym != 0 else 0.0
        max_drawdown_cap = self.ind_maximo_drawdown(df_data,'usd_strat')
        max_drawdown_sym = self.ind_maximo_drawdown(df_data,'usd_hold')
        ratio_max_drawdown = (max_drawdown_cap/max_drawdown_sym)*100 if max_drawdown_sym != 0 else 0.0
        max_drawup_cap = self.ind_maximo_drawup(df_data,'usd_strat')
        max_drawup_sym = self.ind_maximo_drawup(df_data,'usd_hold')
        ratio_max_drawup = (max_drawup_cap/max_drawup_sym)*100  if max_drawup_sym != 0 else 0.0
        cagr = self.ind_cagr(df_data)
        ratio_calmar = self.ind_ratio_calmar(df_data) if trades_pos > 0 else 0.0
        modificacion_sharpe = self.ind_indice_modificacion_sharpe(df_data) if trades_pos > 0 else 0.0
        
        resultados = []
        resultados.append({'ind':'cagr',self.symbol: cagr })          
        resultados.append({'ind':'max_drawdown_cap',self.symbol: max_drawdown_cap })
        resultados.append({'ind':'maximo_operaciones_negativas_consecutivas',self.symbol: maximo_operaciones_negativas_consecutivas })   
        resultados.append({'ind':'ratio_dias_sin_operar',self.symbol: ratio_dias_sin_operar })  
        resultados.append({'ind':'trades_x_mes',self.symbol: trades_x_mes})  
        resultados.append({'ind':'ratio_trade_pos',self.symbol: ratio_trade_pos  })    
        resultados.append({'ind':'ratio_perdida_ganancia',self.symbol: ratio_perdida_ganancia })    
        resultados.append({'ind':'ratio_max_perdida_ganancia',self.symbol: ratio_max_perdida_ganancia })    
        resultados.append({'ind':'ratio_volatilidad',self.symbol: ratio_volatilidad})          
        resultados.append({'ind':'ratio_max_drawdown',self.symbol: ratio_max_drawdown })
        resultados.append({'ind':'ratio_max_drawup',self.symbol: ratio_max_drawup })
        #resultados.append({'ind':'ratio_calmar',self.symbol: ratio_calmar })          
        #resultados.append({'ind':'modificacion_sharpe',self.symbol: modificacion_sharpe })

        return resultados
        
    def ind_ratio_ganancia_perdida(self,df_trades):
        # Esta función calcula el ratio de ganancias y pérdidas de las operaciones.
        ganancias = df_trades[df_trades['result_perc'] > 0]['result_perc']
        perdidas = df_trades[df_trades['result_perc'] < 0]['result_perc']
        promedio_ganancias = ganancias.mean() if len(ganancias) > 0 else 0
        promedio_perdidas = perdidas.mean() if len(perdidas) > 0 else 0
        ratio_ganancia_perdida = promedio_ganancias / abs(promedio_perdidas) if promedio_perdidas != 0 else 0
        return round(ratio_ganancia_perdida,2)
    
    def ind_maximo_operaciones_negativas_consecutivas(self, df_trades):
        max_consecutivas = 0
        consecutivas = 0
        for resultado in df_trades['result_perc']:
            if resultado < 0:
                consecutivas += 1
                if consecutivas > max_consecutivas:
                    max_consecutivas = consecutivas
            else:
                consecutivas = 0
        return max_consecutivas
    
    def ind_maximo_drawdown(self, df_data, key):
        # Esta función calcula el máximo drawdown del capital acumulado.
        data = df_data[key]
        roll_max = data.cummax()
        drawdown = ((data / roll_max) - 1.0 ) * (-100)
        return round(drawdown.max(),2)

    def ind_maximo_drawup(self, df_data, key):
        # Esta función calcula el máximo drawup del capital acumulado.
        data = df_data[key]
        roll_min = data.cummin()
        drawup = ((data / roll_min) - 1.0 ) * 100
        return round(drawup.max(),2)

    def ind_volatilidad(self, df_data,key):
        # Volatilidad anualizada 
        return df_data[key].pct_change().std() * np.sqrt(360)*100

    def ind_ratio_sharpe(self, df_data, risk_free_rate=0.045):
        returns = df_data['usd_strat'].pct_change()
        sharpe_ratio = (self.ind_cagr(df_data) - risk_free_rate) / self.ind_volatilidad(df_data,'usd_strat')
        return sharpe_ratio
    
    def ind_cagr(self, df_data):
        # CAGR (Compound Annual Growth Rate).
        kline_ini = self.klines.loc[self.klines.index[0]]
        kline_end = self.klines.loc[self.klines.index[-1]]

        dif_days = kline_end['datetime'] - kline_ini['datetime']
        dias_operando = round(dif_days.total_seconds() / 3600 / 24,1)
        years = dias_operando / 365
       
        data = df_data['usd_strat']
        return ((data.iloc[-1] / data.iloc[0]) ** (1 / years) - 1)*100
    
    def ind_ratio_sortino(self, df_data, risk_free_rate):
        df_data['retorno_diario'] = df_data['usd_strat'].pct_change()
        negative_returns = df_data[df_data['retorno_diario'] < 0]['retorno_diario'].std() * np.sqrt(360)
        sortino_ratio = (self.ind_cagr(df_data) - risk_free_rate) / negative_returns
        return sortino_ratio
    
    def ind_drawdowns(self, df_data):
    # Esta función calcula los drawdowns a partir de los datos del capital acumulado.
        data = df_data['usd_strat']
        roll_max = data.cummax()
        drawdowns = data - roll_max
        return drawdowns

    def ind_ratio_ulcer(self, df_data):
        # Esta función calcula el Ratio de Ulcer.
        drawdowns = self.ind_drawdowns(df_data)
        ulcer_index = np.sqrt(np.mean(drawdowns ** 2))
        return ulcer_index

    def ind_indice_modificacion_sharpe(self, df_data, risk_free_rate=4.5):
        # Esta función calcula el Índice de Modificación de Sharpe.

        """
        me parece que risk_free_rate deberia ser 4.5 en lugar de 0.045
        el CAGR esta expresado en porcentaje y el risk_free_rate en 1/100
        """

        cagr = self.ind_cagr(df_data)
        volatilidad = self.ind_volatilidad(df_data,'usd_strat')
        max_drawdown = self.ind_maximo_drawdown(df_data,'usd_strat')
        sharpe_ratio = self.ind_ratio_sharpe(df_data, risk_free_rate=risk_free_rate)
        indice_modificacion_sharpe = (cagr - risk_free_rate) / (volatilidad * abs(max_drawdown) * sharpe_ratio)

        return indice_modificacion_sharpe
    
    def ind_ratio_calmar(self, df_data):
        # Esta función calcula el Ratio de Calmar.
        cagr = self.ind_cagr(df_data)
        max_drawdown = self.ind_maximo_drawdown(df_data,'usd_strat')
        ratio_calmar = cagr / abs(max_drawdown)
        return ratio_calmar
    
    def ind_ratio_sortino_modificado(self, df_trades, umbral_objetivo_riesgo):
        # Esta función calcula el Ratio de Sortino Modificado.
        retorno_total = df_trades['result_usd'].sum()
        df_trades['retorno_diario'] = df_trades['result_usd'] / self.quote_qty
        df_trades['retorno_negativo'] = df_trades['retorno_diario'].apply(lambda x: x if x < 0 else 0)
        desviacion_negativa = df_trades['retorno_negativo'].std()
        if desviacion_negativa!=0:
            ratio_sortino_modificado = (retorno_total - umbral_objetivo_riesgo) / desviacion_negativa
            return ratio_sortino_modificado
        return 0.0
