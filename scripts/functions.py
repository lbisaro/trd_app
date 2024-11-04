import pandas as pd
import numpy as np
from math import floor
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly
import json

def get_intervals(i='ALL',c='ALL'):
    columns=['id','interval_id','name','binance','pandas_resample','minutes']
    intervals = pd.DataFrame([['0m01','0m01','1 minuto','1m','1T',1],
                              ['0m05','0m05','5 minutos','5m','5T',5],
                              ['0m15','0m15','15 minutos','15m','15T',15],
                              ['0m30','0m30','30 minutos','30m','30T',30],
                              ['1h01','1h01','1 hora','1h','1H',60],
                              ['1h04','1h04','4 horas','4h','4H',(60*4)],
                              ['2d01','2d01','1 dia','1d','1D',(60*4*24)],
                              ['2d03','2d03','3 dias','3d','3D',(60*4*24*3)],
                             ],columns=columns)
    intervals.set_index('id',inplace=True)
    if i=='ALL' and c=='ALL':
        return intervals
    else:
        if i!='ALL' and c=='ALL':
            if i in intervals.index:
                return intervals.loc[i]
            else:
                return None
        elif i!='ALL' and c!='ALL':
            if i in intervals.index:
                if c in intervals.loc[i]:
                    return intervals.loc[i][c]
                else:
                    return None
            else:
                return None
            
def get_binance_intervals():
    intervals = get_intervals()
    return intervals['binance'].values


def get_apply_intervals(dt):

    #Se calcula el time interval con GMT+0 para que Al buscar velas de 4hs o diarias, se obtengan velas cerradas
    dt = dt+timedelta(hours=3)
    print(f'get_apply_intervals dt {dt}')

    hr = dt.strftime('%H')
    mn = dt.strftime('%M')

    whereIn = "'0m01'"
    if mn[1]=='0' or mn[1]=='5':
        whereIn = whereIn + ",'0m05'"
    if mn=='00' or mn=='15' or mn=='30' or mn=='45':
        whereIn = whereIn + ",'0m15'"
    if mn=='00' or mn=='30':
        whereIn = whereIn + ",'0m30'"
    if mn=='00' :
        whereIn = whereIn + ",'1h01'"
    if mn=='00' and (hr=='00' or hr=='04' or hr=='08' or hr=='12' or hr=='16' or hr=='20'):
        whereIn = whereIn + ",'1h04'"
    if mn=='00' and (hr=='00'):
        whereIn = whereIn + ",'2d01'"

    return whereIn

def round_down(num, decs):
    pot = 10**decs
    num = num * pot
    num = floor(num)
    num = num / pot
    return num

def pendiente(y):
    qty = len(y)
    x = np.arange(qty)
    p = np.polyfit(x, y, 1)
    return round(p[0],2)

def ohlc_mirror_v(df):
    """
    Transforma el DF invirtiendo las tendencias, 
    espejando los precios de OHLC de forma vertical
    """
    df.rename(columns={'open':'open_i','close':'close_i','low':'low_i','high':'high_i'},inplace=True)

    open_high = df['high_i'].max()
    open_low  = df['low_i'].min()
    open_mean = (open_high+open_low)/2
    df['open_diff'] = open_mean-df['open_i']
    df['open'] = open_mean + df['open_diff']

    df['close_d'] = df['open_i']-df['close_i']
    df['close'] = df['open']+df['close_d']

    df['high_d'] = df['open_i']-df['high_i']
    df['low'] = df['open']+df['high_d']

    df['low_d'] = df['open_i']-df['low_i']
    df['high'] = df['open']+df['low_d']

    df.drop(columns=['open_i','close_i','low_i','high_i','open_diff','close_d','high_d','low_d'],inplace=True)
    return df

def ohlc_mirror_h(df):
    """
    Transforma el DF colocando al inicio las velas finales y viceversa, 
    espejando los precios de OHLC de forma horizontal
    """
    df_i = df.iloc[::-1].copy()
    df_i.reset_index(inplace = True)
    df_i.drop(columns=['index'],inplace=True)
 
    df['close']  = df_i['open']
    df['open']   = df_i['close']
    df['high']   = df_i['high']
    df['low']    = df_i['low']
    df['volume'] = df_i['volume']

    return df

