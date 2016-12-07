from pyalgotrade.stratanalyzer import returns
from pyalgotrade.broker.backtestTickBroker import *
from pyalgotrade import dispatcher
import logging

import datetime


class PositionState(object):
    def onEnter(self, position):
        pass

    def canSubmitOrder(self, position, order):
        raise NotImplementedError()

    def onOrderEvent(self, position, orderEvent):
        raise NotImplementedError()

    def isOpen(self, position):
        raise NotImplementedError()

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        raise NotImplementedError()

        
class WaitingEntryState(PositionState):
    def canSubmitOrder(self, position, order):
        if position.entryActive():
            raise Exception("The entry order is still active")

    def onOrderEvent(self, position, orderEvent):
        assert(position.getEntryOrder().getId() == orderEvent.getOrder().getId())

        if orderEvent.getEventType() in (OrderEvent.Type.FILLED, OrderEvent.Type.PARTIALLY_FILLED):
            position.switchState(OpenState())
            position.getStrategy().onEnterOk(position)
        elif orderEvent.getEventType() == orderEvent.Type.CANCELED:
            assert(position.getEntryOrder().getFilled() == 0)
            position.switchState(ClosedState())
            position.getStrategy().onEnterCanceled(position)

    def isOpen(self, position):
        return True

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        assert(position.getShares() == 0)
        assert(position.getEntryOrder().isActive())
        position.getStrategy().getBroker().cancelOrder(position.getEntryOrder())

class OpenState(PositionState):
    def onEnter(self, position):
        entryDateTime = position.getEntryOrder().getExecutionInfo().getDateTime()
        position.setEntryDateTime(entryDateTime)

    def canSubmitOrder(self, position, order):
        pass

    def onOrderEvent(self, position, orderEvent):
        if position.getExitOrder() and position.getExitOrder().getId() == orderEvent.getOrder().getId():
            if orderEvent.getEventType() == OrderEvent.Type.FILLED:
                if position.getShares() == 0:
                    position.switchState(ClosedState())
                    position.getStrategy().onExitOk(position)
            elif orderEvent.getEventType() == OrderEvent.Type.CANCELED:
                assert(position.getShares() != 0)
                position.getStrategy().onExitCanceled(position)
##### what about the paritally filled exitOrder?
#### this doesnt change the position state

####how does the inner state:posTracker of the postion change?######


### this time, the orderEvent is for the second fill for the last partially filled order
#### this dosent change the position state
        elif position.getEntryOrder().getId() == orderEvent.getOrder().getId():
            assert(position.getShares() != 0)
        else:
            raise Exception("Invalid order event '%s' in OpenState" % (orderEvent.getEventType()))

    def isOpen(self, position):
        return True

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        assert(position.getShares() != 0)

        if position.exitActive():
            raise Exception("Exit order is active and it should be canceled first")

        if position.entryActive():
            position.getStrategy().getBroker().cancelOrder(position.getEntryOrder())

        position._submitExitOrder(stopPrice, limitPrice, goodTillCanceled)


class ClosedState(PositionState):
    def onEnter(self, position):
        if position.exitFilled():
            exitDateTime = position.getExitOrder().getExecutionInfo().getDateTime()
            position.setExitDateTime(exitDateTime)

        assert(position.getShares() == 0)
        position.getStrategy().unregisterPosition(position)

    def canSubmitOrder(self, position, order):
        raise Exception("The position is closed")

    def onOrderEvent(self, position, orderEvent):
        raise Exception("Invalid order event '%s' in ClosedState" % (orderEvent.getEventType()))

    def isOpen(self, position):
        return False

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        pass


