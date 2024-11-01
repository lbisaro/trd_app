from scripts.app_log import app_log as Log

class BotCoreLog(Log):
    bot_id = 0
    username = ''

    def write(self,type,msg):
        msg = f'{self.username} Bot#{self.bot_id} {msg}'
        super().write(type,msg)

class Order:

    SIDE_BUY = 0
    SIDE_SELL = 1

    TYPE_MARKET = 0
    TYPE_LIMIT = 1

    FLAG_SIGNAL = 0
    FLAG_STOPLOSS = 1
    FLAG_TAKEPROFIT = 2

    STATE_NEW = 0
    STATE_COMPLETE = 1
    STATE_CANCEL = -1

    live_exch_comision_perc = 0.1

    bot_id = 0
    completed = 0
    id = 0
    type = 0
    datetime = None
    side = 0
    qty = 0
    price = 0
    comision = 0
    tag = ''
    pos_order_id = 0

    def __init__(self,id,type,datetime,side,qty,price,flag,**kwargs):
        self.bot_id = 0
        self.completed = 0
        self.id = id
        self.type = type
        self.datetime = datetime
        self.side = side
        self.qty = qty
        if self.type == self.TYPE_MARKET:
            self.price = price
            self.limit_price = price
        else:
            self.price = 0
            self.limit_price = price
        self.flag = flag
        self.comision = 0
        self.tag = ''
        if 'tag' in kwargs:
            self.tag = kwargs['tag']

        self.activation_price = 0
        self.pos_order_id = 0
        
    
    def __repr__(self):
        return str(self)

    def __str__(self):
        params = f'{self.datetime:%Y-%m-%d %Z %H:%M:%S} #{self.id} {self.str_side()}\t{self.qty}\t{self.price} {self.str_type()} {self.str_flag()} '
        if self.type != self.TYPE_MARKET:
            params += f'Limit Price {self.limit_price} '
        if len(self.tag):
            params += f' {self.tag}'    

        return f'{params}'
    
    def str_flag(self):
        if self.flag == self.FLAG_STOPLOSS:
            return 'STOP-LOSS'        
        elif self.flag == self.FLAG_TAKEPROFIT:
            return 'TAKE_PROFIT'
        else:
            return ''
    
    def str_type(self):
        if self.type == self.TYPE_LIMIT:
            return 'LIMIT'
        else:
            return ''

    
    def str_side(self):
        if self.side == self.SIDE_BUY:
            return 'BUY'        
        else:
            return 'SELL'
        