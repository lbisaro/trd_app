import pandas as pd
import datetime as dt

from django.utils import timezone

from scripts.Bot_Core_utils import Order as BotCoreUtilsOrder, BotCoreLog
from scripts.functions import round_down

from bot.models import Bot as DbBot

class Bot_Core_live:
    
    log = BotCoreLog()

    def live_get_signal(self,klines):
        self.klines = klines
        self.start()
        #No devuelve la ultima vela porque recien inicia a formarse
        #Es por eso que se devuelve la ante-ultima
        return self.klines.iloc[-2]
    
    def live_execute(self,just_check_orders=False):
        #self.log.info('live_execute()')
        self.backtesting = False
        self.live = True

        self.log.bot_id = self.bot_id
        self.log.username = self.username
        
        jsonRsp = {}
        
        symbol_info = self.exchange.get_symbol_info(self.symbol)
        self.base_asset = symbol_info['base_asset']
        self.quote_asset = symbol_info['quote_asset']
        self.qd_price = symbol_info['qty_decs_price']
        self.qd_qty = symbol_info['qty_decs_qty']
        self.qd_quote = symbol_info['qty_decs_quote']

        self.datetime = dt.datetime.now()
        
        if self.live_check_orders():
            jsonRsp['execute'] = True
        
        if not just_check_orders:
            self.next()
            

        return jsonRsp

    def live_check_orders(self):
        #self.log.info('live_check_orders()')
        executed = False
        price = self.price
       
        if len(self._orders) > 0:
            
            _orders = self._orders.copy().items()
            
            for i,order in _orders:
                print(order)
                if i in self._orders: #Se consulta si esta o no porque puede que se ejecute mas de una orden en la misma vela
                    order  = self._orders[i]

                    if order.type == BotCoreUtilsOrder.TYPE_LIMIT:
                        
                        if order.side == BotCoreUtilsOrder.SIDE_BUY and order.flag != BotCoreUtilsOrder.FLAG_STOPLOSS:
                            if price <= order.limit_price:
                                executed =  self.live_execute_order(order.id)
                                
                        if order.side == BotCoreUtilsOrder.SIDE_BUY and order.flag == BotCoreUtilsOrder.FLAG_STOPLOSS:
                            if price >= order.limit_price:
                                executed =  self.live_execute_order(order.id)

                        if order.side == BotCoreUtilsOrder.SIDE_SELL and order.flag != BotCoreUtilsOrder.FLAG_STOPLOSS:
                            if price >= order.limit_price:
                                executed = self.live_execute_order(order.id)
                                
                        if order.side == BotCoreUtilsOrder.SIDE_SELL and order.flag == BotCoreUtilsOrder.FLAG_STOPLOSS:
                            if price <= order.limit_price:
                                executed = self.live_execute_order(order.id)
        
        return executed
    
    def live_execute_order(self,orderid):
        #self.log.info(f'live_execute_order({orderid})')
        wallet = self.exchange_wallet
        exchange = self.exchange
        broker_wallet_base  = round_down(wallet[self.base_asset]['free'],self.qd_qty)
        broker_wallet_quote = round_down(wallet[self.quote_asset]['free'],self.qd_quote)
        symbol = self.symbol

        order = self._orders[orderid]
        qty = order.qty

        try:
            if order.side == BotCoreUtilsOrder.SIDE_BUY:
                str_side = 'BUY'
                exch_order = exchange.order_market_buy(symbol=symbol, qty= qty)
            else:
                str_side = 'SELL'
                exch_order = exchange.order_market_sell(symbol=symbol, qty= qty)
        except Exception as e:
            self.log.error(f'bot.id: {self.bot_id} {e}')
            self.bloquear_bot(f'No fue posible ejecutar la orden {order} - {e}')
            self.cancel_order(order.id)
            return False

        """
        Binance order status:

        ORDER_STATUS_NEW = 'NEW'
        ORDER_STATUS_PARTIALLY_FILLED = 'PARTIALLY_FILLED'
        ORDER_STATUS_FILLED = 'FILLED'
        ORDER_STATUS_CANCELED = 'CANCELED'
        ORDER_STATUS_PENDING_CANCEL = 'PENDING_CANCEL'
        ORDER_STATUS_REJECTED = 'REJECTED'
        ORDER_STATUS_EXPIRED = 'EXPIRED'
        """
        
        if exch_order['status'] != 'CANCELED' and \
           exch_order['status'] != 'PENDING_CANCEL' and \
           exch_order['status'] != 'REJECTED' and \
           exch_order['status'] != 'EXPIRED':
            
            order.completed = 1 if exch_order['status'] == 'FILLED' else 0
            order.price = 0
            if order.type == BotCoreUtilsOrder.TYPE_MARKET:
                order.limit_price = 0.0
            if order.completed == 1:
                order.price = round(float(exch_order['cummulativeQuoteQty'])/float(exch_order['executedQty']),self.qd_price)
                order.qty = round(float(exch_order['executedQty']),self.qd_qty)
            order.orderid = exch_order['orderId']
            order = self.update_order(order)

            #Pasa la orden a trade
            del self._orders[order.id]
            self._trades[order.id] = order

            order_quote = round(order.qty*order.price,self.qd_quote)
            if order.side == BotCoreUtilsOrder.SIDE_BUY:
                self.wallet_base += order.qty
                self.wallet_quote -= order_quote
            else:
                self.wallet_base -= order.qty
                self.wallet_quote += order_quote
            
            #Descontando comision de la wallet
            comision = (order.qty*order.price) * BotCoreUtilsOrder.live_exch_comision_perc/100
            self.wallet_quote -= comision

            self.on_order_execute(order)
            self.log.info(f'live_execute_order OK - {order}')
            return True
        
        print('Exec. Order ERROR ',exch_order['status'],str(order))
        return False 
    

    def bloquear_bot(self,texto):
        bot = DbBot.objects.get(pk=self.bot_id) 
        bot.bloquear(texto)       


