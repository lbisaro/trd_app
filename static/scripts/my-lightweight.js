// ===============================================================
// CLASE PRINCIPAL LWC
// ===============================================================

function formatTime(time) {
    return (Date.parse(time)/1000) - (3 * 3600);
}

class LWC {
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

    getChart() {
        var addContainer = $('#tv-attr-logo').parent();

        addContainer.prepend('<div id="add-legends" style="position: absolute;z-index: 10; top: 0; left: 0; padding: 0px; border: 0px;background-color: transparent; "></div>');

        addContainer.append('<button id="reset-button" style="' + this.btnStyle + ' right: 30px;" title="Resetear vista"><i class="bi bi-bootstrap-reboot"></i></button>');
        const resetButton = document.getElementById('reset-button');

    
        addContainer.append('<button id="full-button"  style="' + this.btnStyle + '  right: 5px;" title="Ver desde el inicio"><i class="bi bi-arrows-expand-vertical"></i></button>');
        const fullButton = document.getElementById('full-button');
        fullButton.addEventListener('click', () => {
            this.fullView();
        });
        resetButton.addEventListener('click', () => {
            this.minView();
        });

        this.minView();

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

    addPriceSeries(priceData, pane = 0, height = 100, precision = 2, title = '') {
        const priceSeries = this.chart.addSeries(LightweightCharts.LineSeries, {
            priceFormat: {
                type: 'custom',
                formatter: (price) => `${price.toFixed(precision)}`,
            },
            lastValueVisible: true,
            lineWidth: 1,
            title: title,
            color: '#f8b935',
            crosshairMarkerVisible: false,
            priceLineVisible: false,
        }, pane);
        priceSeries.setData(priceData);
        if (pane > 0)
            this.chart.panes()[[pane]].setHeight(height);
        return priceSeries;
    }

    addPnlSeries(pnlData, pane = 0, height = 100, precision = 2) {
        const pnlSeries = this.chart.addSeries(LightweightCharts.BaselineSeries, {
            priceFormat: {
                type: 'custom',
                formatter: (price) => `${price.toFixed(precision)}`,
            },
            baseValue: { type: 'price', price: -0.1 },
            topLineColor: '#0ecb81',
            topFillColor1: 'rgba( 38, 166, 154, 0.28)',
            topFillColor2: 'transparent',
            bottomLineColor: '#f6465d',
            bottomFillColor1: 'transparent',
            bottomFillColor2: 'rgba( 239, 83, 80, 0.28)',
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
        }, pane);
        pnlSeries.setData(pnlData);
        if (pane > 0)
            this.chart.panes()[[pane]].setHeight(height);
        return pnlSeries;
    }

    addTradesSeries(data, pane = 0) {
        const serie = this.chart.addSeries(LightweightCharts.LineSeries, {
            lineWidth: 1,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            color: 'transparent',
        }, pane);
        serie.setData(data);

        var markers = []
        for (let i = 0; i < data.length; i++) {
            if (data[i].side == 0) {
                markers.push({
                    time: data[i].time,
                    position: 'inBar',
                    color: '#0ecb81',
                    shape: 'arrowUp',
                });
            }
            else {
                markers.push({
                    time: data[i].time,
                    position: 'inBar',
                    color: '#f6465d',
                    shape: 'arrowDown',
                });
            }
        }
        return LightweightCharts.createSeriesMarkers(serie, markers);
    }

    addOrdersSeries(data, pane = 0) {
        const color = data[0].side == 0 ? '#0ecb81' : '#f6465d';
        const serie = this.chart.addSeries(LightweightCharts.LineSeries, {
            lineWidth: 1,
            color: color,
            lineStyle: 1, //Solid: 0 | Dotted: 1 | Dashed: 2 | LargeDashed: 3 | SparseDotted: 4
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        }, pane);

        serie.setData(data);
        return serie;
    }
} 
