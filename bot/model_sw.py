from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

from django.db.models import Max
from django.core.exceptions import ValidationError
from django.db.models import F, Min, Max, Avg, Sum
from django.db.models.functions import TruncDay, TruncHour, TruncMinute
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import scripts.functions as fn
from scripts.Exchange import Exchange


from scripts.Bot_Core_utils import Order as BotUtilsOrder
from bot.models import Symbol

class Sw(models.Model):
    name = models.CharField(max_length = 50, unique = True, null=False, blank=False)
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    symbol_stable = models.CharField(max_length = 16, unique = True, null=False, blank=False)
    estado = models.IntegerField(default=timezone.now, null=False, blank=False)
    creado = models.DateTimeField(null=False, blank=False, db_index=True)
    finalizado = models.DateTimeField(null=True, blank=True, db_index=True)
    activo = models.IntegerField(default=0)  

    ESTADO_NODATA = 0
    ESTADO_ONLINE = 10
    ESTADO_STANDBY = 20
    ESTADO_ERROR = 30
    ESTADO_STOPPED = 90

   
    def __str__(self):
        return f'Usuario {self.usuario.username}'
    
    class Meta:
        verbose_name = "Smart Wallet"
        verbose_name_plural='Smart Wallets'

    def activar(self):
        self.activo = 1
        self.estado = self.ESTADO_NODATA
        self.save()
        
    def desactivar(self):
        self.activo = 0
        self.estado = self.ESTADO_STOPPED
        self.save()

    def str_estado(self):
        arr = {
            self.ESTADO_NODATA      : 'Pendiente de incorporar ordenes',
            self.ESTADO_ONLINE      : 'En curso',
            self.ESTADO_STANDBY     : 'En pausa',
            self.ESTADO_ERROR       : 'Error',
            self.ESTADO_STOPPED     : 'Detenido',
        }
        str_activo = 'Activado -' if self.activo > 0 else 'Desactivado -'
        return str_activo+' '+arr.get(self.estado)


    def estado_class(self):
        arr = {
            self.ESTADO_NODATA    : 'text-danger',
            self.ESTADO_ONLINE    : 'text-success',
            self.ESTADO_STANDBY   : 'text-warning',
            self.ESTADO_ERROR     : 'text-danger',
            self.ESTADO_STOPPED   : 'text-secondary',
        }
        return arr.get(self.estado)
    
    
    def get_orders(self):
        orders = SwOrder.objects.filter(sw=self).order_by('datetime')
        return list(orders)
    
    def get_assets(self):
        orders = SwOrder.objects.filter(sw=self).order_by('symbol__base_asset')
        base_assets = orders.values_list('symbol__base_asset', flat=True).distinct()
        return list(base_assets)
    
    def get_assets_brief(self):
        orders = SwOrder.objects.filter(sw=self).order_by('datetime').values(
            *[field.name for field in SwOrder._meta.fields],  # Todos los campos de SwOrder
            *[f'symbol__{field.name}' for field in Symbol._meta.fields]  # Todos los campos de Symbol
        )   
        df_orders = pd.DataFrame.from_records(orders)
        assets = self.get_assets()
        assets_brief = {}
        
        #Buscando precios de los symbols
        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        prices = exchInfo.get_all_prices()
        

        for asset in assets:
            
            df = df_orders[df_orders['symbol__base_asset'] == asset].copy()
            compras = df[(df["side"] == 0)]
            ventas  = df[(df["side"] == 1)]

            #Obteniendo info sobre la cantidad de decimales 
            qd_qty =  compras.iloc[0]['symbol__qty_decs_qty']
            qd_price =  compras.iloc[0]['symbol__qty_decs_price']
            qd_quote =  compras.iloc[0]['symbol__qty_decs_quote']

            # Calcular valores totales de compras
            total_qty_comprada = compras["qty"].sum()
            total_usdt_compras = (compras["qty"] * compras["price"]).sum()
            ppp_compras = total_usdt_compras / total_qty_comprada  # Precio promedio de compras

            # Calcular valores totales de ventas
            total_qty_vendida = ventas["qty"].sum()  # Ya es negativo, lo pasamos a positivo
            total_usdt_ventas = (ventas["qty"].abs() * ventas["price"]).sum()
            
            # Calcular ganancia total
            costo_tokens_vendidos = abs(total_qty_vendida) * ppp_compras
            ganancia_total = total_usdt_ventas - costo_tokens_vendidos

            # Calcular stock final y costo ajustado
            stock_final = total_qty_comprada + total_qty_vendida  # Suma porque ventas es negativo
            costo_ajustado = total_usdt_compras - ganancia_total

            # Calcular nuevo precio promedio ajustado
            ppp_ajustado = costo_ajustado / stock_final if stock_final > 0 else 0

            #Calculo de resultados
            symbol = asset+self.symbol_stable
            qty =  round(total_qty_comprada-total_qty_vendida,qd_qty)
            avg_price = round(ppp_ajustado,qd_price)
            price = prices[symbol]
            buyed = round(qty*avg_price,qd_quote)
            cap = round(qty*price,qd_quote)
            result = round(((cap/buyed)-1)*100,2)
            
            assets_brief[asset] = {'asset': asset,
                                   'qty':qty,
                                   'avg_price': avg_price,
                                   'price': price,
                                   'buyed': buyed,
                                   'cap': cap,
                                   'result': result,
                                   }
            
        #Calculando porcion de cada asset sobre la Smart Wallet
        tot_cap = sum(data['cap'] for data in assets_brief.values())
        for asset in assets:
            assets_brief[asset]['portion'] = round((assets_brief[asset]['cap']/tot_cap)*100,2)
        return assets_brief
        
        
