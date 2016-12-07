import collections

from pyalgotrade.broker.backtestTickBroker import *

import matplotlib.pyplot as plt
from matplotlib import ticker
import numpy as np

import pdb

def get_last_value(dataSeries):
    ret = None
    try:
        ret = dataSeries[-1]
    except IndexError:
        pass
    return ret


def _filter_datetimes(dateTimes, fromDate=None, toDate=None):
    class DateTimeFilter(object):
        def __init__(self, fromDate=None, toDate=None):
            self.__fromDate = fromDate
            self.__toDate= toDate

        def includeDateTime(self, dateTime):
            if self.__toDate and dateTime > self.__toDate:
                return False
            if self.__fromDate and dateTime < self.__fromDate:
                return False

            return True

    dateTimeFilter = DateTimeFilter(fromDate, toDate)
    return filter(lambda x: dateTimeFilter.includeDateTime(x), dateTimes)

def _post_plot_fun(subPlot, mplSubplot):
    mplSubplot.legend(subPlot.getAllSeries().keys(),shadow=True, loc="best")
    mplSubplot.yaxis.set_major_formatter(ticker.ScalarFormatter(useOffset=False))

class Series(object):
    def __init__(self):
        self.__values = {}

    def getColor(self):
        return None

    def addValue(self, dateTime, value):
        self.__values[dateTime] = value

    def getValue(self, dateTime):
        return self.__values.get(dateTime, None)

    def getValues(self):
        return self.__values

    def getMarker(self):
        raise NotImplementedError()

    def needColor(self):
        raise NotImplementedError()

    def plot(self, mplSubplot, dateTimes, color):
        values = []
        for dateTime in dateTimes:
            values.append(self.getValue(dateTime))
        #mplSubplot.plot(dateTimes, values, color=color, marker=self.getMarker())
        N = len(dateTimes)
        ind = np.arange(N)
        def format_date(x,pos=None):
            thisind = np.clip(int(x+0.5),0,N-1)
            return dateTimes[thisind].strftime('%Y-%m-%d %H:%M:%S:%f')

        try:
            mplSubplot.plot(ind, values, color=color, marker=self.getMarker())
        except:
            pdb.set_trace()
        mplSubplot.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))

class BuyMarker(Series):
    def getColor(self):
        return 'g'

    def getMarker(self):
        return "^"

    def needColor(self):
        return True
        
class SellMarker(Series):
    def getColor(self):
        return 'r'

    def getMarker(self):
        return "v"

    def needColor(self):
        return True

class CustomMarker(Series):
    def __init__(self):
        super(CustomMarker, self).__init__()
        self.__marker = "o"

    def needColor(self):
        return True

    def setMarker(self, marker):
        self.__marker = marker

    def getMarker(self):
        return self.__marker

class LineMarker(Series):
    def __init__(self):
        super(LineMarker, self).__init__()
        self.__marker = " "
    
    def needColor(self):
        return True

    def setMarker(self, marker):
        self.__marker = marker

    def getMarker(self):
        return self.__marker

class InstrumentMarker(Series):
    def __init__(self):
        super(InstrumentMarker, self).__init__()
        self.__marker = " "

    def needColor(self):
        return True

    def setMarker(self, marker):
        self.__marker = marker

    def getMarker(self):
        return self.__marker

    def getValue(self, dateTime):
        ret = Series.getValue(self, dateTime)
        if ret is not None:
            ret = ret.getLast()

        return ret

class HistogramMarker(Series):
    def needColor(self):
        return True

    def getColorForValue(self, value, default):
        return default

    def plot(self, mplSubplot, dateTimes, color):
        validDateTimes = []
        values = []
        colors = []
        for dateTime in dateTimes:
            value = self.getValue[dateTime]
            if value is not None:
                validDateTimes.append(dateTime)
                values.append(value)
                colors.append(self.getColorForValue(value, color))
        mplSubplot.bar(validDateTimes, values, color=colors)

class MACDMarker(HistogramMarker):
    def getColorForValue(self, value, default):
        ret = default
        if value >= 0:
            ret = 'g'
        else:
            ret = 'r'

        return ret


class Subplot(object):
    colors = ['b', 'c', 'm', 'y', 'k']

    def __init__(self):
        self.__series = {}
        self.__callbacks = {}
        self.__nextColor = 0

    def __getColor(self, series):
        ret = series.getColor()
        if ret is None:
            ret = Subplot.colors[self.__nextColor % len(Subplot.colors)]
            self.__nextColor += 1
        return ret

    def isEmpty(self):
        return len(self.__series) == 0

    def getAllSeries(self):
        return self.__series

    def addDataSeries(self, label, dataSeries, defaultClass=LineMarker):
        ###closure non-local variable: dataSeries
        callback = lambda ticks: get_last_value(dataSeries)
        self.__callbacks[callback] = self.getSeries(label, defaultClass)

    def addCallback(self, label, callback, defaultClass=LineMarker):
        self.__callbacks[callback] = self.getSeries(label, defaultClass)

    def addLine(self, label, level):
        self.addCallback(label, lambda x: level)

    def onTicks(self, ticks):
        dateTime = ticks.getDateTime()
        for cb, series in self.__callbacks.iteritems():
            series.addValue(dateTime, cb(ticks))

    def getSeries(self, name, defaultClass=LineMarker):
        try:
            ret = self.__series[name]
        except KeyError:
            ret = defaultClass()
            self.__series[name] = ret
        return ret

    def getCustomMarksSeries(self, name):
        return self.getSeries(name, CustomMarker)

    def plot(self, mplSubplot, dateTimes, postPlotFun=_post_plot_fun):
        for series in self.__series.values():
            color = None
            if series.needColor():
                color = self.__getColor(series)
            series.plot(mplSubplot, dateTimes, color)

        postPlotFun(self, mplSubplot)


