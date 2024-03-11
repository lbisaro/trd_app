import os
from pathlib import Path

import pandas as pd
BASE_DIR = Path(__file__).resolve().parent.parent

#Configurando intervals
columns=['id','interval_id','name','binance','pandas_resample','minutes']
intervals = pd.DataFrame([ 
                            ['0m01','0m01','1 minuto','1m','1T',1],
                            ['0m05','0m05','5 minutos','5m','5T',5],
                            ['0m15','0m15','15 minutos','15m','15T',15],
                            ['0m30','0m30','30 minutos','30m','30T',30],
                            ['1h01','1h01','1 hora','1h','1H',60],
                            ['1h04','1h04','4 horas','4h','4H',(60*4)],
                            ['2d01','2d01','1 dia','1d','1D',(60*24)],
                            ],columns=columns)
intervals.set_index('id',inplace=True)

symbols = {
    'ADAUSDT', 
    'BNBUSDT', 
    'BTCUSDT',
    'DOTUSDT', 
    'ETHUSDT', 
    'XRPUSDT', 
    'TRXUSDT',
    'EURUSDT',
    #'LUNAUSDT'
}

#Periodos definidos por Tipo, Fecha de inicio y fin y Pares para backtesting
periodos = [{'tipo':'Completo',
            'start':'2021-01-01',
            'end':'2023-07-31',
            'symbols': symbols
            },
            {'tipo':'Alcista',
            'start':'2020-09-07',
            'end':'2021-05-03',
            'symbols': symbols
            },
            {'tipo':'Lateral',
            'start':'2023-06-20',
            'end':'2023-10-09',
            'symbols': symbols
            },
            {'tipo':'Bajista',
            'start':'2021-04-12',
            'end':'2021-07-12',
            'symbols': symbols
            },            
            #{'tipo':'Full',
            #'start':'2019-01-01',
            #'end':'2024-03-07',
            #'symbols': symbols
            #},
            ]


