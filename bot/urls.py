from django.contrib import admin
from django.urls import path

from bot import views_estrategia as ve
from bot import views_bot as vb
from bot import views_backtesting as vbt_old
from bot import views_backtest as vbt
from bot import views_symbols as vs
from bot import views_graph_test as vgt
from bot import views_indicator as vi
from bot import views_sw as sw
from bot import views_ob as ob
from bot import views_alerts as alerts

urlpatterns = [
    path('estrategias/',ve.estrategias,name='estrategias'),
    path('estrategia/<int:estrategia_id>/',ve.estrategia,name='estrategia'),
    path('estrategia/create/',ve.estrategia_create,name='estrategia_create'),
    path('estrategia/load_parametros/<str:clase>/',ve.load_parametros,name='est_load_parametros'),
    path('estrategia/edit/<int:estrategia_id>/',ve.estrategia_edit,name='estrategia_edit'),
    path('estrategia/toogle_activo/<int:estrategia_id>/',ve.estrategia_toogle_activo,name='estrategia_toogle_activo'),
    path('estrategia/delete/<int:estrategia_id>/',ve.estrategia_delete,name='estrategia_delete'),

    path('bots/',vb.bots,name='bots'),
    path('bot/<int:bot_id>/',vb.bot,name='bot'),
    path('bot/create/',vb.bot_create,name='bot_create'),
    path('bot/get_parametros_estrategia/<int:estrategia_id>/',vb.get_parametros_estrategia,name='get_parametros_estrategia'),
    path('bot/edit/<int:bot_id>/',vb.bot_edit,name='bot_edit'),
    path('bot/activar/<int:bot_id>/',vb.activar,name='bot_activar'),
    path('bot/desactivar/<int:bot_id>/<str:action>/',vb.desactivar,name='bot_desactivar'),
    path('bot/get_resultados/<int:bot_id>/',vb.get_resultados,name='get_resultados'),
    path('bot/delete/<int:bot_id>/',vb.bot_delete,name='bot_delete'),
    path('bot/bot_order_echange_info/<int:order_id>/',vb.bot_order_echange_info,name='bot_order_echange_info'),

    path('symbols/',vs.symbols,name='symbols'),
    path('symbol/add/',vs.symbol_add,name='symbol_add'),
    path('symbol/get_info/<str:symbol>/',vs.symbol_get_info,name='symbol_get_info'),
    path('symbol/<int:symbol_id>/',vs.symbol,name='symbol'),
    path('symbol/toogle_activo/<int:symbol_id>/',vs.symbol_toogle_activo,name='symbol_toogle_activo'),
    path('update_klines/<str:symbol>/',vs.update_klines,name='update_klines'),

    path('backtest/',vbt.backtest,name='backtest'),
    path('backtest/config/<str:bot_class_name>/',vbt.config,name='backtest_config'),
    path('backtest/config/<str:bot_class_name>/clone/<int:backtest_id_to_clone>/',vbt.config,name='backtest_clone'),
    path('backtest/create/',vbt.create,name='backtest_create'),
    path('backtest/view/<int:backtest_id>/',vbt.view,name='backtest_view'),
    path('backtest/execute/<int:backtest_id>/',vbt.execute,name='backtest_execute'),
    path('backtest/delete/<int:backtest_id>/',vbt.delete,name='backtest_delete'),

    path('backtesting/',vbt_old.backtesting,name='backtesting'),
    path('backtesting/config/<str:bot_class_name>/',vbt_old.config,name='backtesting_config'),
    path('backtesting/run/',vbt_old.run,name='backtesting_run'),

    path('sw/list',sw.list,name='sw_list'),
    path('sw/create/',sw.create,name='sw_create'),
    path('sw/view/<int:sw_id>/',sw.view,name='sw_view'),
    path('sw/view_orders/<int:sw_id>/<int:symbol_id>/',sw.view_orders,name='sw_view_orders'),
    path('sw/add_trades_empty/<int:sw_id>/',sw.add_trades_empty,name='sw_add_trades_empty'),
    path('sw/add_trades/<int:sw_id>/<int:symbol_id>/',sw.add_trades,name='sw_add_trades'),
    path('sw/activar/<int:sw_id>/',sw.activar,name='sw_activar'),
    path('sw/desactivar/<int:sw_id>/<str:action>/',sw.desactivar,name='sw_desactivar'),
    path('sw/delete/<int:sw_id>/',sw.delete,name='sw_delete'),
    path('sw/get_orders/<int:symbol_id>/',sw.get_orders,name='sw_get_orders'),
    path('sw/add_order/<int:sw_id>/',sw.add_order,name='sw_add_order'),

    path('alerts/list/',alerts.list,name='alerts_list'),
    path('alerts/analyze/<str:key>/',alerts.analyze,name='alerts_analyze'),
    path('alerts/execute/<str:key>/',alerts.execute,name='alerts_execute'),

    path('chart/get/<str:symbol>',vgt.chart_get,name='chart_get'),
    path('chart/',vgt.chart,name='chart'),
    
    path('ob/panel',ob.panel,name='ob_panel'),
    
    path('indicator/',vi.panel,name='indicator_panel'),
]