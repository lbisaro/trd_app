from scripts.Exchange import Exchange
from bot.models import *
from bot.model_sw import *
from user.models import UserProfile
import scripts.functions as fn

def run():

    today = datetime.now().date()
    now = datetime.now()

    if now.minute == 59:

        exch_info = Exchange(type='info',exchange='bnc', prms=None)
        prices = exch_info.get_all_prices()
        
        #Obteniendo lista de usuarios
        profiles = UserProfile.objects.all()
        for profile in profiles:
            profile_config = profile.parse_config()
            prms = {}
            prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
            prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
            prms['bnc_env'] = profile_config['bnc']['bnc_env']
            try:
                exch = Exchange(type='user_apikey',exchange='bnc',prms=prms) 
                #Cargando Billetera del Exchange
                account = exch.client.margin_v1_get_asset_wallet_balance()
                usdt = 0.0
                for wallet_type in account:
                    btc_balance = float(wallet_type['balance'])
                    usdt += btc_balance*prices['BTCUSDT']
                usdt = round(usdt,2)
                
                WalletLog.objects.update_or_create(
                    usuario=profile.user,
                    date=today,
                    defaults={'total_usd': usdt}
                )
                print(f'Total USDT {usdt}')
                    
            except:
                print('No fue posible obtener la billetera del usuario')
            
            print('|----------------------------------------->')

            