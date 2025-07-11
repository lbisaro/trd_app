import os
from pathlib import Path

import pandas as pd
BASE_DIR = Path(__file__).resolve().parent.parent

#Configurando intervals
columns=['id','interval_id','name','binance','pandas_resample','minutes']
intervals = pd.DataFrame([ 
                            ['0m01','0m01','1 minuto','1m','1T',1],
                            #['0m05','0m05','5 minutos','5m','5T',5],
                            #['0m15','0m15','15 minutos','15m','15T',15],
                            #['0m30','0m30','30 minutos','30m','30T',30],
                            ['1h01','1h01','1 hora','1h','1H',60],
                            #['1h04','1h04','4 horas','4h','4H',(60*4)],
                            #['2d01','2d01','1 dia','1d','1D',(60*24)],
                            ],columns=columns)
intervals.set_index('id',inplace=True)

symbols = {
    'BNBUSDT', 
    'BTCUSDT',
    'ETHUSDT', 
    
    #Top 30 MarketCap
    #'XRPUSDT',
    #'SOLUSDT',
    #'TRXUSDT',
    #'DOGEUSDT',
    #'ADAUSDT',
    #'WBTCUSDT',
    #'BCHUSDT',
    #'SUIUSDT',
    #'LINKUSDT',
    #'XLMUSDT',
    #'AVAXUSDT',
    #'SHIBUSDT',
    #'LTCUSDT',
    #'HBARUSDT',
    #'DOTUSDT',
    #'UNIUSDT',
    #'PEPEUSDT',
    #'AAVEUSDT',
    #'APTUSDT',
    #'NEARUSDT',
    #'ICPUSDT',
    #'ETCUSDT',
    #'VETUSDT',
    #'ATOMUSDT',
    #'FETUSDT',
    #'FILUSDT',
    #'WLDUSDT',
    #'ALGOUSDT',
    #'NEXOUSDT',
    #'OPUSDT',

    #'AAVEUSDT',
    #'GMXUSDT',
    #'AVAXUSDT',
    #'GALAUSDT',

    #'TRXUSDT',
    #'MATICUSDT',
    #'ETHBTC',
    #'LUNAUSDT'
}

#Periodos definidos por Tipo, Fecha de inicio y fin y Pares para backtesting
periodos = [
            #{'tipo':'Completo',
            #'start':'2021-01-01',
            #'end':'2023-07-31',
            #'symbols': symbols
            #},
            {'tipo':'top30',
            'start':'2024-05-01',
            'end':'2025-05-31',
            'symbols': symbols
            },
            #{'tipo':'Full',
            #'start':'2019-01-01',
            #'end':'2024-11-13',
            #'symbols': symbols
            #},
            #{'tipo':'Alts',
            #'start':'2024-05-28',
            #'end':'2025-05-28',
            #'symbols': symbols
            #},
            ]


