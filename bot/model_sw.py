from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

from django.db.models import Sum
from django.utils import timezone
import pandas as pd
from scripts.Exchange import Exchange
import pickle
import os
from django.conf import settings


from scripts.Bot_Core_utils import Order as BotUtilsOrder
from bot.models import Symbol

class Sw(models.Model):
    name = models.CharField(max_length = 50, unique = True, null=False, blank=False)
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    quote_asset = models.CharField(max_length = 16, null=False, blank=False)
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

    def can_activar(self):
        orders = self.get_orders()
        qty = len(orders)
        return True if (qty > 0 and self.activo == 0) else False
    
    def activar(self):
        self.activo = 1
        self.estado = self.ESTADO_NODATA
        self.save()
        
    def desactivar(self):
        self.activo = 0
        self.estado = self.ESTADO_STOPPED
        self.save()

    def can_delete(self):
        orders = self.get_orders()
        qty = len(orders)
        return True if (qty == 0 and self.activo == 0) else False
    
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
    
    def get_symbols(self):
        symbols = Symbol.objects.filter(sworder__sw=self).distinct()
        return symbols

    def get_assets(self):
        cap = SwOrder.objects.filter(sw=self).order_by('symbol__base_asset')
        base_assets = cap.values_list('symbol__base_asset', flat=True).distinct()
        return list(base_assets)
    
    def get_orders(self,**kwargs):
        if 'symbol' in kwargs:
            orders = SwOrder.objects.filter(sw=self,symbol=kwargs['symbol']).order_by('datetime')
        else:
            orders = SwOrder.objects.filter(sw=self).order_by('datetime')

        return list(orders)

    def get_asset_brief(self, symbol, orders, precio_actual):
        #Calcular el stock total
        stock_compra = sum(o['qty'] for o in orders if (o['side']==0))
        stock_venta  = sum(o['qty'] for o in orders if (o['side']==1))
        stock_total = stock_compra - stock_venta

        #Controlando Stock en cero aproximado
        if stock_total * precio_actual < 0.1: # Stock menor a 0.10 USD
            stock_total = 0.0

        #Calcular el valor del stock actual
        valor_compras = sum(o['qty']*o['price'] for o in orders if (o['side']==0 ))
        valor_ventas = sum(o['qty']*o['price'] for o in orders if (o['side']==1 ))
        stock_quote = valor_ventas - valor_compras

        #Calcular las ganancias y el valor actual total
        precio_promedio = valor_compras/stock_compra
        ganancias_realizadas = sum(o['qty']* (o['price'] - precio_promedio) for o in orders if (o['side']==1))

        
        valor_stock = stock_total * precio_actual
        total_stock_en_usd = stock_quote + valor_stock

        ganancias_y_stock = ganancias_realizadas + total_stock_en_usd
        
        distancia_ppc     = (precio_actual / precio_promedio - 1) * 100

        return {
            'stock_total': round(stock_total,symbol.qty_decs_qty),
            'valor_stock': round(valor_stock,2),
            'precio_promedio': round(precio_promedio,symbol.qty_decs_price),
            'valor_compras': round(valor_compras,2),
            'stock_quote': round(stock_quote,2),
            'total_stock_en_usd': round(total_stock_en_usd,2),
            'precio_actual': round(precio_actual,symbol.qty_decs_price),
            'ganancias_realizadas':  round(ganancias_realizadas,2),
            'distancia_ppc': round(distancia_ppc,2),
            'ganancias_y_stock': round(ganancias_y_stock,2),
            'symbol_id': symbol.id,
        }

    def get_assets_brief(self):

        symbols = self.get_symbols()
        assets_brief = {}
        
        #Buscando precios de los symbols
        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        prices = exchInfo.get_all_prices()

        for symbol in symbols:
            asset = symbol.base_asset
            price = prices[symbol.base_asset+symbol.quote_asset] 
            db_orders = self.get_orders(symbol=symbol)

            orders = []
            for o in db_orders:
                if o.symbol == symbol:
                    orders.append({'qty':o.qty, 'price': o.price,'side':o.side})
            
            assets_brief[asset] = self.get_asset_brief(symbol,orders,price)

        return assets_brief
    
class SwOrder(models.Model):
    sw = models.ForeignKey(Sw, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    completed = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    qty = models.FloatField(null=False, blank=False)
    price = models.FloatField(null=False, blank=False)
    orderid = models.CharField(default='NA', max_length = 20, null=False, blank=True, db_index=True)
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
