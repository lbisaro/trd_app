// ===============================================================
// CLASE PRINCIPAL LWC
// ===============================================================

function formatTime(time) {
    return (Date.parse(time)/1000) - (3 * 3600);
}

function timeToStr(timestamp) {
    const fecha = new Date(timestamp * 1000);
    return fecha.toUTCString();
}

class LWC {
    startClick = null;
    endClick = null;
    meassureData = null;
    meassureSerie = null;
    meassureMarkers = null;
    crosshairTime = null;

    constructor(containerId, height = 400) {
        this.containerId = containerId;
        this.height = height;

        this.btnStyle = "position: absolute;z-index: 10; top: 0; padding: 0px 4px; border: 0px;background-color: transparent; ";

        if (!this.containerId) {
            console.error('Se debe especificar el parametro containerId');
            return;
        }

        const chartContainer = document.getElementById(this.containerId);
        if (!chartContainer) {
            console.error(`Error: El elemento con ID '${this.containerId}' no se encontró.`);
            return;
        }

        this.chart = LightweightCharts.createChart(chartContainer, {
            height: height,
            width: parseInt($('#' + this.containerId).css('width')),
            layout: {
                background: { color: '#212529' },
                textColor: '#DDD',
                fontSize: 10,
                panes: {
                    separatorColor: '#444',
                    separatorHoverColor: 'rgba(233, 233, 233, 0.09)',
                    enableResize: true,
                },
            },
            grid: {
                vertLines: { color: '#333' },
                horzLines: { color: '#333' },
            },
            leftPriceScale: {
                visible: false,
            },
            rightPriceScale: {
                visible: true,
                borderColor: '#444',
                barSpacing: 5,
            },
            crosshair: {
                mode: 0,
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#444',
            },
            localization: {
                locale: 'es-ES',
            },
        });

        window.addEventListener('resize', () => {
            this.chart.resize(parseInt($('#' + this.containerId).css('width')), height);
        });
    }

    addButton (innerHTML,onclick) {
        const container = document.querySelector('#' + this.containerId+' #actionBar');
        const button = document.createElement("button");
        button.style = 'padding: 0px 4px; border: 0px; background-color: transparent;';
        button.innerHTML = innerHTML;
        button.addEventListener('click', () => {
            eval(onclick);
            });
        container.appendChild(button);
    }

    addPaneTitle(title='',color='', paneIndex=0) {
        setTimeout(function () {

            const panes = this.chart.panes();
            const pane = panes[paneIndex];
            
            var container = pane.getHTMLElement();
            
            var div = document.createElement('div');
            div.style = `padding: 0px 4px; ${color?'color: '+color+';':''} text-align: center; background-color: transparent; position:absolute;left:0px;top:0px;height:19px;width:100%;margin:0;border:0;z-index:3;`;
            div.textContent = title;
            container.cells[1].appendChild(div);
        },250);
        
    }