class SwOrder(models.Model):
    sw = models.ForeignKey(Sw, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    completed = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    qty = models.FloatField(null=False, blank=False)
    price = models.FloatField(null=False, blank=False)
    orderid = models.CharField(max_length = 20, null=False, blank=True, db_index=True)
    pos_order_id = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    symbol = models.ForeignKey(Symbol, on_delete = models.CASCADE)
    #Definido en BotUtilsOrder: SIDE_BUY, SIDE_SELL
    side = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    #Definido en BotUtilsOrder: FLAG_SIGNAL, FLAG_STOPLOSS, FLAG_TAKEPROFIT
    flag = models.IntegerField(default=0, null=False, blank=False)
    #Definido en BotUtilsOrder: TYPE_MARKET, TYPE_LIMIT
    type = models.IntegerField(default=0, null=False, blank=False)
    limit_price = models.FloatField(null=False, blank=True, default=0.0)
    tag = models.TextField(null=False, blank=True, default='')
    
    class Meta:
        verbose_name = "SW Order"
        verbose_name_plural='SW Orders'
    
    def __str__(self):
        params = f'{self.datetime:%Y-%m-%d %Z %H:%M} #{self.id} {self.str_side()}\t{self.qty}\t{self.price} {self.str_type()} {self.str_flag()} '
        if self.type != BotUtilsOrder.TYPE_MARKET:
            params += f'Limit Price {self.limit_price} '
        if len(self.tag):
            params += f' {self.tag} '    

        return f'{params}'
        
    def str_side(self):
        if self.side == BotUtilsOrder.SIDE_BUY:
            return 'Compra'
        elif self.side == BotUtilsOrder.SIDE_SELL:
            return 'Venta'
        return ''
    
    def str_flag(self):
        if self.flag == BotUtilsOrder.FLAG_STOPLOSS:
            return 'Stop-Loss'
        elif self.flag == BotUtilsOrder.FLAG_TAKEPROFIT:
            return 'Take-Profit'
        return ''

    def str_type(self):
        if self.type == BotUtilsOrder.TYPE_LIMIT:
            return 'LIMIT'
        else:
            return ''
    
    def quote_qty(self):
        return round( self.price * self.qty , self.symbol.qty_decs_quote)
    
    def comision(self):
        return round(self.quote_qty() * (BotUtilsOrder.live_exch_comision_perc/100) , self.symbol.qty_decs_quote+4 )
