// UDF JavaScript datafeed adapter — connects Lightweight Charts to our UDF server.
//
// Implements the Lightweight Charts datafeed interface:
// https://tradingview.github.io/lightweight-charts/docs/api/interfaces/IDatafeedChartApi

class UDFDatafeed {
    constructor(baseUrl = "") {
        this._baseUrl = baseUrl;  // e.g. "" for same-origin, or "http://localhost:8088"
    }

    // ─── Lightweight Charts Interface ──────────────────────────

    onReady(callback) {
        fetch(`${this._baseUrl}/config`)
            .then(r => r.json())
            .then(config => {
                setTimeout(() => callback(config), 0);
            })
            .catch(err => {
                console.error("UDF onReady failed:", err);
                setTimeout(() => callback({
                    supported_resolutions: ["1", "5", "15", "60", "240", "1D", "1W", "1M"],
                    exchanges: [{ value: "Binance", name: "Binance", desc: "Binance Spot" }],
                    symbols_types: [{ name: "crypto", value: "crypto" }],
                }), 0);
            });
    }

    searchSymbols(userInput, exchange, symbolType, onResultReadyCallback) {
        fetch(`${this._baseUrl}/search?query=${encodeURIComponent(userInput)}&limit=30`)
            .then(r => r.json())
            .then(results => {
                // Adapt to Lightweight Charts format
                const items = results.map(item => ({
                    symbol: item.symbol,
                    full_name: item.symbol,
                    description: item.description,
                    exchange: item.exchange || "Binance",
                    ticker: item.ticker || item.symbol,
                    type: item.type || "crypto",
                }));
                onResultReadyCallback(items);
            })
            .catch(err => {
                console.error("UDF searchSymbols failed:", err);
                onResultReadyCallback([]);
            });
    }

    resolveSymbol(symbolName, onSymbolResolvedCallback, onResolveErrorCallback) {
        fetch(`${this._baseUrl}/symbols?symbol=${encodeURIComponent(symbolName)}`)
            .then(r => {
                if (!r.ok) throw new Error(`Symbol not found: ${symbolName}`);
                return r.json();
            })
            .then(symbolInfo => {
                onSymbolResolvedCallback({
                    name: symbolInfo.name,
                    ticker: symbolInfo.ticker || symbolInfo.name,
                    description: symbolInfo.description,
                    type: symbolInfo.type || "crypto",
                    session: symbolInfo.session || "24x7",
                    timezone: symbolInfo.timezone || "Etc/UTC",
                    exchange: symbolInfo.exchange || "Binance",
                    listed_exchange: symbolInfo.listed_exchange || "Binance",
                    minmov: symbolInfo.minmov || 1,
                    pricescale: symbolInfo.pricescale || 100,
                    has_intraday: symbolInfo.has_intraday !== false,
                    has_daily: symbolInfo.has_daily !== false,
                    has_weekly_and_monthly: symbolInfo.has_weekly_and_monthly !== false,
                    supported_resolutions: symbolInfo.supported_resolutions || ["1", "5", "15", "60", "240", "1D", "1W", "1M"],
                    intraday_multipliers: symbolInfo.intraday_multipliers || ["1", "5", "15", "60", "240"],
                    volume_precision: symbolInfo.volume_precision || 8,
                    data_status: symbolInfo.data_status || "streaming",
                    format: symbolInfo.format || "price",
                });
            })
            .catch(err => {
                console.error("UDF resolveSymbol failed:", err);
                onResolveErrorCallback(err.message);
            });
    }

    getBars(symbolInfo, resolution, periodParams, onHistoryCallback, onErrorCallback) {
        const { from, to, countBack, firstDataRequest } = periodParams;

        let url = `${this._baseUrl}/history?symbol=${encodeURIComponent(symbolInfo.name)}&resolution=${resolution}&to=${to}`;

        if (countBack && countBack > 0) {
            url += `&countback=${countBack}`;
        } else if (from && from > 0) {
            url += `&from=${from}`;
        } else {
            url += "&countback=300";
        }

        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (data.s === "ok") {
                    const bars = [];
                    for (let i = 0; i < data.t.length; i++) {
                        bars.push({
                            time: data.t[i],
                            open: data.o[i],
                            high: data.h[i],
                            low: data.l[i],
                            close: data.c[i],
                            volume: data.v[i],
                        });
                    }
                    onHistoryCallback(bars, { noData: false, nextTime: data.nextTime });
                } else if (data.s === "no_data") {
                    onHistoryCallback([], { noData: true, nextTime: data.nextTime });
                } else {
                    onErrorCallback(data.errmsg || "Unknown error");
                }
            })
            .catch(err => {
                console.error("UDF getBars failed:", err);
                onErrorCallback(err.message);
            });
    }

    subscribeBars(symbolInfo, resolution, onRealtimeCallback, subscriberUID, onResetCacheNeededCallback) {
        // Real-time updates via polling the /history endpoint
        // In a production setup, this would use SSE or WebSocket
        this._pollBars(symbolInfo, resolution, onRealtimeCallback, subscriberUID);
    }

    unsubscribeBars(subscriberUID) {
        if (this._pollIntervals && this._pollIntervals[subscriberUID]) {
            clearInterval(this._pollIntervals[subscriberUID]);
            delete this._pollIntervals[subscriberUID];
        }
    }

    // ─── Internal: Polling-based real-time ─────────────────────

    _pollBars(symbolInfo, resolution, callback, uid) {
        if (!this._pollIntervals) this._pollIntervals = {};

        // Poll every 5 seconds for latest bar
        this._pollIntervals[uid] = setInterval(() => {
            const now = Math.floor(Date.now() / 1000);
            fetch(`${this._baseUrl}/history?symbol=${encodeURIComponent(symbolInfo.name)}&resolution=${resolution}&countback=1&to=${now}`)
                .then(r => r.json())
                .then(data => {
                    if (data.s === "ok" && data.t.length > 0) {
                        const i = data.t.length - 1;
                        callback({
                            time: data.t[i],
                            open: data.o[i],
                            high: data.h[i],
                            low: data.l[i],
                            close: data.c[i],
                            volume: data.v[i],
                        });
                    }
                })
                .catch(() => { /* silent retry */ });
        }, 5000);
    }

    _pollIntervals = {};
}
