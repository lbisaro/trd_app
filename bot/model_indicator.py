from django.conf import settings
from django.db import models, connection
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

import pandas as pd
import numpy as np
import datetime as dt

import scripts.functions as fn
from scripts.Exchange import Exchange
from bot.model_kline import Symbol
from scripts.indicators import supertrend,volume_level,volatility_level

class Indicator(models.Model):
    """
    INDICADOR DE TENDENCIA
        La tendencia se mide con 2 supertrends (Slow -> 7,3) y (Fast -> 7,2)
        Slow    Fast    Trend   Referencia sobre la tendencia
        -1      -1      -2      Bajista +
        -1      +1      -1      Bajista
        +1      -1      +1      Alcista 
        +1      +1      +2      Alcista +

        En resumen el indicador de tendencia resulta entre +2 y -2, 
        los valores positivos representan una tendencia alcista y los negativos una tendencia bajista,
        Los valores de +2 y -2 representan una tendencia firme
        Los valores de +1 y -1 representan que la tendencia esta en un posible cambio
    
    INDICADOR DE VOLUMEN


    INDICADOR DE VOLATILLIDAD



    """

    intervals = ['1h01','1h04','2d01','2d03']
    max_periods = 100

    INDICATOR_ID_TREND = 1
    INDICATOR_ID_VOLUME = 2
    INDICATOR_ID_VOLATILITY = 3

    symbol = models.ForeignKey(Symbol, on_delete = models.CASCADE)
    interval_id = models.CharField(max_length = 4, null=False, blank=False)
    datetime = models.DateTimeField(default=timezone.now)
    indicator_id = models.IntegerField(null=False, blank=False)  
    value = models.IntegerField(null=False, blank=False)
    last = models.BooleanField(null=False, blank=False)
    change = models.IntegerField(null=False, blank=False, default = 0)  
    
    class Meta:
        verbose_name = "Main Indicator"
        verbose_name_plural='Main Indicators'
    
    def __str__(self):
        intervalo = fn.get_intervals(self.interval_id,'binance')
        return f'{self.datetime} {self.symbol} {intervalo} {self.indicator_str(self.indicator_id)}' 
    
    def indicator_str(self,indicator_id):
        if indicator_id == self.INDICATOR_ID_TREND:
            return 'Tendencia'
        elif indicator_id == self.INDICATOR_ID_VOLUME:
            return 'Volumen'
        elif indicator_id == self.INDICATOR_ID_VOLATILITY:
            return 'Volatilidad'
        else:
            return ''

    def update(self):
        startDt = dt.datetime.now()
        #hr = startDt.strftime('%H')
        mn = startDt.strftime('%M')
        print('mn: ',mn)
        if mn[1]=='0': #Solo entra en los minutos multiplo de 10 / Representa que se ejecuta cada 10 minutos

            limit = self.max_periods
            exch = Exchange(type='info',exchange='bnc',prms=None)
            symbols  = Symbol.objects.filter(activo=1).order_by('symbol')
            
            for symb in symbols:
                symbol = symb.symbol

                for interval_id in self.intervals:
                    if interval_id <= '1h04' or mn == '00': # (Intervalos de 1 o 4 horas) o (Cada 1 hora)
                        df = exch.get_klines(symbol=symbol,interval_id=interval_id,limit=limit)

                        #Calculo de Tendencia
                        df = supertrend(df,length=7,multiplier=3)
                        df.rename(columns={'st_trend': 'st_trend_s'},inplace=True)
                        df = supertrend(df,length=7,multiplier=2)
                        df.rename(columns={'st_trend': 'st_trend_f'},inplace=True)
                        df['trend'] = np.where((df['st_trend_s']>0) & (df['st_trend_f']>0),2,0)
                        df['trend'] = np.where((df['st_trend_s']>0) & (df['st_trend_f']<0),1,df['trend'])
                        df['trend'] = np.where((df['st_trend_s']<0) & (df['st_trend_f']>0),-1,df['trend'])
                        df['trend'] = np.where((df['st_trend_s']<0) & (df['st_trend_f']<0),-2,df['trend'])
                        df.drop(columns=[col for col in df.columns if col.startswith('st_')],inplace=True)
                        
                        #Calculo de Volumen
                        df = volume_level(df)

                        #Calculo de la Volatilidad
                        df = volatility_level(df)


                        last = df.iloc[-1]
                        self.add(symb,interval_id,self.INDICATOR_ID_TREND,last['trend'])
                        self.add(symb,interval_id,self.INDICATOR_ID_VOLUME,last['vol_range'])
                        self.add(symb,interval_id,self.INDICATOR_ID_VOLATILITY,last['vlt_range'])


    def add(self,symbol,interval_id,indicator_id,value):
        try:
            exists = Indicator.objects.get(symbol=symbol, interval_id=interval_id, indicator_id=indicator_id, last=True)
            if exists.value != value:
                exists.last = False
                exists.save()

                change = 1 if value > exists.value else -1
                
                new_ind = Indicator(
                            symbol=symbol, 
                            interval_id = interval_id,
                            indicator_id = indicator_id,
                            value = value,
                            change = change,
                            last = True,
                            )
                new_ind.save()

        except Indicator.DoesNotExist:
            new_ind = Indicator(
                        symbol=symbol, 
                        interval_id = interval_id,
                        indicator_id = indicator_id,
                        value = value,
                        change = 0,
                        last = True,
                        )
            new_ind.save()

            
            