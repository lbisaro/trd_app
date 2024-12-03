import pandas as pd
import datetime as dt
from datetime import timedelta

from django.utils import timezone

from scripts.Bot_Core_utils import Order as BotCoreUtilsOrder, BotCoreLog
from scripts.functions import round_down

from bot.models import Bot as DbBot


class Bot_Core_live:
    
    log = BotCoreLog()
    klines = pd.DataFrame()

    def live_get_signal(self,klines,timeframe_minutes,ref_dt):
        timeframe_minutes = int(timeframe_minutes)
        if timeframe_minutes<(60*24):
            strftime_format = '%Y-%m-%d %H:%M'
        else:
            strftime_format = '%Y-%m-%d'
        
        signal_key = (ref_dt - timedelta(minutes=timeframe_minutes)).strftime(strftime_format)
        
        self.klines = klines
        self.start()

        info = 'live_get_signal - RefDT: '+ref_dt.strftime(strftime_format)
        info += f' - signal_key: {signal_key}'
        for i in range(len(self.klines) - 1, -1, -1):
            row_signal = self.klines.iloc[i]
            info += ' -> '+row_signal['datetime'].strftime(strftime_format)
            if row_signal['datetime'].strftime(strftime_format) == signal_key:
                info += ' <- '+row_signal['signal']
                self.log.info(info)
                return row_signal
        
        self.log.error('Bot_Core_live::live_get_signal() - No fue posible obtener row_signals')
        return pd.DataFrame()
    
    def live_execute(self,just_check_orders=False):
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
        executed = False
        price = self.price
       
        if len(self._orders) > 0:
            _orders = self._orders.copy().items()
            
            for i,order in _orders:
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
        exchange = self.exchange
        wallet = self.exchange_wallet
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

            
            self.on_order_execute(order)
            self.log.info(f'live_execute_order OK - {order}')
            return True
        
        print('Exec. Order ERROR ',exch_order['status'],str(order))
        return False 

    def bloquear_bot(self,texto):
        bot = DbBot.objects.get(pk=self.bot_id) 
        bot.bloquear(texto)       