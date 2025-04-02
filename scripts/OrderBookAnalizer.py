import pickle
import pandas as pd
from datetime import datetime
import os
import numpy as np

class OrderBookAnalyzer:
    def __init__(self, data_file=''):
        self.data_file = data_file
        if len(self.data_file)>0:
            self.df = self.load_or_create_dataframe()

    def load_or_create_dataframe(self):
        """Carga el DataFrame existente o crea uno nuevo"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'rb') as f:
                return pickle.load(f)
        return pd.DataFrame(columns=[
            'timestamp',
            'high',
            'low',
            'close',
            'volume',
            'base_price',
            'bid_supports',
            'ask_resistances',
            'total_bid_volume',
            'total_ask_volume',
            'bid_volume_distribution',
            'ask_volume_distribution',
            'market_imbalance'
        ])

    def find_significant_levels(self, levels, is_bid=True, volume_threshold_pct=7.0, price_range_pct=1.0):
        """
        Identifica niveles significativos con métricas relativas
        
        Args:
            levels: Lista de [precio, cantidad]
            is_bid: True para bids, False para asks
            volume_threshold_pct: Umbral porcentual mínimo para considerar nivel
            price_range_pct: Rango alrededor del precio para calcular media
            
        Returns:
            Dict con niveles significativos y métricas
        """
        df = pd.DataFrame(levels, columns=['price', 'amount'])
        df['volume'] = df['price'] * df['amount']
        total_volume = df['volume'].sum()
        
        # Convertir a porcentaje del volumen total
        df['volume_pct'] = (df['volume'] / total_volume) * 100
        
        # Calcular media del volumen en el rango de precios
        price_reference = df['price'].iloc[0]
        price_range = price_reference * (price_range_pct / 100)
        range_mask = (df['price'] >= price_reference - price_range) & \
                     (df['price'] <= price_reference + price_range)
        mean_volume_in_range = df[range_mask]['volume_pct'].mean()
        
        # Umbral dinámico (máximo entre 1.5x la media o 1%)
        dynamic_threshold = max(1.5 * mean_volume_in_range, volume_threshold_pct)
        
        # Filtrar niveles significativos
        significant_levels = df[df['volume_pct'] > dynamic_threshold].copy()
        significant_levels.sort_values('price', ascending=not is_bid, inplace=True)
        
        # Calcular score de fortaleza relativa
        significant_levels['strength_score'] = significant_levels['volume_pct'] / mean_volume_in_range
        
        # Agrupar niveles cercanos (clusters)
        price_group_size = price_reference * 0.005  # Agrupa en bins de 0.5%
        significant_levels['price_group'] = (significant_levels['price'] / price_group_size).round()
        
        clusters = significant_levels.groupby('price_group').agg({
            'price': 'first',
            'volume': 'sum',
            'volume_pct': 'sum',
            'strength_score': 'mean'
        }).reset_index(drop=True)
        
        return {
            'levels': clusters.to_dict('records'),
            'total_volume': total_volume,
            'mean_volume_pct_in_range': mean_volume_in_range,
            'price_reference': price_reference,
            'dynamic_threshold': dynamic_threshold
        }

    def calculate_volume_distribution(self, levels, base_price):
        """Calcula distribución del volumen por rangos porcentuales (versión corregida)"""
        df = pd.DataFrame(levels, columns=['price', 'amount'])
        df['volume'] = df['price'] * df['amount']
        
        # Definir los bins correctamente
        bins_pct = [-5, -2, -1, -0.5, 0, 0.5, 1, 2, 5]
        bins = [base_price * (1 + p/100) for p in bins_pct]
        
        # Añadir -infinito e infinito para capturar valores fuera del rango
        bins = [-np.inf] + bins + [np.inf]
        
        # Definir etiquetas que correspondan a los bins
        labels = [
            '<-5%', 
            '-5% to -2%', 
            '-2% to -1%', 
            '-1% to -0.5%', 
            '-0.5% to 0%',
            '0% to 0.5%', 
            '0.5% to 1%', 
            '1% to 2%', 
            '2% to 5%', 
            '>5%'
        ]
        
        # Verificar que tenemos una etiqueta menos que los bins
        assert len(bins) == len(labels) + 1, "Número de bins y etiquetas no coincide"
        
        df['price_pct_from_base'] = (df['price'] - base_price) / base_price * 100
        df['price_bin'] = pd.cut(
            df['price'], 
            bins=bins, 
            labels=labels,
            include_lowest=True
        )
        
        distribution = df.groupby('price_bin')['volume'].sum().to_dict()
        total = sum(distribution.values())
        distribution_pct = {k: (v/total*100 if total > 0 else 0) for k, v in distribution.items()}
        
        return {
            'absolute': distribution,
            'percentage': distribution_pct,
            'total_volume': total,
            'bins_used': bins,
            'labels_used': labels
        }

    def calculate_market_imbalance(self, bid_data, ask_data):
        """Calcula el desequilibrio entre compra y venta"""
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

    def analyze_order_book(self, high, low, close, volume, bids, asks):
        
        print(bids[0])
        print(asks[0])
        """Analiza el libro de órdenes completo"""
        # 1. Precio base y referencia
        base_price = (asks[0][0] + bids[0][0]) / 2
        
        # 2. Niveles significativos
        bid_supports = self.find_significant_levels(bids, is_bid=True)
        ask_resistances = self.find_significant_levels(asks, is_bid=False)
        
        # 3. Distribución del volumen
        bid_distribution = self.calculate_volume_distribution(bids, base_price)
        ask_distribution = self.calculate_volume_distribution(asks, base_price)
        
        # 4. Desequilibrio del mercado
        market_imbalance = self.calculate_market_imbalance(bid_supports, ask_resistances)
        
        # 5. Crear nuevo registro
        new_record = {
            'timestamp': datetime.now(),
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'base_price': base_price,
            'bid_supports': bid_supports,
            'ask_resistances': ask_resistances,
            'total_bid_volume': bid_supports['total_volume'],
            'total_ask_volume': ask_resistances['total_volume'],
            'bid_volume_distribution': bid_distribution,
            'ask_volume_distribution': ask_distribution,
            'market_imbalance': market_imbalance
        }
        
        # 6. Actualizar DataFrame
        self.df = pd.concat([self.df, pd.DataFrame([new_record])], ignore_index=True)
        
        ## 7. Guardar datos
        if len(self.data_file)>0:
            with open(self.data_file, 'wb') as f:
                pickle.dump(self.df, f)
            
        return new_record

    def get_summary_stats(self, last_n=24):
        """Devuelve estadísticas resumidas de los últimos N registros"""
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
        """Agrega niveles a lo largo del tiempo"""
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