import unittest
from pyalgotrade.broker.backtestTickBroker import *
from pyalgotrade.feed.csvTickFeed import *
from pyalgotrade.strategy.tickStrategy import *
from pyalgotrade.dataseries import aligned
from pyalgotrade.strategy import plotter
import pdb
import numpy as np

class StatArb(BacktestingLeveledTickStrategy):
    def __init__(self, feed, instrument1, instrument2, cash):
        super(StatArb, self).__init__(feed, cash)
        self.__i1 = instrument1
        self.__i2 = instrument2

        self.__spread = dataseries.SequenceDataSeries()
        self.__riskRate = dataseries.SequenceDataSeries()

    def getSpreadDS(self):
        return self.__spread

    def getPnLDS(self):
        return self.__PnL

    def getRiskRateDS(self):
        return self.__riskRate

    def __getOrderSize(self, ticks):
        freeCash = self.getBroker().getFreeCash()
        price1 = ticks[self.__i1].getLast()
        price2 = ticks[self.__i2].getLast()
        mgn1 = self.getBroker().getMarginRate(self.__i1)
        mgn2 = self.getBroker().getMarginRate(self.__i2)
        size = int(freeCash/(price1*mgn1+price2*mgn2))
        
        return size

    def buySpread(self, ticks):
        amount = self.__getOrderSize(ticks)
        self.getBroker().enterLong(self.__i1, amount)
        self.getBroker().enterShort(self.__i2, amount)

    def sellSpread(self, ticks):
        amount = self.__getOrderSize(ticks)
        self.getBroker().enterShort(self.__i1, amount)
        self.getBroker().enterLong(self.__i2, amount)

    def onTicks(self, ticks):

        if ticks.getTick(self.__i1) and ticks.getTick(self.__i2):
            zScore = ticks.getTick(self.__i1).getLast() -\
                    ticks.getTick(self.__i2).getLast()
            self.__spread.appendWithDateTime(ticks.getDateTime(), zScore)

            if zScore is not None:
                currentPos = abs(self.getBroker().getShares(self.__i1)) +\
                        abs(self.getBroker().getShares(self.__i2))
                if abs(zScore) <=5 and currentPos !=0:
                    for pos in self.getBroker().getActivePositions():
                        pos.exitMarket()
                elif zScore <= -20 and currentPos == 0:
                    self.buySpread(ticks)
                elif zScore >= 20 and currentPos == 0:
                    self.sellSpread(ticks)


        riskRate = self.getBroker().getTotalMargin() / self.getBroker().getEquity()
        self.__riskRate.appendWithDateTime(ticks.getDateTime(), riskRate)


cash = 100000.0
tickFeed = GenericTickFeed()
rangeFilter =  DateTimeRangeFilter(fromDateTime=datetime.datetime(2016,10,25,9,00,00), toDateTime=datetime.datetime(2016,10,25,12,01,01))
#tickFeed.setTickFilter(rangeFilter)
tickFeed.addTicksFromCSV('rb1701','RB1701.SHF.csv')
tickFeed.addTicksFromCSV('rb1705','RB1705.SHF.csv')

strat = StatArb(tickFeed,'rb1701','rb1705',cash)
strat.getBroker().setMarginRate('rb1701',0.10)
strat.getBroker().setMarginRate('rb1705',0.10)
cms = TradePercentage(0.00045)
strat.getBroker().setCommission('rb1701',cms)
strat.getBroker().setCommission('rb1705',cms)

plt = plotter.StrategyPlotter(strat, True, True, True)
plt.getOrCreateSubplot("spread").addDataSeries("spread", strat.getSpreadDS())
plt.getOrCreateSubplot("riskRate").addDataSeries("riskRate=\nmargin/equity", strat.getRiskRateDS())

strat.run()
plt.plot()
