from django.contrib import admin
from django.urls import path

from bot import views_estrategia as ve
from bot import views_bot as vb
from bot import views_backtesting as vbt_old
from bot import views_backtest as vbt
from bot import views_graph_test as vgt

from bot import views_symbols as vs

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
    path('bot/toogle_activo/<int:bot_id>/',vb.bot_toogle_activo,name='bot_toogle_activo'),
    path('bot/get_resultados/<int:bot_id>/',vb.get_resultados,name='get_resultados'),
    path('bot/delete/<int:bot_id>/',vb.bot_delete,name='bot_delete'),
    path('bot/bot_order_echange_info/<int:order_id>/',vb.bot_order_echange_info,name='bot_order_echange_info'),

    path('symbols/',vs.symbols,name='symbols'),
    path('symbol/add/',vs.symbol_add,name='symbol_add'),
    path('symbol/get_info/<str:symbol>/',vs.symbol_get_info,name='symbol_get_info'),
    path('symbol/<int:symbol_id>/',vs.symbol,name='symbol'),
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
    
]