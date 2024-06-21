from bot.model_kline import *
import numpy as np
from ..Bot_CoreLong import Bot_CoreLong

import pandas_ta as ta
from scripts.indicators import resample, join_after_resample, ITG_Scalper

class BotStrat_01(Bot_CoreLong):

    descripcion = 'Bot Core v2 \n'\
                  'Ejecuta la compra al recibir una señal de Compra, '\
                  'y cierra la operación por Stop Loss o Take Profit (Si se definen con un % mayor a cero) '\
                  'o cuando recibe una señal de Venta.'
    
    
    def start(self):
        self.klines = ITG_Scalper(self.klines)
               
        df = self.klines.copy()
        klines_x4 = resample(df,4)
        rsi_x4 = ta.rsi(klines_x4['close'], length=21)
        self.klines = join_after_resample(self.klines,rsi_x4,'rsi')
        self.klines['rsi_sma'] = self.klines['rsi'].rolling(14).mean()
        self.klines['rsi_long_ok'] = np.where((self.klines['rsi']>self.klines['rsi_sma'])&(self.klines['rsi'].shift(6)<self.klines['rsi_sma'].shift(6)),self.klines['rsi'],None)   
        self.klines['rsi_short_ok'] = np.where((self.klines['rsi']<self.klines['rsi_sma'])&(self.klines['rsi'].shift(6)>self.klines['rsi_sma'].shift(6)),self.klines['rsi'],None)   

        self.klines['signal'] = np.where((self.klines['long']>0)&(self.klines['rsi_long_ok']>0),'COMPRA','NEUTRO')
        self.klines['signal'] = np.where((self.klines['short']>0)&(self.klines['rsi_short_ok']>0),'VENTA',self.klines['signal'])
