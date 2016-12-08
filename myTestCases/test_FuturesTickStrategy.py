#coding=utf8
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
        self.__equity = dataseries.SequenceDataSeries()
        self.__lastCapital = 0.0

    def getSpreadDS(self):
        return self.__spread

    def getEquityDS(self):
        return self.__equity

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
        lstPnL = 0.0
        for pos in self.getBroker().getActivePositions():
            lstPnL += pos.getPnL()

        for pos in self.getBroker().getClosedPositions():
            lstPnL += pos.getPnL()

        if lstPnL != 0:
            self.__lastCapital = lstPnL

        self.__equity.appendWithDateTime(ticks.getDateTime(), self.__lastCapital)


class TicksBuilder(object):
    def __init__(self, instrument1, instrument2):
        self.__instrument1 = instrument1
        self.__instrument1 = instrument2
        self.__nextDateTime = datetime.datetime(2011,1,1)
        self.__delta = datetime.timedelta(milliseconds=1000)

    def getCurrentDateTime(self):
        return self.__nextDateTime

    def advance(self):
        self.__nextDateTime += self.__delta

    #def nextTicks(self, instrument, ask1, asize1, bid1, bsize1, volume, last):
    def nextTicks(self, instrument1, tick1tuple, instrument2, tick2tuple):
        tick_1 = Tick(self.__nextDateTime,*tick1tuple)
        tick_2 = Tick(self.__nextDateTime,*tick2tuple)
        ret = {instrument1: tick_1,instrument2: tick_2}
        self.advance()
        return Ticks(ret)


class TickFeed(BaseTickFeed):
    def __init__(self, instrument1, instrument2):
        BaseTickFeed.__init__(self)
        self.__builder = TicksBuilder(instrument1,instrument2)
        self.__nextTicks = None

    def getCurrentDateTime(self):
        return self.__builder.getCurrentDateTime()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def join(self):
        raise NotImplementedError()

    def eof(self):
        raise NotImplementedError()

    def peekDateTime(self):
        raise NotImplementedError()

    #def dispatchTicks(self, ask1, asize1, bid1, bsize1, volume, last):
    def dispatchTicks(self, instrument1, tick1, instrument2, tick2):
        self.__nextTicks = self.__builder.nextTicks(instrument1, tick1, instrument2, tick2)
        self.dispatch()

    def barsHaveAdjClose(self):
        raise True

    def getNextTicks(self):
        return self.__nextTicks

####
def setToDict(posSet):
    lst = list(posSet)
    ret = {}
    for i in lst:
        ret[i.getInstrument()] = i
    return ret

