#coding=utf8
import unittest
from pyalgotrade.broker.backtestTickBroker import *
import pdb

class DefaultTraits(InstrumentTraits):
    def roundQuantity(self, quantity):
        return int(quantity)

class PositionTrackerLeveledTestCase(unittest.TestCase):
    def testBuyThenSell(self):
        posTracker = PositionTrackerLeveled(DefaultTraits())
        posTracker.buy(1,100,0.0,0.2)
        margin = 100*0.2
        self.assertEquals(posTracker.getMargin(),margin) #20
        totalCommitted = margin
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = 0.0
        self.assertEquals(posTracker.getPnL(100),pnl)
        ret = 0.0
        self.assertEquals(posTracker.getReturn(100),ret)
        cashOccupied = 100*.2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)
        

        posTracker.buy(2,200,0.0,0.2)
        margin += 200*2*.2
        self.assertEquals(posTracker.getMargin(),margin) #100
        totalCommitted = margin
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = 100
        self.assertEquals(posTracker.getPnL(200),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(200),ret)
        cashOccupied += 200*2*.2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)


        posTracker.buy(3,300,0.0,0.1)
        margin += 300*3*0.1
        self.assertEquals(posTracker.getMargin(),margin) #190
        totalCommitted = margin
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = (300-100) + (300-200)*2
        self.assertEquals(posTracker.getPnL(300),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(300),ret)
        cashOccupied += 300*3*0.1
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)

###################

        posTracker.sell(2,300,0.0,0.9)
        margin -= 100*0.2 + 200*0.2 #190-60=130
        self.assertEquals(posTracker.getMargin(),margin) 
        #totalCommitted
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = (300-100)*1 + (300-200)*2 + (300-300)*3
        self.assertEquals(posTracker.getPnL(300),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(300),ret)
        cashOccupied -= 100*0.2 + 200*0.2 + (300-100) + (300-200)
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)

        posTracker.sell(1,200,0.0,0.9)
        margin -= 200*0.2 #90
        self.assertEquals(posTracker.getMargin(),margin) 
        #totalCommitted
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = (300-100)*1 + (300-200)*1 + (200-200)*1 + (200-300)*3
        self.assertEquals(posTracker.getPnL(200),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(200),ret)
        cashOccupied -= 200*0.2 + (200-200)
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)

        posTracker.sell(2,250,0.0,0.9)
        margin -= 300*0.1*2 #30
        self.assertEquals(posTracker.getMargin(),margin) 
        #totalCommitted
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = (300-100)*1 + (300-200)*1 + (200-200)*1 + (250-300)*3
        self.assertEquals(posTracker.getPnL(250),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(250),ret)
        cashOccupied -= 300*0.1*2 + (250-300)*2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)

        ### open the opposite position
        posTracker.sell(3,500,0.0,0.2)
        margin -= 300*0.1*1 - 500*0.2*2 #30
        self.assertEquals(posTracker.getMargin(),margin) 
        totalCommitted += 500*0.2*2
        self.assertEquals(posTracker.getTotalCommitted(),totalCommitted)
        pnl = (300-100)*1 + (300-200)*1 + (200-200)*1 + (250-300)*2 + (500-300)*1
        self.assertEquals(posTracker.getPnL(500),pnl)
        ret = pnl/totalCommitted
        self.assertEquals(posTracker.getReturn(500),ret)
        cashOccupied -= 300*0.1*1 + (500-300)*1 - 500*0.2*2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)

####
####
    def testSellThenBuy(self):
        posTracker = PositionTrackerLeveled(DefaultTraits())
        posTracker.sell(1,100,0.0,0.2)
        margin = 100*0.2
        self.assertEquals(posTracker.getMargin(),margin) #20
        pnl = 0.0
        self.assertEquals(posTracker.getPnL(100),pnl)
        ret = 0.0
        self.assertEquals(posTracker.getReturn(100),ret)
        cashOccupied = margin
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

        posTracker.sell(2,200,0.0,0.2)
        margin += 200*2*.2
        self.assertEquals(posTracker.getMargin(),margin) #100
        pnl = (100-200)*1 + (200-200)*2
        self.assertEquals(posTracker.getPnL(200),pnl)
        cashOccupied = margin
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

        posTracker.sell(3,300,0.0,0.1)
        margin += 300*3*0.1
        self.assertEquals(posTracker.getMargin(),margin) #190
        pnl = (100-300)*1 + (200-300)*2 + (300-300)*3
        self.assertEquals(posTracker.getPnL(300),pnl)
        cashOccupied = margin
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

###################

        posTracker.buy(2,300,0.0,0.9)
        margin -= 100*0.2 + 200*0.2 #190-60=130
        self.assertEquals(posTracker.getMargin(),margin) 
        pnl = (100-300)*1 + (200-300)*1 + (200-300)*1 + (300-300)*3
        self.assertEquals(posTracker.getPnL(300),pnl)
        cashOccupied -= 100*0.2 + 200*0.2 + (100-300) + (200-300)
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

        posTracker.buy(1,200,0.0,0.9)
        margin -= 200*0.2 #90
        self.assertEquals(posTracker.getMargin(),margin) 
        pnl = (100-300)*1+(200-300)*1 +(200-200)*1 + (300-200)*3
        self.assertEquals(posTracker.getPnL(200),pnl)
        cashOccupied -= 200*0.2 + (200-200)
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

        posTracker.buy(2,250,0.0,0.9)
        margin -= 300*0.1*2 #30
        self.assertEquals(posTracker.getMargin(),margin) 
        pnl = (100-300)*1+(200-300)*1+(200-200)*1 + (300-250)*2 + (300-250)*1
        self.assertEquals(posTracker.getPnL(250),pnl)
        cashOccupied -= 300*0.1*2 + (300 - 250)*2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied) #20

        ### open the opposite position
        posTracker.buy(3,500,0.0,0.2)
        margin -= 300*0.1*1 - 500*0.2*2 #30
        self.assertEquals(posTracker.getMargin(),margin) 
        pnl = (100-300)*1+(200-300)*1+(200-200)*1+(300-250)*2 + (300-500)*1 +(500-500)*2
        self.assertEquals(posTracker.getPnL(500),pnl)
        cashOccupied -= 300*0.1*1 + (300-500)*1 - 500*0.2*2
        self.assertEquals(posTracker.getCashOccupied(),cashOccupied)


if __name__ == '__main__':
    unittest.main()


    '''
PositionTracker
如果不发生买卖，就不估值了吗？当然不是，getPnL传入price，pnl就应该变化
    '''
