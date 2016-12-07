#coding=utf8
import datetime
from pyalgotrade.broker.backtestTickBroker import *
from pyalgotrade.feed.csvTickFeed import *
import pdb 
import unittest

class DefaultTraits(InstrumentTraits):
    def roundQuantity(self, quantity):
        return int(quantity)

class TicksBuilder(object):
    def __init__(self, instrument):
        self.__instrument = instrument
        self.__nextDateTime = datetime.datetime(2011,1,1)
        self.__delta = datetime.timedelta(milliseconds=1000)

    def getCurrentDateTime(self):
        return self.__nextDateTime

    def advance(self):
        #self.__nextDateTime = datetime.datetime(self.__nextDateTime.year, self.__nextDateTime.month, self.__nextDateTime.day)
        self.__nextDateTime += self.__delta

    def nextTicks(self, ask1, asize1, bid1, bsize1, volume, last):
        tick_ = Tick(self.__nextDateTime, ask1, asize1, bid1, bsize1, volume, last)
        ret = {self.__instrument: tick_}
        self.advance()
        return Ticks(ret)

    def nextTick(self, ask1, asize1, bid1, bsize1, volume, last):
        return self.nextTicks(ask1, asize1, bid1, bsize1, volume, last)[self.__instrument]

    def nextTuple(self, ask1, asize1, bid1, bsize1, volume, last):
        ret = self.nextTicks(ask1, asize1, bid1, bsize1, volume, last)[self.__instrument]
        return (ret.getDateTime(), ret)


class TickFeed(BaseTickFeed):
    def __init__(self, instrument):
        BaseTickFeed.__init__(self)
        self.__builder = TicksBuilder(instrument)
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

    def dispatchTicks(self, ask1, asize1, bid1, bsize1, volume, last):
        self.__nextTicks = self.__builder.nextTicks(ask1, asize1, bid1, bsize1, volume, last)
        self.dispatch()

    def barsHaveAdjClose(self):
        raise True

    def getNextTicks(self):
        return self.__nextTicks



class TickBrokerTestCase(unittest.TestCase):
    def testEnterLongMarketExitMarket(self):
        cash = 100.0
        tickFeed = TickFeed('xxx')
        broker = TickBroker(cash,tickFeed)
        longPos = broker.enterLong('xxx',1)
        longPos_state = longPos._Position2__state
        self.assertEquals(isinstance(longPos_state, WaitingEntryState2),True)

        tickFeed.dispatchTicks(101,1000,100,900,900,100)
        self.assertEquals(broker.getLastPrice('xxx'),100.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,1))
        self.assertEquals(longPos.isOpen(),True)
        pos_pnl = longPos.getPnL()
        self.assertEquals(pos_pnl,-1.0)
        brk_Equity = broker.getEquity()
        self.assertEquals(brk_Equity,cash-1.0)
        
        tickFeed.dispatchTicks(95,1000,90,900,900,90)
        self.assertEquals(broker.getLastPrice('xxx'),90.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,2))
        self.assertEquals(longPos.entryFilled(),True)
        self.assertEquals(longPos.isOpen(),True)
        pos_pnl = longPos.getPnL()
        self.assertEquals(pos_pnl,-11.0)
        brk_Equity = broker.getEquity()
        self.assertEquals(brk_Equity,cash-11.0)
        

        longPos2 = broker.enterLong('xxx',100)
        tickFeed.dispatchTicks(110,1000,105,900,900,110)
        self.assertEquals(broker.getLastPrice('xxx'),110.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,3))
        self.assertEquals(longPos2.entryFilled(),False)


       
        longPos.exitMarket()
        tickFeed.dispatchTicks(120,1000,115,900,900,115)
        self.assertEquals(longPos.exitFilled(),True)
        self.assertEquals(longPos.getPnL(),115-101)
        self.assertEquals(broker.getEquity(),115-101+100)

    def testEnterShortMarketExitMarket(self):
        cash = 100.0
        tickFeed = TickFeed('xxx')
        broker = TickBroker(cash,tickFeed)
        shortPos = broker.enterShort('xxx',1)
        shortPos_state = shortPos._Position2__state
        self.assertEquals(isinstance(shortPos_state, WaitingEntryState2),True)

        tickFeed.dispatchTicks(101,1000,100,900,900,100)
        self.assertEquals(broker.getLastPrice('xxx'),100.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,1))
        self.assertEquals(shortPos.isOpen(),True)
        pos_pnl = shortPos.getPnL()
        self.assertEquals(pos_pnl,0.0)
        brk_Equity = broker.getEquity()
        self.assertEquals(brk_Equity,cash)
        
        tickFeed.dispatchTicks(95,1000,90,900,900,90)
        self.assertEquals(broker.getLastPrice('xxx'),90.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,2))
        self.assertEquals(shortPos.entryFilled(),True)
        self.assertEquals(shortPos.isOpen(),True)
        pos_pnl = shortPos.getPnL()
        self.assertEquals(pos_pnl,100-90)
        brk_Equity = broker.getEquity()
        self.assertEquals(brk_Equity,cash+100-90)
        

        shortPos2 = broker.enterLong('xxx',100)
        tickFeed.dispatchTicks(110,1000,105,900,900,110)
        self.assertEquals(broker.getLastPrice('xxx'),110.0)
        self.assertEquals(broker.getCurrentDateTime(),datetime.datetime(2011,1,1,0,0,3))
        self.assertEquals(shortPos2.entryFilled(),False)


       
        shortPos.exitMarket()
        tickFeed.dispatchTicks(120,1000,115,900,900,115)
        self.assertEquals(shortPos.exitFilled(),True)
        self.assertEquals(shortPos.getPnL(),100-120)
        self.assertEquals(broker.getEquity(),100-120+100)

    def testMarginRate(self):
        cash = 100.0
        tickFeed = TickFeed('xxx')
        broker = TickBroker(cash,tickFeed)

        broker.setMarginRate('xxx',0.2)
        self.assertEquals(broker.getMarginRate('xxx'),0.2)
        self.assertEquals(broker.getMarginRate('yyy'),0.1)

    def testBrokerPnL(self):
        pass

if __name__ == '__main__':
    unittest.main()