class TestStrategy(unittest.TestCase):
    def test1(self):
        cash = 100.0
        tickFeed = TickFeed('xxx','yyy')
        strat = StatArb(tickFeed,'xxx','yyy',cash)
        strat.getBroker().setMarginRate('xxx',0.15)
        strat.getBroker().setMarginRate('yyy',0.2)
        #plt = plotter.StrategyPlotter(strat,True,True,True)
        #plt.getOrCreateSubplot("spread").addDataSeries("spread",strat.getSpreadDS())
        #plt.getOrCreateSubplot("capital").addDataSeries("capital",strat.getEquityDS())

        tick1 = (100,1000,100,1000,1000,100)
        tick2 = (125,1000,125,1000,1000,125)
        #pdb.set_trace()
        tickFeed.dispatchTicks('xxx',tick1,'yyy',tick2)
        self.assertEquals(strat._StatArb__spread[-1], -25.0)
        actPos = setToDict(strat.getBroker().getActivePositions())
        self.assertEquals(len(actPos),2)
        self.assertEquals('xxx' in actPos.keys() and 'yyy' in actPos.keys(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isBuy(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isFilled(),False)
        #self.assertEquals(actPos['xxx'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['yyy'].getEntryOrder().isSell(),True)
        self.assertEquals(actPos['yyy'].getEntryOrder().isFilled(),False)
        #self.assertEquals(actPos['yyy'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['xxx'].getShares(),0)
        self.assertEquals(actPos['yyy'].getShares(),0)
        self.assertEquals(strat.getBroker().getTotalMargin(),0.0)
        self.assertEquals(strat.getBroker().getEquity(),100.0)

        tick1 = (200,1000,200,1000,1000,200)
        tick2 = (230,1000,230,1000,1000,230)
        tickFeed.dispatchTicks('xxx',tick1,'yyy',tick2)
        self.assertEquals(strat._StatArb__spread[-1], -30.0)
        actPos = setToDict(strat.getBroker().getActivePositions())
        self.assertEquals(len(actPos),2)
        self.assertEquals('xxx' in actPos.keys() and 'yyy' in actPos.keys(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isBuy(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isFilled(),True)
        #self.assertEquals(actPos['xxx'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['yyy'].getEntryOrder().isSell(),True)
        self.assertEquals(actPos['yyy'].getEntryOrder().isFilled(),True)
        #self.assertEquals(actPos['yyy'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['xxx'].getShares(),int(100/(100*0.15+125*0.2)))#2
        self.assertEquals(actPos['yyy'].getShares(),-int(100/(100*0.15+125*0.2)))#-2
        self.assertEquals(strat.getBroker().getTotalMargin(),200*2*0.15+230*2*0.2)
        self.assertEquals(strat.getBroker().getEquity(),100.0)

        tick1 = (300,1000,300,1000,1000,300)
        tick2 = (302,1000,302,1000,1000,302)
        tickFeed.dispatchTicks('xxx',tick1,'yyy',tick2)
        self.assertEquals(strat._StatArb__spread[-1], -2.0)
        ## 有信号，提交退出订单，下个tick才能市价成交
        actPos = setToDict(strat.getBroker().getActivePositions())
        self.assertEquals(len(actPos),2)
        self.assertEquals('xxx' in actPos.keys() and 'yyy' in actPos.keys(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isBuy(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isFilled(),True)
        self.assertEquals(actPos['xxx'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['yyy'].getEntryOrder().isSell(),True)
        self.assertEquals(actPos['yyy'].getEntryOrder().isFilled(),True)
        self.assertEquals(actPos['yyy'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['xxx'].getShares(),int(100/(100*0.15+125*0.2)))#2
        self.assertEquals(actPos['yyy'].getShares(),-int(100/(100*0.15+125*0.2)))#-2
        self.assertEquals(strat.getBroker().getTotalMargin(),200*2*0.15+230*2*0.2)
        self.assertEquals(strat.getBroker().getEquity(),100.0+(300-200)*2 +(230-302)*2)


        tick1 = (430,1000,430,1000,1000,430)
        tick2 = (400,1000,400,1000,1000,400)
        tickFeed.dispatchTicks('xxx',tick1,'yyy',tick2)
        self.assertEquals(strat._StatArb__spread[-1], 30.0)
        ### 这里很幸运，上个时刻发出结清信号后，现在时刻价差反向扩大是盈利的，要是价差继续通向扩大就惨了
        cldPos = setToDict(strat.getBroker().getClosedPositions())
        self.assertEquals(len(cldPos),2)
        self.assertEquals('xxx' in cldPos.keys() and 'yyy' in cldPos.keys(),True)
        self.assertEquals(cldPos['xxx'].getEntryOrder().isBuy(),True)
        self.assertEquals(cldPos['xxx'].getEntryOrder().isFilled(),True)
        self.assertEquals(cldPos['xxx'].getExitOrder().isFilled(),True)
        self.assertEquals(cldPos['yyy'].getEntryOrder().isSell(),True)
        self.assertEquals(cldPos['yyy'].getEntryOrder().isFilled(),True)
        self.assertEquals(cldPos['yyy'].getExitOrder().isFilled(),True)
        self.assertEquals(cldPos['xxx'].getShares(),0)#2
        self.assertEquals(cldPos['yyy'].getShares(),0)#-2
        self.assertEquals(strat.getBroker().getTotalMargin(),0.0)
        self.assertEquals(strat.getBroker().getEquity(),100.0+(430-200)*2 +(230-400)*2)

        ## 前一组头寸在此处结清之后，紧接着又开一个信号，反向开仓
        actPos = setToDict(strat.getBroker().getActivePositions())
        self.assertEquals(len(actPos),2)
        self.assertEquals('xxx' in actPos.keys() and 'yyy' in actPos.keys(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isSell(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isFilled(),False)
        #self.assertEquals(actPos['xxx'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['yyy'].getEntryOrder().isBuy(),True)
        self.assertEquals(actPos['yyy'].getEntryOrder().isFilled(),False)
        #self.assertEquals(actPos['yyy'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['xxx'].getShares(),0)#2
        self.assertEquals(actPos['yyy'].getShares(),0)#-2


        tick1 = (500,1000,500,1000,1000,500)
        tick2 = (500,1000,500,1000,1000,500)
        tickFeed.dispatchTicks('xxx',tick1,'yyy',tick2)
        self.assertEquals(strat._StatArb__spread[-1], 0.0)
        ## 发出平仓信号，下一个时刻再执行
        actPos = setToDict(strat.getBroker().getActivePositions())
        self.assertEquals(len(actPos),2)
        self.assertEquals('xxx' in actPos.keys() and 'yyy' in actPos.keys(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isSell(),True)
        self.assertEquals(actPos['xxx'].getEntryOrder().isFilled(),True)
        self.assertEquals(actPos['xxx'].getExitOrder().isFilled(),False)
        self.assertEquals(actPos['yyy'].getEntryOrder().isBuy(),True)
        self.assertEquals(actPos['yyy'].getEntryOrder().isFilled(),True)
        self.assertEquals(actPos['yyy'].getExitOrder().isFilled(),False)
        cash_updated = (100.0+(430-200)*2 +(230-400)*2)
        self.assertEquals(actPos['xxx'].getShares(),-int(cash_updated/(430*0.15+400*0.2)))#-1
        self.assertEquals(actPos['yyy'].getShares(),int(cash_updated/(430*0.15+400*0.2)))#1
        self.assertEquals(strat.getBroker().getTotalMargin(),500*0.15+500*0.2)
        self.assertEquals(strat.getBroker().getEquity(),cash_updated)

        #plt.plot()


if __name__ == '__main__':
    unittest.main()
