/**
 * @class TA
 * Una clase de utilidad con métodos estáticos para el análisis técnico.
 * No almacena estado. Cada método recibe datos y devuelve un nuevo array con los resultados.
 * Este enfoque es funcional y no modifica los datos de entrada originales.
 */
class TA {

  /**
   * Calcula el Average True Range (ATR).
   * @param {Array<Object>} ohlcData - Array de datos con formato {high, low, close, time}.
   * @param {number} period - El período para el cálculo del ATR (por defecto 14).
   * @returns {Array<Object>} Un nuevo array con objetos {time, value} para la serie del ATR.
   *                          Devuelve un array vacío si no hay suficientes datos.
   */
  static ATR(ohlcData, period = 14) {
    if (!ohlcData || ohlcData.length < period) {
      return [];
    }

    const trueRanges = [];
    for (let i = 0; i < ohlcData.length; i++) {
      const candle = ohlcData[i];
      if (i === 0) {
        trueRanges.push(candle.high - candle.low);
        continue;
      }
      const prevClose = ohlcData[i - 1].close;
      const trueRange = Math.max(
        candle.high - candle.low,
        Math.abs(candle.high - prevClose),
        Math.abs(candle.low - prevClose)
      );
      trueRanges.push(trueRange);
    }

    const atrSeries = [];
    let firstAtrSum = 0;
    for (let i = 0; i < period; i++) {
      firstAtrSum += trueRanges[i];
    }
    let prevAtr = firstAtrSum / period;
    
    // El primer ATR corresponde a la vela en el índice 'period - 1'
    atrSeries.push({ time: ohlcData[period - 1].time, value: prevAtr });

    for (let i = period; i < ohlcData.length; i++) {
      const currentAtr = ((prevAtr * (period - 1)) + trueRanges[i]) / period;
      atrSeries.push({ time: ohlcData[i].time, value: currentAtr });
      prevAtr = currentAtr;
    }

    return atrSeries;
  }

  /**
   * Calcula el indicador SuperTrend.
   * @param {Array<Object>} ohlcData - Array de datos con formato {time, open, high, low, close}.
   * @param {number} atrPeriod - El período de ATR a usar para el SuperTrend (por defecto 10).
   * @param {number} multiplier - El multiplicador de ATR (por defecto 3).
   * @returns {Array<Object>} Un nuevo array con objetos {time, value, direction} para la serie del SuperTrend.
   */
  static SuperTrend(ohlcData, atrPeriod = 7, multiplier = 3) {
    if (!ohlcData || ohlcData.length < atrPeriod) {
        return [];
    }

    const DIRECTION_UP = 1;
    const DIRECTION_DOWN = -1
    
    // 1. Calcular el ATR internamente.
    const atrSeries = TA.ATR(ohlcData, atrPeriod);
    // Convertir el ATR a un Map para una búsqueda rápida por 'time'.
    const atrMap = new Map(atrSeries.map(item => [item.time, item.value]));

    const supertrendSeries = [];
    let direction = DIRECTION_UP;
    let prevSupertrend = { value: 0, direction: DIRECTION_UP };

    for (let i = atrPeriod; i < ohlcData.length; i++) {
      const candle = ohlcData[i];
      const atrValue = atrMap.get(candle.time);

      if (!atrValue) continue;

      const basicUpperBand = ((candle.high + candle.low) / 2) + (multiplier * atrValue);
      const basicLowerBand = ((candle.high + candle.low) / 2) - (multiplier * atrValue);

      let finalUpperBand = basicUpperBand;
      let finalLowerBand = basicLowerBand;
      
      const prevCandle = ohlcData[i - 1];
      if (prevSupertrend.value !== 0) {
        if (basicUpperBand < prevSupertrend.value || prevCandle.close > prevSupertrend.value) {
            finalUpperBand = basicUpperBand;
        } else {
            finalUpperBand = prevSupertrend.value;
        }

        if (basicLowerBand > prevSupertrend.value || prevCandle.close < prevSupertrend.value) {
            finalLowerBand = basicLowerBand;
        } else {
            finalLowerBand = prevSupertrend.value;
        }
      }

      let currentSupertrendValue;
      
      if (prevSupertrend.direction === DIRECTION_UP) {
        if (candle.close > finalLowerBand) {
          currentSupertrendValue = finalLowerBand;
          direction = DIRECTION_UP;
        } else {
          currentSupertrendValue = finalUpperBand;
          direction = DIRECTION_DOWN;
        }
      } else { // direction is DIRECTION_DOWN
        if (candle.close < finalUpperBand) {
          currentSupertrendValue = finalUpperBand;
          direction = DIRECTION_DOWN;
        } else {
          currentSupertrendValue = finalLowerBand;
          direction = DIRECTION_UP;
        }
      }

      const resultPoint = {
        time: candle.time,
        value: currentSupertrendValue,
        direction: direction
      };

      supertrendSeries.push(resultPoint);
      prevSupertrend = resultPoint;
    }
    
    return supertrendSeries;
  }
}