class Position(object):
    def __init__(self, strategy, entryOrder, goodTillCanceled, allOrNone):
        assert(entryOrder.isInitial())

        self.__state = None
        self.__activeOrders = {}
        self.__shares = 0
        self.__strategy = strategy
        self.__entryOrder = None
        self.__entryDateTime = None
        self.__exitOrder = None
        self.__exitDateTime = None
        self.__posTracker = returns.PositionTracker(entryOrder.getInstrumentTraits())
        self.__allOrNone = allOrNone

        self.switchState(WaitingEntryState())
        
        entryOrder.setGoodTillCanceled(goodTillCanceled)
        entryOrder.setAllOrNone(allOrNone)
        self.__submitAndRegisterOrder(entryOrder)
        self.__entryOrder = entryOrder

    def __submitAndRegisterOrder(self, order):
        self.__state.canSubmitOrder(self, order)

        self.getStrategy().getBroker().submitOrder(order)

        self.__activeOrders[order.getId()] = order
        self.getStrategy().registerPositionOrder(self, order)

    def setEntryDateTime(self, dateTime):
        self.__entryDateTime = dateTime

    def setExitDateTime(self, dateTime):
        self.__exitDateTime = dateTime

    def switchState(self, newState):
        self.__state = newState
        self.__state.onEnter(self)

    def getStrategy(self):
        return self.__strategy

    def getLastPrice(self):
        return self.__strategy.getLastPrice(self.getInstrument())

    def getActiveOrders(self):
        return self.__activeOrders.values()

    def getShares(self):
        return self.__shares

    def entryActive(self):
        return self.__entryOrder is not None and self.__entryOrder.isActive()

    def entryFilled(self):
        return self.__entryOrder is not None and self.__entryOrder.isFilled()

    def exitActive(self):
        return self.__exitOrder is not None and self.__exitOrder.isActive()

    def exitFilled(self):
        return self.__exitOrder is not None and self.__exitOrder.isFilled()

    def getEntryOrder(self):
        return self.__entryOrder

    def getExitOrder(self):
        return self.__exitOrder

    def getInstrument(self):
        return self.__entryOrder.getInstrument()

    def getReturn(self, includeCommissions=True):
        ret = 0
        price = self.getLastPrice()
        if price is not None:
            ret = self.__posTracker.getReturn(price, includeCommissions)

        return ret
            
    def getPnL(self, includeCommissions=True):
        ret = 0
        price = self.getLastPrice()
        if price is not None:
            ret = self.__posTracker.getPnL(price, includeCommissions)

        return ret

    def cancelEntry(self):
        if self.entryActive():
            self.getStrategy().getBroker().cancelOrder(self.getEntryOrder())

    def cancelExit(self):
        if self.exitActive():
            self.getStrategy().getBroker().cancelOrder(self.getExitOrder())

    def exitMarket(self, goodTillCanceled=None):
        self.__state.exit(self, None, None, goodTillCanceled)

    def exitLimit(self, limitPrice, goodTillCanceled=None):
        self.__state.exit(self, None, limitPrice, goodTillCanceled)

    def exitStop(self, stopPrice, goodTillCanceled=None):
        self.__state.exit(self, stopPrice,None,goodTillCanceled)

    def exitStopLimit(self, stopPrice, limitPrice, goodTillCanceled=None):
        self.__state.exit(self, stopPrice, limitPrice, goodTillCanceled)

    def _submitExitOrder(self, stopPrice, limitPrice, goodTillCanceled):
        assert(not self.exitActive())
        
        exitOrder = self.buildExitOrder(stopPrice, limitPrice)

        if goodTillCanceled is None:
            goodTillCanceled = self.__entryOrder.getGoodTillCanceled()
        exitOrder.setGoodTillCanceled(goodTillCanceled)

        exitOrder.setAllOrNone(self.__allOrNone)

        self.__submitAndRegisterOrder(exitOrder)
        self.__exitOrder = exitOrder

    def onOrderEvent(self, orderEvent):
        self.__updatePosTracker(orderEvent)

        order = orderEvent.getOrder()
        if not order.isActive():
            del self.__activeOrders[order.getId()]

        if orderEvent.getEventType() in (OrderEvent.Type.PARTIALLY_FILLED, OrderEvent.Type.FILLED):
            execInfo = orderEvent.getEventInfo()
            if order.isBuy():
                self.__shares = order.getInstrumentTraits().roundQuantity(self.__shares + execInfo.getQuantity())
            else:
                self.__shares = order.getInstrumentTraits().roundQuantity(self.__shares - execInfo.getQuantity())
        self.__state.onOrderEvent(self, orderEvent)

    def __updatePosTracker(self, orderEvent):
        if orderEvent.getEventType() in (OrderEvent.Type.PARTIALLY_FILLED, OrderEvent.Type.FILLED):
            order = orderEvent.getOrder()
            execInfo = orderEvent.getEventInfo()
            if order.isBuy():
                self.__posTracker.buy(execInfo.getQuantity(), execInfo.getPrice(), execInfo.getCommission())
            else:
                self.__posTracker.sell(execInfo.getQuantity(), execInfo.getPrice(), execInfo.getCommission())
       
    def buildExitOrder(self, stopPrice, limitPrice):
        raise NotImplementedError()

    def isOpen(self):
        return self.__state.isOpen(self)

    def getAge(self):
        ret = datetime.timedelta()
        if self.__entryDateTime is not None:
            if self.__exitDateTime is not None:
                last = self.__exitDateTime
            else:
                last = self.__strategy.getCurrentDateTime()
            ret = last - self.__entryDateTime
        return ret

