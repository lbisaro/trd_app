import json
from scripts.CoinmarketCap import CoinmarketCap

def run():
    cmc = CoinmarketCap()

    cmc_data = cmc.top30()

    print(cmc_data)

    print(len(cmc_data))

    nombre_archivo = 'C:/Users/lbisa/OneDrive/Descargas/CoinmarketCap.json'

    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        json.dump(cmc_data, f, indent=4, ensure_ascii=False)