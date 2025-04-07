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

    #reporte.append('Soportes clave históricos:')
    #for level in summary['support_levels']:
    #    reporte.append(f"\n• ${level['mean_price']:.2f}: " \
    #        f"\n{level['mean_volume_pct']:.2f}% volumen " \
    #        f"(\napareció {level['frequency']} veces)")
    #    
    #reporte.append('Resistencias clave históricos:')
    #for level in summary['resistance_levels']:
    #    reporte.append(f"• ${level['mean_price']:.2f}: " \
    #        f"{level['mean_volume_pct']:.2f}% volumen " \
    #        f"(apareció {level['frequency']} veces)")
        
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

    # Generando series de S&R y Market Imbalance
    sr = []
    mi = []
    miu = []
    mid = []
    for i,row in df.iterrows():
        #print(type(row['bid_supports']))
        tot_vol = row['total_bid_volume']+row['total_ask_volume']
        for r in row['bid_supports']['levels']:
            if r['price']>row['base_price']*0.5:
                sr.append({'timestamp': row['timestamp'],
                        'price': r['price'],
                        'pct': round((r['volume']/tot_vol)*100,0),
                        })
        for r in row['ask_resistances']['levels']:
            if r['price']<row['base_price']*1.5:
                sr.append({'timestamp': row['timestamp'],
                        'price': r['price'],
                        'pct': round((r['volume']/tot_vol)*100,0),
                        })
        mi.append({'timestamp':row['timestamp'],
               'mi':-round(row['market_imbalance']['imbalance_pct'],2)})
        if row['market_imbalance']['imbalance_pct']>0:
            miu.append({'timestamp':row['timestamp'],
                        'mi':-round(row['market_imbalance']['imbalance_pct'],2)})
        if row['market_imbalance']['imbalance_pct']<0:
            mid.append({'timestamp':row['timestamp'],
                        'mi':-round(row['market_imbalance']['imbalance_pct'],2)})
    sr = pd.DataFrame(sr)
    sr_pct_max = sr['pct'].max()
    sr_pct_min = sr['pct'].min()
    sr['pct_adj'] = fn.map(sr['pct'],sr_pct_min,sr_pct_max,1,10)
    
    mi = pd.DataFrame(mi, columns=['timestamp','mi'])
    mi['ma'] = mi['mi'].rolling(window=48).mean()
    miu = pd.DataFrame(miu, columns=['timestamp','mi'])
    mid = pd.DataFrame(mid, columns=['timestamp','mi'])

    # Creando Chart 
    chart_rows = 2
    row_heights=[600,100]
    total_height = sum(row_heights)

    fig = make_subplots(rows=chart_rows, 
                        shared_xaxes=True,
                        row_heights=row_heights,
                        )

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"], y=df["base_price"], name=f'{symbol} Price', mode="lines",  
            line={'width': 0.75},  
            marker=dict(color='yellow',),
            legendgroup = '1',
            hovertemplate="%{x}<br>%{y}<extra></extra>",
        ),
        row=1,
        col=1,
    )  


    fig.add_trace(
        go.Scatter(x=sr["timestamp"], y=sr['price'], name='Sop y Res', mode='markers', 
            marker=dict(symbol='circle',
                        size=sr['pct_adj'],
                        color=sr['pct_adj'],
                        colorscale="Aggrnyl", #ice
                        #showscale=True,
                        line=dict(width=0,),
                        ),
            legendgroup = '1',
            hovertemplate="%{x}<br>%{y}<extra></extra>",
            ),row=1,col=1,
    )

    fig.add_trace(
        go.Bar(
            x=miu["timestamp"], y=miu["mi"], name=f'{symbol}',  
            marker=dict(color='#f6465d',
                        line=dict(width=0,)
                        ),
            hovertemplate="%{x}<br>%{y} %<extra></extra>",
            legendgroup = '2',
            showlegend=False,
        ),
        row=2,
        col=1,
    )  
    fig.add_trace(
        go.Bar(
            x=mid["timestamp"], y=mid["mi"], name=f'{symbol}',  
            marker=dict(color='#0ecb81',
                        line=dict(width=0,)
                        ),
            hovertemplate="%{x}<br>%{y} %<extra></extra>",
            legendgroup = '2',
            showlegend=False,
        ),
        row=2,
        col=1,
    )  
    
    fig.add_trace(
        go.Scatter(
            x=mi["timestamp"], y=mi["ma"], name=f'MI MA', mode="lines",  
            line={'width': 0.75},  
            marker=dict(color='white',),
            legendgroup = '1',
            hovertemplate="%{x}<br>%{y}<extra></extra>",
        ),
        row=2,
        col=1,
    ) 

    fig.update_layout(
        font=dict(color="#ffffff", family="Helvetica"),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="#162024",  
        height=total_height,
        xaxis_rangeslider_visible=False,
        modebar_bgcolor="rgba(0,0,0,0)",
        #legend_tracegroupgap = 100,
    )

    fig.update_layout(
        yaxis1=dict(title="Precio",showticklabels=True,),
        yaxis2=dict(title="Balance (%)",showticklabels=True,),
    )
    fig.update_xaxes(showline=False, linewidth=2,linecolor='#000000', gridcolor='rgba(0,0,0,0)')
    fig.update_yaxes(showline=False, linewidth=2, zeroline= False, linecolor='#ff0000', gridcolor='rgba(50,50,50,255)')
    chart = fig.to_html(config = {'scrollZoom': True, }) #'displayModeBar': False
        
    data = {
        'reporte': reporte,
        'chart': chart,


    }

    return render(request, 'ob_panel.html', data)