    getChart() {
        
        this.addButton('<i class="bi bi-arrows-expand-vertical"></i>','this.fullView();');
        this.addButton('<i class="bi bi-bootstrap-reboot"></i>','this.minView();');

        this.minView();

        this.chart.subscribeClick(param => {
            if (!param.point) {return;}
            
            if (!this.startClick && this.endClick ) {
                if (this.meassureSerie) {
                    this.chart.removeSeries(this.meassureSerie);
                    this.meassureSerie = null;
                    this.meassureData = null;
                    this.meassureMarkers = null;
                }
                this.endClick = null;
                return;
            }

            const paneIndex = param.paneIndex;
            const pane = this.chart.panes()[paneIndex];
            const serieRef = pane.getSeries()[0];
            
            const y_coordinate = param.point.y;
            const priceValue = serieRef.coordinateToPrice(y_coordinate);
            if (priceValue === null) {return;}

            const referPoint = { time: param.time, 
                                   value: priceValue, 
                                   timeStr: timeToStr(param.time), 
                                   y_coordinate: y_coordinate,   
                                   paneIndex: paneIndex,   
                                };

            if (!this.startClick) {

                if (this.meassureSerie) {
                    this.chart.removeSeries(this.meassureSerie);
                    this.meassureSerie = null;
                    this.meassureData = null;
                    this.meassureMarkers = null;
                }
                this.startClick = referPoint;
            } else {
                this.startClick = null;
                this.endClick = referPoint;
           }
        });

        this.chart.subscribeCrosshairMove(param => {
            const checkTime = Date.now()
            if (!this.crosshairTime)
                this.crosshairTime = checkTime;
            else if (checkTime-this.crosshairTime < 50){
                return;
            }
            this.crosshairTime = checkTime;
                

            if (!param.point) {return;}
            if (this.startClick) {
                const paneIndex = param.paneIndex;
                const pane = this.chart.panes()[paneIndex];
                const serieRef = pane.getSeries()[0];

                const y_coordinate = param.point.y;
                const priceValue = serieRef.coordinateToPrice(y_coordinate);
                if (priceValue === null) {return;}

                const referPoint = { time: param.time, 
                                    value: priceValue, 
                                    timeStr: timeToStr(param.time), 
                                    y_coordinate: y_coordinate,   
                                    paneIndex: paneIndex,   
                                    };
                this.endClick = referPoint;

                const valor1 =  this.startClick.value;
                const valor2 =  this.endClick.value;

                const porcentaje = ((valor2 - valor1) / Math.abs(valor1)) * 100
                                            
                const meassureColor = (porcentaje > 0 ? '#0ecb8188' : '#f6465d88');

                if (this.startClick.value && this.endClick.value && this.startClick.time && this.endClick.time) {
                    if (this.startClick.paneIndex == this.endClick.paneIndex) {
                        if (this.endClick.time > this.startClick.time)
                            this.meassureData = [this.startClick,this.endClick];
                        else
                            this.meassureData = [this.endClick,this.startClick];
                        if (!this.meassureSerie) {
                            this.meassureSerie = this.chart.addSeries(LightweightCharts.LineSeries, {
                                lineWidth: 1,
                                color: meassureColor,
                                lastValueVisible: false,
                                crosshairMarkerVisible: false,
                                priceLineVisible: false,
                            }, paneIndex);
                        }
                        this.meassureSerie.applyOptions({color: meassureColor, })
                        this.meassureSerie.setData(this.meassureData);
                        const meassureMarkers = [
                            {
                                time: this.meassureData[0].time,
                                position: 'inBar',
                                color: meassureColor,
                                shape: 'circle',
                                text: '',
                            },
                                            {
                                time: this.meassureData[1].time,
                                position: 'inBar',
                                color: meassureColor,
                                shape: 'circle',
                                text: `${porcentaje.toFixed(2)}%`,
                            },
                        ];
                        if (this.meassureMarkers)
                            this.meassureMarkers.setMarkers([]);
                        this.meassureMarkers = LightweightCharts.createSeriesMarkers(this.meassureSerie, meassureMarkers);

                    }
                }                
            }
        });

        return this.chart;
    }

    minView() {
        this.chart.timeScale().resetTimeScale();
        this.chart.priceScale('right').applyOptions({mode: 0,});
    }

    fullView() {
        this.chart.timeScale().fitContent();
        this.chart.priceScale('right').applyOptions({mode: 0,});
    }

    addPriceSeries(sData, pane = 0, height = 100, precision = 2, title = '', priceScaleId='right') {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const priceSeries = this.chart.addSeries(LightweightCharts.LineSeries, {
            priceFormat: {
                type: 'custom',
                formatter: (price) => `${price.toFixed(precision)}`,
            },
            lastValueVisible: true,
            lineWidth: 1,
            priceScaleId: priceScaleId,
            title: title,
            color: '#f8b935',
            crosshairMarkerVisible: false,
            priceLineVisible: false,
        }, pane);
        priceSeries.setData(sData);
        if (pane > 0)
            this.chart.panes()[[pane]].setHeight(height);
        return priceSeries;
    }

    addPnlSeries(sData, pane = 0, height = 100, precision = 2, title = '', priceScaleId='right') {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const pnlSeries = this.chart.addSeries(LightweightCharts.BaselineSeries, {
            priceFormat: {
                type: 'custom',
                formatter: (price) => `${price.toFixed(precision)}`,
            },
            priceScaleId: priceScaleId,
            baseValue: { type: 'price', price: -0.1 },
            topLineColor: '#0ecb81',
            topFillColor1: 'rgba( 38, 166, 154, 0.28)',
            topFillColor2: 'transparent',
            bottomLineColor: '#f6465d',
            bottomFillColor1: 'transparent',
            bottomFillColor2: 'rgba( 239, 83, 80, 0.28)',
            title: title,
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
        }, pane);
        pnlSeries.setData(sData);
        if (pane > 0)
            this.chart.panes()[[pane]].setHeight(height);
        return pnlSeries;
    }


