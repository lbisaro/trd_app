from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.conf import settings

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pandas as pd
import numpy as np
import pickle
import os
from datetime import timedelta

import scripts.OrderBookAnalizer as oba
import scripts.functions as fn

@login_required
def panel(request):
    
    symbol='BTCUSDT'
    LOG_DIR = os.path.join(settings.BASE_DIR,'log')
    DATA_FILE = os.path.join(LOG_DIR, f"order_book_{symbol}_historic.pkl")
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as archivo:
            df = pickle.load(archivo)

    # Creando summary
    reporte = []
    qty_recs = df['timestamp'].count()
    if qty_recs>48:
        qty_recs = 48
    reporte.append('Tiempo de datos almacenados: '+str(df.iloc[-1]['timestamp']-df.iloc[0]['timestamp']))

    #Primer analisis sobre ultima lectura de ordenes
    analysis_result = df.iloc[-1]
    imbalance = analysis_result['market_imbalance']['imbalance_pct']

    if imbalance > 25:
        reporte.append('Fuerte presión COMPRADORA - Posible movimiento alcista')
    elif imbalance > 10:
        reporte.append('Moderada presión compradora')
    elif imbalance < -25:
        reporte.append('Fuerte presión VENDEDORA - Posible movimiento bajista')
    elif imbalance < -10:
        reporte.append('Moderada presión vendedora')
    else:
        reporte.append('Mercado equilibrado')

    analizer = oba.OrderBookAnalyzer(DATA_FILE)
    summary = analizer.get_summary_stats(qty_recs)

    
    change = summary['price_change_pct']
    direction = "subió" if change > 0 else "bajó"
    reporte.append(f"El precio {direction} un {abs(change):.2f}% en las últimas {qty_recs/2} horas")

    reporte.append(f"📈 Resumen {qty_recs/2}h | Δ {summary['price_change_pct']:+.2f}%")
    reporte.append(f"⚖️ Desbalance: {summary['mean_imbalance']:+.1f}%")
    #reporte.append(f"🛡️ Soportes clave: {len(summary['support_levels'])}")
    #reporte.append(f"🚧 Resistencias: {len(summary['resistance_levels'])}")

    reporte.append("🔝 Top resistencias:")
    for s in sorted(summary['resistance_levels'], key=lambda x: -x['mean_volume_pct'])[:3]:
        reporte.append(f"• ${s['mean_price']:.0f} | 📊 {s['mean_volume_pct']:.1f}% | 🔁 {s['frequency']}x")

    reporte.append("🔝 Top soportes:")
    for s in sorted(summary['support_levels'], key=lambda x: -x['mean_volume_pct'])[:3]:
        reporte.append(f"• ${s['mean_price']:.0f} | 📊 {s['mean_volume_pct']:.1f}% | 🔁 {s['frequency']}x")

    

    resample_periods = 2
    resample_str = '1H'


    df_indexado = df.set_index('timestamp')
    dfr = df_indexado.resample(resample_str).first()
    dfr = dfr.reset_index()
    dfr = dfr[['timestamp']]
    dfr['timestamp'] = pd.to_datetime(dfr['timestamp'].dt.strftime('%Y-%m-%d %H:%M'))
    dfr['next_ts'] = dfr['timestamp'].shift(-1)
    dfr['next_ts'].fillna(dfr['timestamp'] + timedelta(days=2), inplace=True)

    analizer = oba.OrderBookAnalyzer()
    data = []
    sr = []
    for i,row in dfr.iterrows():
        start = row['timestamp']
        end = row['next_ts']
        dfp = df[(df['timestamp']>=start)&(df['timestamp']<end)] 
        qty_recs = dfp['timestamp'].count()
        
        analizer.load_data(dfp)
        summary = analizer.get_summary_stats(qty_recs)
        data_r = {
                'timestamp': row['timestamp'],
                'high_price': summary['high_price'],
                'low_price': summary['low_price'],
                'mi': -summary['mean_imbalance'],       
                }
            
        data.append(data_r)
        for i in summary['support_levels']:
            if i['mean_price']>summary['low_price']*0.6:
                sr.append({'timestamp': row['timestamp'],
                        'price': i['mean_price'],
                        'pct': i['mean_volume_pct'],
                        })
        for i in summary['resistance_levels']:
            if i['mean_price']<summary['low_price']*1.4:
                sr.append({'timestamp': row['timestamp'],
                        'price': i['mean_price'],
                        'pct': i['mean_volume_pct'],
                        })

    dfr = pd.DataFrame(data)
    dfr['mi_ma'] = dfr['mi'].rolling(window=int(48/resample_periods)).mean()
    sr = pd.DataFrame(sr)
    sr_pct_max = sr['pct'].max()
    sr_pct_min = sr['pct'].min()
    sr['pct_adj'] = fn.map(sr['pct'],sr_pct_min,sr_pct_max,1,10)

    # Creando Chart 
    chart_rows = 2
    row_heights=[600,200]
    total_height = sum(row_heights)


    fig = make_subplots(rows=chart_rows, 
                        shared_xaxes=True,
                        row_heights=row_heights,
                        )

    # Línea High
    fig.add_trace(
        go.Scatter(
            x=dfr["timestamp"], y=dfr["high_price"], name=f'{symbol}', mode="lines",
            line={'width': 0.5, 'color': '#fd7e14'},
            marker=dict(color='#fd7e14',),
            hovertemplate="%{x}<br>%{y}<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Línea Low con relleno hacia la línea High
    fig.add_trace(
        go.Scatter(
            x=dfr["timestamp"], y=dfr["low_price"], name=f'{symbol}', mode="lines",
            line={'width': 0.5, 'color': '#fd7e14'},
            marker=dict(color='#fd7e14',),
            hovertemplate="%{x}<br>%{y}<extra></extra>",
            showlegend=False,
            fill='tonexty',  # Rellena hacia la siguiente traza en el eje y
            fillcolor='rgba(253, 126, 20, 0.25)', # Color de relleno blanco (opcional, por defecto es el color de la traza anterior)
        ),
        row=1,
        col=1,
    )


    fig.add_trace(
        go.Scatter(x=sr["timestamp"], y=sr['price'], name='Sop y Res', mode='markers', 
            marker=dict(symbol='circle',
                        size=sr['pct_adj'],
                        color=sr['pct_adj'],
                        colorscale="Aggrnyl",
                        #showscale=True,
                        line=dict(width=0,),
                        ),
            hovertemplate="%{x}<br>%{y}<extra></extra>",
            showlegend=False,
            ),row=1,col=1,
        )

    def get_bar_color(value):
        if value == 0:
            return '#333333'  # Gris oscuro para 0
        elif value > 25:
            return '#0ecb81'
        elif value > 10:
            return 'rgba(14, 203, 129, 0.75)'
        elif value > 0:
            return 'rgba(14, 203, 129, 0.5)'
        elif value < -25:
            return '#f6465d'
        elif value < -10:
            return 'rgba(246, 70, 93, 0.75)'
        elif value < 0:
            return 'rgba(246, 70, 93, 0.5)'
        else: 
            return '#333333'

    # Aplicar la función para obtener la lista de colores
    bar_colors = dfr["mi"].apply(get_bar_color)

    # Gráfica de barras con color variable
    fig.add_trace(
        go.Bar(
            x=dfr["timestamp"], y=dfr["mi"], name=f'{symbol}',
            marker=dict(color=bar_colors,
                        line=dict(width=0,)
                        ),
            hovertemplate="%{x}<br>%{y}<extra></extra>",
            showlegend=False,
        ), row=2, col=1,
    )

    # Adjust layout for subplots
    fig.update_layout(
        font=dict(color="#ffffff", family="Helvetica"),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="#162024",  
        height=total_height,
        xaxis_rangeslider_visible=False,
        modebar_bgcolor="rgba(0,0,0,0)",
    )

    #Ajustar el tamaño de cada sub_plot
    fig.update_layout(
        yaxis1=dict(title="Precio",showticklabels=True,),
        yaxis2=dict(title="Balance del Mercado (%)",showticklabels=True,),
    )
    fig.update_xaxes(showline=False, linewidth=2,linecolor='#000000', gridcolor='rgba(0,0,0,0)')
    fig.update_yaxes(showline=False, linewidth=2, zeroline= False, linecolor='#ff0000', gridcolor='rgba(50,50,50,255)') 
    chart = fig.to_html(config = {'scrollZoom': True, }) #'displayModeBar': False
        
    data = {
        'reporte': reporte,
        'chart': chart,


    }

    return render(request, 'ob_panel.html', data)

