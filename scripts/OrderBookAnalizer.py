import pickle
import pandas as pd
from datetime import datetime
import os
import numpy as np

#Version 1.0

class OrderBookAnalyzer:
    def __init__(self, data_file='', price_scale=100):
        """
        Inicializa el analizador del libro de órdenes.
        
        Args:
            data_file (str): Ruta al archivo para guardar datos históricos.
            price_scale (int): Escala de agrupación (ej. 100 para BTC en niveles como 77000, 78000).
        """
        self.data_file = data_file
        self.price_scale = price_scale
        if len(self.data_file) > 0:
            self.df = self.load_or_create_dataframe()

    def load_or_create_dataframe(self):
        """Carga datos históricos o crea un nuevo DataFrame."""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'rb') as f:
                return pickle.load(f)
        return pd.DataFrame(columns=[
            'timestamp',
            'base_price',
            'bid_supports',
            'ask_resistances',
            'total_bid_volume',
            'total_ask_volume',
            'bid_volume_distribution',
            'ask_volume_distribution',
            'market_imbalance',
            'price_scale_used'
        ])

    def _group_by_scale(self, price, is_bid=True):
        """
        Agrupa un precio según la escala definida.
        
        Args:
            price (float): Precio a agrupar.
            is_bid (bool): True para bids (usa floor), False para asks (usa ceil).
        Returns:
            float: Precio agrupado (ej. 77050 → 77000 para bids, 77100 para asks).
        """
        if is_bid:
            return np.floor(price / self.price_scale) * self.price_scale
        else:
            return np.ceil(price / self.price_scale) * self.price_scale

    def find_significant_levels(self, levels, is_bid=True, volume_threshold_pct=7.0):
        """
        Identifica niveles significativos agrupados por escala.
        
        Args:
            levels (list): Lista de [precio, cantidad].
            is_bid (bool): True para bids, False para asks.
            volume_threshold_pct (float): Umbral mínimo de volumen para considerar un nivel.
            
        Returns:
            dict: Niveles significativos con métricas.
        """
        df = pd.DataFrame(levels, columns=['price', 'amount'])
        df['volume'] = df['price'] * df['amount']
        total_volume = df['volume'].sum()
        
        # Agrupar por escala
        df['price_group'] = df['price'].apply(lambda x: self._group_by_scale(x, is_bid))
        
        # Calcular volumen por grupo
        grouped = df.groupby('price_group').agg({
            'price': 'first',  # Precio representativo del grupo
            'volume': 'sum',
            'amount': 'sum'
        }).reset_index()
        
        grouped['volume_pct'] = (grouped['volume'] / total_volume) * 100
        
        # Filtrar por volumen significativo
        significant_levels = grouped[grouped['volume_pct'] > volume_threshold_pct].copy()
        significant_levels.sort_values('price', ascending=not is_bid, inplace=True)
        
        # Calcular fuerza relativa (vs. volumen promedio)
        mean_volume = grouped['volume_pct'].mean()
        significant_levels['strength_score'] = significant_levels['volume_pct'] / mean_volume
        
        return {
            'levels': significant_levels.to_dict('records'),
            'total_volume': total_volume,
            'mean_volume_pct': mean_volume,
            'price_reference': df['price'].iloc[0],
            'dynamic_threshold': volume_threshold_pct
        }

    def calculate_volume_distribution(self, levels, base_price):
        """Calcula la distribución del volumen por rangos de escala."""
        df = pd.DataFrame(levels, columns=['price', 'amount'])
        df['volume'] = df['price'] * df['amount']
        
        # Definir bins basados en la escala
        price_groups = sorted({self._group_by_scale(p, True) for p in df['price']})
        bins = [-np.inf] + price_groups + [np.inf]
        
        df['price_group'] = df['price'].apply(lambda x: self._group_by_scale(x, True))
        distribution = df.groupby('price_group')['volume'].sum().to_dict()
        
        total = sum(distribution.values())
        distribution_pct = {k: (v / total * 100 if total > 0 else 0) for k, v in distribution.items()}
        
        return {
            'absolute': distribution,
            'percentage': distribution_pct,
            'total_volume': total,
            'price_scale_used': self.price_scale
        }

    def calculate_market_imbalance(self, bid_data, ask_data):
        """Calcula el desequilibrio entre compras (bids) y ventas (asks)."""
        total_bid = bid_data['total_volume']
        total_ask = ask_data['total_volume']
        total = total_bid + total_ask
        
        if total > 0:
            imbalance = (total_bid - total_ask) / total * 100  # -100 a +100
            bid_dominance = total_bid / total * 100
        else:
            imbalance = 0
            bid_dominance = 50
            
        return {
            'imbalance_pct': imbalance,
            'bid_dominance_pct': bid_dominance,
            'ratio': total_bid / total_ask if total_ask > 0 else np.inf
        }

    def analyze_order_book(self, bids, asks):
        """Analiza el libro de órdenes y devuelve métricas clave."""
        # 1. Precio base
        base_price = (asks[0][0] + bids[0][0]) / 2
        
        # 2. Soportes y resistencias agrupados por escala
        bid_supports = self.find_significant_levels(bids, is_bid=True)
        ask_resistances = self.find_significant_levels(asks, is_bid=False)
        
        # 3. Distribución del volumen
        bid_distribution = self.calculate_volume_distribution(bids, base_price)
        ask_distribution = self.calculate_volume_distribution(asks, base_price)
        
        # 4. Desequilibrio del mercado
        market_imbalance = self.calculate_market_imbalance(bid_supports, ask_resistances)
        
        # 5. Crear registro
        new_record = {
            'timestamp': datetime.now(),
            'base_price': base_price,
            'bid_supports': bid_supports,
            'ask_resistances': ask_resistances,
            'total_bid_volume': bid_supports['total_volume'],
            'total_ask_volume': ask_resistances['total_volume'],
            'bid_volume_distribution': bid_distribution,
            'ask_volume_distribution': ask_distribution,
            'market_imbalance': market_imbalance,
            'price_scale_used': self.price_scale
        }
        
        # 6. Actualizar DataFrame histórico
        if hasattr(self, 'df'):
            self.df = pd.concat([self.df, pd.DataFrame([new_record])], ignore_index=True)
        else:
            self.df = pd.DataFrame([new_record])
        
        # 7. Guardar datos (si se especificó archivo)
        if len(self.data_file) > 0:
            with open(self.data_file, 'wb') as f:
                pickle.dump(self.df, f)
            
        return new_record

    def get_summary_stats(self, last_n=24):
        """Devuelve un resumen de los últimos `n` registros."""
        if len(self.df) < 1:
            return None
            
        last_records = self.df.tail(last_n)
        
        return {
            'mean_imbalance': last_records['market_imbalance'].apply(lambda x: x['imbalance_pct']).mean(),
            'mean_bid_dominance': last_records['market_imbalance'].apply(lambda x: x['bid_dominance_pct']).mean(),
            'support_levels': self.aggregate_levels(last_records, 'bid_supports'),
            'resistance_levels': self.aggregate_levels(last_records, 'ask_resistances'),
            'price_change_pct': (last_records['base_price'].iloc[-1] / last_records['base_price'].iloc[0] - 1) * 100
        }

    def aggregate_levels(self, df, level_type):
        """Agrupa niveles históricos para identificar zonas clave."""
        all_levels = []
        for _, row in df.iterrows():
            for level in row[level_type]['levels']:
                all_levels.append({
                    'price': level['price'],
                    'volume_pct': level['volume_pct'],
                    'strength_score': level['strength_score']
                })
        
        if not all_levels:
            return []
            
        levels_df = pd.DataFrame(all_levels)
        levels_df['price_bin'] = pd.cut(levels_df['price'], bins=20)
        
        aggregated = levels_df.groupby('price_bin').agg({
            'price': 'mean',
            'volume_pct': ['mean', 'count'],
            'strength_score': 'mean'
        }).reset_index()
        
        aggregated.columns = ['price_bin', 'mean_price', 'mean_volume_pct', 'frequency', 'mean_strength']
        aggregated = aggregated[aggregated['frequency'] > 1]  # Filtra niveles poco frecuentes
        
        return aggregated.sort_values('mean_volume_pct', ascending=False).to_dict('records')

    def analyze_summary(self, summary, n_hours):
        """Muestra un análisis interpretable del resumen."""
        print(f"\n=== Análisis de los últimos {n_hours} horas ===")
        
        # 1. Tendencias
        imbalance = summary['mean_imbalance']
        direction = "COMPRADORA" if imbalance > 0 else "VENDEDORA"
        print(f"\nTendencia del mercado: Presión {direction} ({abs(imbalance):.2f}% de desbalance)")
        
        # 2. Niveles clave
        print("\nSoportes más consistentes:")
        for s in sorted(summary['support_levels'], key=lambda x: -x['frequency'])[:3]:
            print(f"- ${s['mean_price']:.0f}: {s['frequency']} apariciones (Vol: {s['mean_volume_pct']:.1f}%)")
        
        print("\nResistencias más consistentes:")
        for r in sorted(summary['resistance_levels'], key=lambda x: -x['frequency'])[:3]:
            print(f"- ${r['mean_price']:.0f}: {r['frequency']} apariciones (Vol: {r['mean_volume_pct']:.1f}%)")
        
        # 3. Relación precio/volumen
        price_change = summary['price_change_pct']
        vol_ratio = summary['mean_bid_dominance'] / (100 - summary['mean_bid_dominance'])
        
        if price_change > 0 and vol_ratio > 1.5:
            print("\nConfirmación alcista: Precio subiendo con fuerte volumen comprador")
        elif price_change < 0 and vol_ratio < 0.67:
            print("\nConfirmación bajista: Precio bajando con fuerte volumen vendedor")
        else:
            print("\nDivergencia detectada entre precio y volumen")