    addTop30Series(sData, title = '', color='', pane = 0 ) {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const top30Series = this.chart.addSeries(LightweightCharts.LineSeries, {
            priceFormat: {
                type: 'custom',
                formatter: (price) => `${price.toFixed(2)}`,
            },
            color: color,
            title:title,
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
        }, pane);
        top30Series.setData(sData);
        return top30Series;
    }

    addRefLineSeries(value, color='', paneIndex = 0 ) {
        const pane = this.chart.panes()[paneIndex];
        const series = pane.getSeries();   
        
        if (series.length==0) return;

        var minTime = null;
        var maxTime = null;
        for (var i=0; i<series.length; i++) {
            const times = series[i].data().map(d => d.time);
            const max = Math.max(...times);
            const min = Math.min(...times);

            if (!minTime || min<minTime)
                minTime = min;
            if (!maxTime || max<maxTime)
                maxTime = max;
        }
        const sData = [{time: minTime, value: value}, {time: maxTime, value: value},];
        
        const rlSeries = this.chart.addSeries(LightweightCharts.LineSeries, {
                color: color,
                lineWidth: 1,
                lineStyle: 3, //Solid: 0 | Dotted: 1 | Dashed: 2 | LargeDashed: 3 | SparseDotted: 4
                priceLineVisible: false,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
            }, paneIndex);
        rlSeries.setData(sData);
        return rlSeries;
    }

    addIndicatorsSeries(sData, color='gray', title = '', pane=0) {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const indSeries = this.chart.addSeries(LightweightCharts.LineSeries, {
            lastValueVisible: false,
            lineWidth: 1,
            title: title,
            color: color,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
        }, pane);
        indSeries.setData(sData);
        return indSeries;
    }

    addTradesSeries(sData, pane = 0) {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const serie = this.chart.addSeries(LightweightCharts.LineSeries, {
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            color: 'transparent',
        }, pane);
        serie.setData(sData);

        var markers = []
        for (let i = 0; i < sData.length; i++) {
            if (sData[i].side == 0) {
                markers.push({
                    time: sData[i].time,
                    position: 'inBar',
                    color: '#0ecb81',
                    shape: 'arrowUp',
                });
            }
            else {
                markers.push({
                    time: sData[i].time,
                    position: 'inBar',
                    color: '#f6465d',
                    shape: 'arrowDown',
                });
            }
        }
        return LightweightCharts.createSeriesMarkers(serie, markers);
    }

    
    addSignalsSeries(sData, pane = 0) {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const serie = this.chart.addSeries(LightweightCharts.LineSeries, {
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            color: 'transparent',
        }, pane);
        serie.setData(sData);

        var markers = []
        for (let i = 0; i < sData.length; i++) {
            if (sData[i].side == 0) {
                markers.push({
                    time: sData[i].time,
                    position: 'belowBar',
                    color: '#fd7e1488',
                    shape: 'signalUp',
                });
            }
            else {
                markers.push({
                    time: sData[i].time,
                    position: 'aboveBar',
                    color: '#fd7e1488',
                    shape: 'signalDown',
                });
            }
        }
        return LightweightCharts.createSeriesMarkers(serie, markers);
    }

    addOrdersSeries(sData, pane = 0) {
        sData = this.filterNullData(sData);
        if (sData.length ==0)
            return null;
        const color = sData[0].side == 0 ? '#0ecb81' : '#f6465d';
        const serie = this.chart.addSeries(LightweightCharts.LineSeries, {
            lineWidth: 1,
            color: color,
            lineStyle: 1, //Solid: 0 | Dotted: 1 | Dashed: 2 | LargeDashed: 3 | SparseDotted: 4
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        }, pane);

        serie.setData(sData);
        return serie;
    }

    filterNullData(sData) {

        const correctedData = sData.map(item => {
            if (item.value === null) {
                item.color = 'transparent';
                item.value = NaN;
            }
            return item;
        });
        return correctedData; //sData.filter(item => item.value !== null);
    }
} 