def ohlc_chart(klines,**kwargs):

    """ 
    klines -> dataframe with columns [datetime,open,close,high,low,volume,pnl]
           -> dataframe with columns [datetime,price,pnl]
    show_pnl = True
    show_volume = True
    indicators = [
         {'col': 'MA_F',
          'name': 'MA Fast',
          'color': 'yellow',
          },
         {'col': 'MA_S',
          'name': 'MA Slow',
          'color': 'green',
          },
    ]
    indicators_out = [
         {'col': 'MA_F',
          'name': 'MA Fast',
          'color': 'yellow',
          'row': 1,
          },
         {'col': 'MA_S',
          'name': 'MA Slow',
          'color': 'green',
          },
     ]
     open_orders = [
         {'col': 'ORD_1',
          'color': 'red',
          },
         {'col': 'ORD_n',
          'color': 'green',
          },
     ]
     events = [
         {'df':Dataframe con una columna ['datetime'] y otra con el nombre indicado en el parametro 'col'
          'col':'MA_cross',
          'name': 'MA Cross',
          'color': 'yellow',
          'symbol': 'circle-open' #https://plotly.com/python/reference/scatter/#scatter-marker-symbol
         }
     ]
     """
   
    show_volume   = kwargs.get('show_volume', True )
    show_pnl   = kwargs.get('show_pnl', True )
    indicators = kwargs.get('indicators', None )
    indicators_out = kwargs.get('indicators_out', None )
    open_orders = kwargs.get('open_orders', None )
    events    = kwargs.get('events', None )

    if not 'volume' in klines.columns:
        show_volume = False
    if not 'pnl' in klines.columns:
        show_pnl = False
    
    chart_rows = 1
    row_heights = [400]

    vol_rows = 0
    pnl_rows = 0
        
    if show_pnl:
        pnl_rows = 1
        row_heights.append(100)
    
    if show_volume:
        vol_rows = 1
        row_heights.append(100)

    
    
    io_max_row = 0
    if indicators_out:
        for io in indicators_out:
            if io['row']>io_max_row:
                io_max_row = io['row']
    
    chart_rows = 1+vol_rows+pnl_rows+io_max_row
    for i in range(0,io_max_row):
        row_heights.append(70)
    

    total_height = sum(row_heights)

    row_heights_prop = []
    for h in row_heights:
        row_heights_prop.append( h/total_height )

    fig = make_subplots(rows=chart_rows, 
                        shared_xaxes=True,
                        row_heights=row_heights_prop)

    # Create subplot for candlesticks o price
    if 'price' in klines:
        fig.add_trace(
            go.Scatter(
                x=klines["datetime"], y=klines["price"], name="Price", mode="lines", showlegend=False, 
                line={'width': 0.5},  
                marker=dict(color='#f8b935'),
            ),
            row=1,
            col=1,
        )    
    elif 'close' in klines:
        fig.add_trace(
            go.Candlestick(
                x=klines["datetime"],
                open=klines["open"],
                high=klines["high"],
                low=klines["low"],
                close=klines["close"],
                increasing_line_color= 'rgba(8,153,129,0.5)', 
                decreasing_line_color= 'rgba(242,54,69,0.5)',
                name="BTCUDST", 
                line=dict(width=0.75,),
                showlegend=False, 
                
            ),
            row=1,
            col=1,
        )

    if indicators:
        
        for ind in indicators:
            f_klines = klines[klines[ind['col']]>0]
            mode = "lines"
            if 'mode' in ind:
                mode = ind['mode']
            symbol = 'x'
            if 'symbol' in ind:
                symbol = ind['symbol']
            fig.add_trace(
                go.Scatter(
                    x=f_klines["datetime"], y=f_klines[ind['col']], name=ind['name'], mode=mode,
                    line={'width': 0.5},  
                    marker=dict(color=ind['color'], symbol=symbol, size=2,), 
                ),
                row=1,
                col=1,
            )
            
    if open_orders:
        for oo in open_orders:

            fig.add_trace(
                go.Scatter(
                    x=klines["datetime"], y=klines[oo['col']], name=oo['col'], showlegend=False,
                    line=dict(width= 1.5,color=oo['color'],dash="dot" ), 
                    ),
                row=1,
                col=1,
            )

    if events:
        for event in events:
            fig.add_trace(
                go.Scatter(x=event['df']["datetime"], y=event['df'][event['col']], name=event['name'], mode='markers', 
                        marker=dict(symbol=event['symbol'],
                                    size=8,
                                    color=event['color'],
                                    line=dict(width=0.75, color="black"),
                                    ),
                        ),
                row=1,
                col=1,
            )

    if show_volume:

        fig.append_trace(
            go.Bar(
                x=klines["datetime"],
                y=klines["volume"],
                name="Volumen",  
                showlegend=False, 
                marker=dict(color="rgba(83,189,235,0.75)"),
                marker_line_width=0,
            ),
            row=2,
            col=1,
        )
            
    if show_pnl:
        fig.append_trace(
            go.Scatter(
                x=klines["datetime"], 
                y=klines['pnl'], 
                name="PNL", 
                mode="lines", 
                showlegend=False, 
                line={'width': 1.25},  
                marker=dict(color="#00c6d5"),
            ),
            row=2+vol_rows,
            col=1,
        )
    
    if indicators_out:
        for ind in indicators_out:

            fig.append_trace(
                go.Scatter(
                    x=klines["datetime"], y=klines[ind['col']], name=ind['name'], mode="lines", 
                    line={'width': 0.5},  
                    marker=dict(color=ind['color']),
                ),
                row= 1 + vol_rows + pnl_rows + ind['row'],
                col=1,
            )

    # Adjust layout for subplots
    fig.update_layout(
        font=dict(color="#ffffff", family="Helvetica"),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="rgba(0,0,0,0)",  # Transparent plot area 
        height=total_height,
        
        #title="",
        #xaxis_title="",
        #yaxis_title="",

        #xaxis=dict(domain=[0, 0]),
        xaxis_rangeslider_visible=False,
 
        modebar_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation = 'h',
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )

    #Ajustar el tamaño de cada sub_plot
    fig.update_layout(
        yaxis1=dict(
            title="Precio",
            #domain=[domain_0, 1],
            showticklabels=True,
        ),
    )
    if show_volume and show_pnl: 
        fig.update_layout(
            yaxis2=dict(
                title="Volume",
                #domain=[domain_0, domain_0+0.2],
                showticklabels=True,
            ),
            yaxis3=dict(
                title="PNL",
                #domain=[0, domain_0],
                showticklabels=True,
            ),
            
        ) 
    elif show_volume:
        fig.update_layout(
            yaxis2=dict(
                title="Volume",
                #domain=[0, domain_0],
                showticklabels=True,
            ),
            
        )
    elif show_pnl:
        fig.update_layout(
            yaxis2=dict(
                title="PNL",
                #domain=[0, domain_0],
                showticklabels=True,
            ),
            
        ) 
    
    fig.update_xaxes(showline=True, linewidth=0.5,linecolor='#40444e', gridcolor='#40444e')
    fig.update_yaxes(showline=False, linewidth=0.5,zeroline= False, linecolor='#40444e', gridcolor='rgba(0,0,0,0)') 

    return fig

def plotly_to_json(fig):
        # Serializar fig a JSON
    # Obtener los datos y el layout del objeto Figure
    data = fig.data
    layout = fig.layout
    
    # Convertir los datos a una lista serializable
    serialized_data = [trace.to_plotly_json() for trace in data]

    
    # Convertir el layout a un diccionario serializable
    serialized_layout = layout.to_plotly_json()
    
    # Crear un diccionario que contenga los datos serializados y el layout
    serialized_fig = {'data': serialized_data, 'layout': serialized_layout}

    fig_json = json.dumps(serialized_fig, cls=plotly.utils.PlotlyJSONEncoder)

    return fig_json