class LongPosition(Position):
    def __init__(self, strategy, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone):
        if limitPrice is None and stopPrice is None:
            entryOrder = strategy.getBroker().createMarketOrder(Order.Action.BUY, instrument, quantity)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = strategy.getBroker().createLimitOrder(Order.Action.BUY, instrument, limitPrice, 
                    quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopOrder(Order.Action.BUY, instrument, stopPrice,
                    quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopLimitOrder(Order.Action.BUY, instrument,
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        super(LongPosition, self).__init__(strategy, entryOrder, goodTillCanceled, allOrNone)

    def buildExitOrder(self, stopPrice, limitPrice):
        quantity = self.getShares()
        assert(quantity > 0)
        if limitPrice is None and stopPrice is None:
            ret = self.getStrategy().getBroker().createMarketOrder(Order.Action.SELL, self.getInstrument(),
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getStrategy().getBroker().createLimitOrder(Order.Action.SELL, self.getInstrument(),
                    limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopOrder(Order.Action.SELL, self.getInstrument(), 
                    stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopLimitOrder(Order.Action.SELL, self.getInstrument(),
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret


class ShortPosition(Position):
    def __init__(self, strategy, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone):
        if limitPrice is None and stopPrice is None:
            entryOrder = strategy.getBroker().createMarketOrder(Order.Action.SELL_SHORT, instrument, 
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = strategy.getBroker().createLimitOrder(Order.Action.SELL_SHORT, instrument, limitPrice, 
                    quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopOrder(Order.Action.SELL_SHORT, instrument, stopPrice,
                    quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopLimitOrder(Order.Action.SELL_SHORT, instrument,
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        super(ShortPosition, self).__init__(strategy, entryOrder, goodTillCanceled, allOrNone)

    def buildExitOrder(self, stopPrice, limitPrice):
        quantity = self.getShares() * -1
        assert(quantity > 0)
        if limitPrice is None and stopPrice is None:
            ret = self.getStrategy().getBroker().createMarketOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getStrategy().getBroker().createLimitOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopOrder(Order.Action.BUY_TO_COVER, self.getInstrument(), 
                    stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopLimitOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret

###################Strategy
class BaseTickStrategy(object):
    __metaclass__ = abc.ABCMeta
    LOGGER_NAME = "strategy"
    def __init__(self, tickFeed, broker):
        self.__tickFeed = tickFeed
        self.__broker = broker
        self.__activePositions = set()
        self.__closedPositions = set()
        self.__orderToPosition = {}
        self.__ticksProcessedEvent = observer.Event()
        self.__analyers = []
        self.__namedAnalyzers = {}
        self.__resampledTickFeeds = []
        self.__dispatcher = dispatcher.Dispatcher()
        self.__broker.getOrderUpdatedEvent().subscribe(self.__onOrderEvent)
        self.__tickFeed.getNewValuesEvent().subscribe(self.__onTicks)

        self.__dispatcher.getStartEvent().subscribe(self.onStart)
        self.__dispatcher.getIdleEvent().subscribe(self.__onIdle)

        self.__dispatcher.addSubject(self.__broker)
        self.__dispatcher.addSubject(self.__tickFeed)

        self.__logger = logger.getLogger(BaseTickStrategy.LOGGER_NAME)

    def _setBroker(self, broker):
        self.__broker = broker

    def setUseEventDateTimeInLogs(self, useEventDateTime):
        if useEventDateTime:
            logger.Formatter.DATETIME_HOOK = self.getDispatcher().getCurrentDateTime
        else:
            logger.Formatter.DATETIME_HOOK = None

    def getLogger(self):
        return self.__logger

    def getActivePositions(self):
        return self.__activePositions

    def getClosedPositions(self):
        return self.__closedPositions

    def getOrderToPosition(self):
        return self.__orderToPosition

    def getDispatcher(self):
        return self.__dispatcher

    def getResult(self):
        return self.getBroker().getEquity()

    def getTicksProcessedEvent(self):
        return self.__ticksProcessedEvent

    def registerPositionOrder(self, position, order):
        self.__activePositions.add(position)
        assert(order.isActive())
        self.__orderToPosition[order.getId()] = position

    def unregisterPositionOrder(self, position, order):
        del self.__orderToPosition[order.getId()]

    def unregisterPosition(self, position):
        assert(not position.isOpen())
        self.__activePositions.remove(position)
        self.__closedPositions.add(position)

    def __notifyAnalyzers(self, lambdaExpression):
        for s in self.__analyers:
            lambdaExpression(s)

    def attachAnalyzerEx(self, strategyAnalyzer, name=None):
        if strategyAnalyzer not in self.__analyers:
            if name is not None:
                if name in self.__namedAnalyzers:
                    raise Exception("A different analyzer named '%s' was already attached" % name)
                self.__namedAnalyzers[name] = strategyAnalyzer

            strategyAnalyzer.beforeAttach(self)
            self.__analyers.append(strategyAnalyzer)
            strategyAnalyzer.attached(self)

    def getLastPrice(self, instrument):
        ret = None
        tick = self.getFeed().getLastTick(instrument)
        if tick is not None:
            ret = tick.getLast()
        return ret

    def getFeed(self):
        return self.__tickFeed

    def getBroker(self):
        return self.__broker

    def getCurrentDateTime(self):
        return self.__tickFeed.getCurrentDateTime()

    def marketOrder(self, instrument, quantity, goodTillCanceled=False, allOrNone=False):
        ret = None
        if quantity > 0:
            ret = self.getBroker().createMarketOrder(Order.Action.BUY, instrument, quantity)
        elif quantity < 0:
            ret = self.getBroker().createMarketOrder(Order.Action.SELL, instrument, quantity)
        if ret:
            ret.setGoodTillCanceled(goodTillCanceled)
            ret.setAllOrNone(allOrNone)
            self.getBroker().submitOrder(ret)
        return ret

    def limitOrder(self, instrument, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        ret = None
        if quantity > 0:
            ret = self.getBroker().createLimitOrder(Order.Action.BUY, instrument, limitPrice, quantity)
        elif quantity < 0:
            ret = self.getBroker().createLimitOrder(Order.Action.SELL, instrument, limitPrice, quantity*-1)
        if ret:
            ret.setGoodTillCanceled(goodTillCanceled)
            ret.setAllOrNone(allOrNone)
            self.getBroker().submitOrder(ret)
        return ret

    def stopOrder(self, instrument, stopPrice, quantity, goodTillCanceled=False, allOrNone=False):
        ret = None
        if quantity > 0:
            ret = self.getBroker().createStopOrder(Order.Action.BUY, instrument, stopPrice, quantity)
        elif quantity < 0:
            ret = self.getBroker().createStopOrder(Order.Action.SELL, instrument, stopPrice, quantity*-1)
        if ret:
            ret.setGoodTillCanceled(goodTillCanceled)
            ret.setAllOrNone(allOrNone)
            self.getBroker().submitOrder(ret)
        return ret
        
    def stopLimitOrder(self, instrument, stopPrice, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        ret = None
        if quantity > 0:
            ret = self.getBroker().createStopLimitOrder(Order.Action.BUY, instrument, stopPrice, limitPrice, 
                    quantity)
        elif quantity < 0:
            ret = self.getBroker().createStopLimitOrder(Order.Action.SELL, instrument, stopPrice, limitPrice,
                    quantity*-1)
        if ret:
            ret.setGoodTillCanceled(goodTillCanceled)
            ret.setAllOrNone(allOrNone)
            self.getBroker().submitOrder(ret)
        return ret

    def enterLong(self, instrument, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition(self, instrument, None, None, quantity, goodTillCanceled, allOrNone)

    def enterShort(self, instrument, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition(self, instrument, None, None, quantity, goodTillCanceled, allOrNone)

    def enterLongLimit(self, instrument, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition(self, instrument, None, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterShortLimit(self, instrument, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition(self, instrument, None, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterLongStop(self, instrument, stopPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition(self, instrument, stopPrice, None, quantity, goodTillCanceled, allOrNone)

    def enterShortStop(self, instrument, stopPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition(self, instrument, stopPrice, None, quantity, goodTillCanceled, allOrNone)

    def enterLongStopLimit(self, instrument, stopPrice, limitPrice, quantity, 
            goodTillCanceled=False, allOrNone=False):
        return LongPosition(self, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterShortStopLimit(self, instrument, stopPrice, limitPrice, quantity, 
            goodTillCanceled=False, allOrNone=False):
        return ShortPosition(self, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone)

    def onEnterOk(self, position):
        pass

    def onEnterCanceled(self, position):
        pass

    def onExitOk(self, position):
        pass

    def onExitCanceled(self, position):
        pass

    def onStart(self):
        pass

    def onFinish(self, ticks):
        pass

    def onIdle(self):
        pass

    @abc.abstractmethod
    def onTicks(self, ticks):
        raise NotImplementedError()

    def onOrderUpdated(self, order):
        pass

    def __onIdle(self):
        for resampledTickFeed in self.__resampledTickFeeds:
            resampledTickFeed.checkNow(self.getCurrentDateTime())

        self.onIdle()

    def __onOrderEvent(self, broker, orderEvent):
        order = orderEvent.getOrder()
        self.onOrderUpdated(order)

        pos = self.__orderToPosition.get(order.getId(), None)
        if pos is not None:
            if not order.isActive():
                self.unregisterPositionOrder(pos, order)

            pos.onOrderEvent(orderEvent)

    def __onTicks(self, dateTime, ticks):
        self.__notifyAnalyzers(lambda s: s.beforeOnTicks(self, ticks))
        self.onTicks(ticks)
        self.__ticksProcessedEvent.emit(self, ticks)

    def run(self):
        self.__dispatcher.run()

        if self.__tickFeed.getCurrentTicks() is not None:
            self.onFinish(self.__tickFeed.getCurrentTicks())
        else:
            raise Exception("Feed was empty")

    def stop(self):
        self.__dispatcher.stop()

    def attachAnalyzer(self, strategyAnalyzer):
        self.attachAnalyzerEx(stratanalyzer)

    def getNamedAnalyzer(self, name):
        return self.__namedAnalyzers.get(name, None)

    def debug(self, msg):
        self.getLogger().debug(msg)

    def info(self, msg):
        self.getLogger().info(msg)

    def warning(self, msg):
        self.getLogger().warning(msg)

    def error(self, msg):
        self.getLogger().error(msg)

    def critical(self, msg):
        self.getLogger().critical(msg)

    def resampledTickFeed(self, frequency, callback):
        pass

class BacktestingTickStrategy(BaseTickStrategy):
    def __init__(self, tickFeed, cash_or_brk=100000):
        if isinstance(cash_or_brk, TickBroker):
            broker = cash_or_brk
        else:
            broker = TickBroker(cash_or_brk, tickFeed)

        BaseTickStrategy.__init__(self, tickFeed, broker)
        self.setUseEventDateTimeInLogs(True)
        self.setDebugMode(True)

    def setDebugMode(self, debugOn):
        level = logging.DEBUG if debugOn else logging.INFO
        self.getLogger().setLevel(level)
        self.getBroker().getLogger().setLevel(level)
