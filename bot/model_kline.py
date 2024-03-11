from django.conf import settings
from django.db import models
from django.db.models import Max
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import F, Min, Max, Avg, Sum
from django.db.models.functions import TruncDay, TruncHour, TruncMinute
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import scripts.functions as fn
import warnings
import pytz


class Symbol(models.Model):
    symbol = models.CharField(max_length = 16, unique = True, null=False, blank=False,verbose_name='Nombre del par')
    base_asset = models.CharField(max_length = 8, null=False, blank=False)
    quote_asset = models.CharField(max_length = 8, null=False, blank=False)
    qty_decs_qty = models.IntegerField(null=False, blank=False)
    qty_decs_price = models.IntegerField(null=False, blank=False)
    qty_decs_quote = models.IntegerField(null=False, blank=False)
    activo = models.IntegerField(default=0)  
    
    def __str__(self):
        return self.symbol
    
    class Meta:
        verbose_name = "Par"
        verbose_name_plural='Pares'
        
    
    def activate(self):
        self.activo = 1
        self.save()

class Kline(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete = models.CASCADE)
    datetime = models.DateTimeField(null=False, blank=False, db_index=True)
    open = models.FloatField(null=False, blank=False)
    close = models.FloatField(null=False, blank=False)
    high = models.FloatField(null=False, blank=False)
    low = models.FloatField(null=False, blank=False)
    volume = models.FloatField(null=False, blank=False)
    
    def __str__(self):
        return f'{self.datetime} {self.close} {self.volume}'
    
    class Meta:
        verbose_name_plural='Velas'
        # Definir que la combinación de 'symbol' y 'datetime' es única
        unique_together = ('symbol', 'datetime')

    def get_df(strSymbol,interval_id,**kwargs):
        """
        Obtener velas desde la base de datos
        El alcance de las velas se especifica con el parametro limit, o en su defecto los parametros from_date y to_date

        Args:
            limit (int): Cantidad de velas anteriores a la fecha y hora actuales.
            from_date ('%Y-%m-%d'): Fecha de inicio del alcance.
            to_date ('%Y-%m-%d'): Fecha de fin del alacnce

        Returns:
            klines (DataFrame): Con fecha y hora, y valores de OHLCV.
        """
        func_start = timezone.now()
        #Procesando parametros kwargs
        limit = kwargs.get('limit', None )
        from_date = kwargs.get('from_date', None )
        to_date = kwargs.get('to_date', None )

        symbol = Symbol.objects.get(symbol = strSymbol)
        pandas_interval = fn.get_intervals(interval_id,'pandas_resample')
        i_unit = interval_id[1:2]
        i_qty = int(interval_id[2:])
        
        if limit is not None:
            if i_unit == 'm': #Minutos
                delta_time = timedelta(minutes = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d %H:%M')+':00'
            elif i_unit == 'h': #Horas
                delta_time = timedelta(hours = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d %H')+':00:00'
            elif i_unit == 'd': #Dias
                delta_time = timedelta(days = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d')+' 00:00:00'
            
            to_datetime = (datetime.now() + timedelta(days = 1) ).strftime('%Y-%m-%d')+' 23:59:59'

        else:
            from_datetime = from_date+' 00:00:00' if from_date is not None else '2010-01-01 00:00:00'
            to_datetime = to_date+' 23:59:59' if to_date is not None else (datetime.now() - timedelta(days = 1) ).strftime('%Y-%m-%d')+' 23:59:59'
        
        #Se agrega UTC
        from_datetime = from_datetime + '+00:00'
        to_datetime   = to_datetime   + '+00:00'

        klines_values = Kline.objects.filter(symbol_id=symbol.id, 
                                             datetime__gt=from_datetime,
                                             datetime__lt=to_datetime).order_by('datetime').values(
                                                'datetime', 
                                                'open', 
                                                'close', 
                                                'high', 
                                                'low', 
                                                'volume')
        
        # Convertir los datos filtrados en un DataFrame de pandas
        df = pd.DataFrame.from_records(klines_values)
        df.rename(columns={'symbol__symbol': 'symbol'}, inplace=True)
        df['open'] = df['open'].astype(float)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        agg_funcs = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }   
        print('model: Kline.get_df() - Resampling',(timezone.now()-func_start))
        if interval_id != '0m01':
            df = df.resample(pandas_interval, on="datetime").agg(agg_funcs).reset_index()
        if limit is not None:
            df = df[0:limit]
        df['volume'] = round(df['volume'],2)
        df['symbol'] = strSymbol
        print('model: Kline.get_df() - End ',(timezone.now()-func_start))
        return df 
    
    """
    def get_df_old(strSymbol,interval_id,**kwargs):
        print('Kline:get_df ',strSymbol,interval_id,' START ',timezone.now())
        #Procesando parametros kwargs
        limit = kwargs.get('limit', None )
        from_date = kwargs.get('from_date', None )
        to_date = kwargs.get('to_date', None )

        symbol = Symbol.objects.get(symbol = strSymbol)
        pandas_interval = fn.get_intervals(interval_id,'pandas_resample')
        i_unit = interval_id[1:2]
        i_qty = int(interval_id[2:])
        
        if limit is not None:
            if i_unit == 'm': #Minutos
                delta_time = timedelta(minutes = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d %H:%M')+':00'
            elif i_unit == 'h': #Horas
                delta_time = timedelta(hours = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d %H')+':00:00'
            elif i_unit == 'd': #Dias
                delta_time = timedelta(days = i_qty*limit)
                from_datetime = (datetime.now() - delta_time ).strftime('%Y-%m-%d')+' 00:00:00'
            
            to_datetime = (datetime.now() + timedelta(days = 1) ).strftime('%Y-%m-%d')+' 23:59:59'

        else:
            from_datetime = from_date+' 00:00:00' if from_date is not None else '2010-01-01 00:00:00'
            to_datetime = to_date+' 23:59:59' if to_date is not None else (datetime.now() - timedelta(days = 1) ).strftime('%Y-%m-%d')+' 23:59:59'
        
        #Se agrega UTC
        from_datetime = from_datetime + '+00:00'
        to_datetime   = to_datetime   + '+00:00'

        
        if i_unit == 'm': #Minutos
            query =  "SELECT id, symbol_id, datetime, open, high, low, close, volume "
            query += " FROM bot_kline "
            query += " WHERE symbol_id = "+str(symbol.id)+" AND datetime >= '"+str(from_datetime)+"' AND datetime <= '"+str(to_datetime)+"' "
            query += " ORDER BY datetime" 
            klines = Kline.objects.raw(query)
        elif i_unit == 'h': #Horas
            query =  "SELECT id, symbol_id, "
            query += " min(datetime) AS datetime, "
            query += " CAST(SUBSTRING_INDEX(GROUP_CONCAT(open ORDER BY datetime ASC SEPARATOR '|'),'|',1) AS DECIMAL(15,8)) AS open, "
            query += " MAX(high) AS high, "
            query += " MIN(low) AS low, "
            query += " SUM(volume) AS volume, "
            query += " CAST(SUBSTRING_INDEX(GROUP_CONCAT(close ORDER BY datetime DESC SEPARATOR '|'),'|',1) AS DECIMAL(15,8)) AS close "
            query += " FROM bot_kline "
            query += " WHERE symbol_id = "+str(symbol.id)+" AND datetime >= '"+str(from_datetime)+"' AND datetime <= '"+str(to_datetime)+"' "
            query += " GROUP BY symbol_id, date(datetime), hour(datetime) "
            query += " ORDER BY datetime" 
            klines = Kline.objects.raw(query)
            
        elif i_unit == 'd': #Dias
            query =  "SELECT id, symbol_id, "
            query += " min(datetime) AS datetime, "
            query += " CAST(SUBSTRING_INDEX(GROUP_CONCAT(open ORDER BY datetime ASC SEPARATOR '|'),'|',1) AS DECIMAL(15,8)) AS open, "
            query += " MAX(high) AS high, "
            query += " MIN(low) AS low, "
            query += " SUM(volume) AS volume, "
            query += " CAST(SUBSTRING_INDEX(GROUP_CONCAT(close ORDER BY datetime DESC SEPARATOR '|'),'|',1) AS DECIMAL(15,8)) AS close "
            query += " FROM bot_kline "
            query += " WHERE symbol_id = "+str(symbol.id)+" AND datetime >= '"+str(from_datetime)+"' AND datetime <= '"+str(to_datetime)+"' "
            query += " GROUP BY symbol_id, date(datetime) "
            query += " ORDER BY datetime" 
            klines = Kline.objects.raw(query)
        
        if not klines:
            return None
        else:
            data = [{'datetime': kline.datetime, 
                    'open':  float(kline.open),
                    'close': float(kline.close),
                    'high':  float(kline.high),
                    'low':   float(kline.low),
                    'volume':float(kline.volume)
                    } for kline in klines]
            df = pd.DataFrame(data)
            
            agg_funcs = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }   
            
            if i_qty != 1:
                df = df.resample(pandas_interval, on="datetime").agg(agg_funcs).reset_index()
            if limit is not None:
                df = df[0:limit]

            df['symbol'] = strSymbol

            print('Kline:get_df ',strSymbol,interval_id,' END   ',timezone.now())
            return df 
    """