class InstrumentSubplot(Subplot):
    def __init__(self, instrument, plotBuySell):
        super(InstrumentSubplot, self).__init__()
        self.__instrument = instrument
        self.__plotBuySell = plotBuySell
        self.__instrumentSeries = self.getSeries(instrument, InstrumentMarker)

    def onTicks(self, ticks):
        super(InstrumentSubplot, self).onTicks(ticks)
        tick = ticks.getTick(self.__instrument)
        if tick:
            dateTime = ticks.getDateTime()
            self.__instrumentSeries.addValue(dateTime, tick)

    def onOrderEvent(self, broker_, orderEvent):
        order = orderEvent.getOrder()
        if self.__plotBuySell and orderEvent.getEventType() in (OrderEvent.Type.PARTIALLY_FILLED,
                OrderEvent.Type.FILLED) and order.getInstrument() == self.__instrument:
            action = order.getAction()
            execInfo = orderEvent.getEventInfo()
            if action in [Order.Action.BUY, Order.Action.BUY_TO_COVER]:
                self.getSeries("Buy", BuyMarker).addValue(execInfo.getDateTime(),execInfo.getPrice())
            elif action in [Order.Action.SELL, Order.Action.SELL_SHORT]:
                self.getSeries("Sell", SellMarker).addValue(execInfo.getDateTime(),execInfo.getPrice())

class StrategyPlotter(object):
    def __init__(self, strat, plotAllInstruments=True, plotBuySell=True, plotPortfolio=True):
        self.__dateTimes = set()
        self.__plotAllInstruments = plotAllInstruments
        self.__plotBuySell = plotBuySell
        self.__tickSubplots = {}
        self.__namedSubplots = collections.OrderedDict()
        self.__portfolioSubplot = None
        if plotPortfolio:
            self.__portfolioSubplot = Subplot()

        strat.getTicksProcessedEvent().subscribe(self.__onTicksProcessed)
        strat.getBroker().getOrderUpdatedEvent().subscribe(self.__onOrderEvent)

    def __checkCreateInstrumentSubplot(self, instrument):
        if instrument not in self.__tickSubplots:
            self.getInstrumentSubplot(instrument)

    def __onTicksProcessed(self, strat, ticks):
        dateTime = ticks.getDateTime()
        self.__dateTimes.add(dateTime)

        if self.__plotAllInstruments:
            for instrument in ticks.getInstruments():
                self.__checkCreateInstrumentSubplot(instrument)

        for subplot in self.__namedSubplots.values():
            subplot.onTicks(ticks)

        for subplot in self.__tickSubplots.values():
            subplot.onTicks(ticks)

        if self.__portfolioSubplot:
            self.__portfolioSubplot.getSeries("Portfolio").addValue(dateTime, strat.getBroker().getEquity())
            self.__portfolioSubplot.onTicks(ticks)

    def __onOrderEvent(self, broker_, orderEvent):
        for subplot in self.__tickSubplots.values():
            subplot.onOrderEvent(broker_, orderEvent)

    def getInstrumentSubplot(self, instrument):
        try:
            ret = self.__tickSubplots[instrument]
        except KeyError:
            ret = InstrumentSubplot(instrument, self.__plotBuySell)
            self.__tickSubplots[instrument] = ret
        return ret

    def getOrCreateSubplot(self, name):
        try:
            ret = self.__namedSubplots[name]
        except KeyError:
            ret = Subplot()
            self.__namedSubplots[name] = ret
        return ret

    def getPortfolioSubplot(self):
        return self.__portfolioSubplot

    def __buildFigureImpl(self, fromDateTime=None, toDateTime=None, postPlotFun=_post_plot_fun):
        dateTimes = _filter_datetimes(self.__dateTimes, fromDateTime, toDateTime)
        dateTimes.sort()

        subplots = []
        subplots.extend(self.__tickSubplots.values())
        subplots.extend(self.__namedSubplots.values())
        if self.__portfolioSubplot is not None:
            subplots.append(self.__portfolioSubplot)

        fig, axes = plt.subplots(nrows=len(subplots), sharex=True, squeeze=False)
        mplSubplots = []
        for i, subplot in enumerate(subplots):
            axesSubplot = axes[i][0]
            if not subplot.isEmpty():
                mplSubplots.append(axesSubplot)
                subplot.plot(axesSubplot, dateTimes, postPlotFun=postPlotFun)
                axesSubplot.grid(True)
        
        return (fig, mplSubplots)

    def buildFigure(self, fromDateTime=None, toDateTime=None):
        fig, _ = self.buildFigureAndSubplots(fromDateTime, toDateTime)
        return fig

    def buildFigureAndSubplots(self, fromDateTime=None, toDateTime=None, postPlotFun=_post_plot_fun):
        fig, mplSubplots = self.__buildFigureImpl(fromDateTime, toDateTime, postPlotFun=postPlotFun)
        fig.autofmt_xdate()
        return fig, mplSubplots

    def plot(self, fromDateTime=None, toDateTime=None, postPlotFun=_post_plot_fun):
        fig, mplSubplots = self.__buildFigureImpl(fromDateTime, toDateTime, postPlotFun=postPlotFun)
        fig.autofmt_xdate()
        plt.show()
