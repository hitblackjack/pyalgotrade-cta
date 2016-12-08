#coding=utf8
import abc
from pyalgotrade import logger
from pyalgotrade import observer
from pyalgotrade import dispatchprio
from pyalgotrade import dispatcher
from pyalgotrade.stratanalyzer import returns
import pdb
import math
import logging

########PositionTracker####
# Helper class to calculate PnL and returns over a single instrument (not the whole portfolio).
class PositionTrackerLeveled(object):
    def __init__(self, instrumentTraits):
        self.__instrumentTraits = instrumentTraits
        self.reset()

    def reset(self):
        self.__pnl = 0.0
        #self.__avgPrice = 0.0  # Volume weighted average price per share.
        self.__position = 0.0
        self.__commissions = 0.0
        self.__totalCommited= 0.0  # The total amount commited to this position.

        self.__totalMargin = 0.0  # The total amount commited to this position.
        self.__marginRate = None
        self.__cashGetBack = 0.0
        self.__longMarginList = []
        self.__shortMarginList = []

    def getPosition(self):
        return self.__position

    #def getAvgPrice(self):
        #return self.__avgPrice

    def getCommissions(self):
        return self.__commissions

    def getMargin(self):
        return self.__totalMargin

    def getTotalCommitted(self):
        return self.__totalCommited

    def getCashBack(self):
        return self.__cashGetBack

    def getCashOccupied(self):
        return self.__totalCommited - self.__cashGetBack

    def getPnL(self, price=None, includeCommissions=True):
        """
        Return the PnL that would result if closing the position a the given price.
        Note that this will be different if commissions are used when the trade is executed.
        """

        ret = self.__pnl
        #if price:
            #ret += (price - self.__avgPrice) * self.__position
        if self.__longMarginList:
            float_pnl = 0.0
            for openPrice, pos, margin in self.__longMarginList:
                float_pnl += (price - openPrice) * pos
            ret += float_pnl

        if self.__shortMarginList:
            float_pnl = 0.0
            for openPrice, pos, margin in self.__shortMarginList:
                float_pnl += (price - openPrice) * pos * -1
            ret += float_pnl

        if includeCommissions:
            ret -= self.__commissions
        return ret

    def getReturn(self, price=None, includeCommissions=True):
        ret = 0
        pnl = self.getPnL(price=price, includeCommissions=includeCommissions)
        if self.__totalCommited != 0:
            ret = pnl / float(self.__totalCommited)
        return ret

    def __openNewPosition(self, quantity, price):
        #self.__avgPrice = price
        self.__position = quantity
        #self.__totalCommited = self.__avgPrice * abs(self.__position)
        thisMargin = abs(quantity) * price * self.__marginRate
        self.__totalCommited += thisMargin
        self.__totalMargin += thisMargin
        if quantity > 0:
            self.__longMarginList.append([price, quantity, thisMargin])
        elif quantity < 0:
            self.__shortMarginList.append([price, -1*quantity, thisMargin])

    def __extendCurrentPosition(self, quantity, price):
        newPosition = self.__instrumentTraits.roundQuantity(self.__position + quantity)
        #self.__avgPrice = (self.__avgPrice*abs(self.__position) + price*abs(quantity)) / abs(float(newPosition))
        self.__position = newPosition
        #self.__totalCommited = self.__avgPrice * abs(self.__position) 
        thisMargin = abs(quantity) * price * self.__marginRate
        self.__totalCommited += thisMargin
        self.__totalMargin += thisMargin
        if quantity > 0:
            self.__longMarginList.append([price, quantity, thisMargin])
        elif quantity < 0:
            self.__shortMarginList.append([price, -1*quantity, thisMargin])

    def __reduceCurrentPosition(self, quantity, price):
        # Check that we're closing or reducing partially
        #assert self.__instrumentTraits.roundQuantity(abs(self.__position) - abs(quantity)) >= 0
        #pnl = (price - self.__avgPrice) * quantity * -1

        #self.__pnl += pnl
        #self.__position = self.__instrumentTraits.roundQuantity(self.__position + quantity)
        #if self.__position == 0:
            #self.__avgPrice = 0.0

        # 原来是空头，现在多头平仓
        if quantity > 0:
            thisClosedVolume = quantity
            while True:
                # 这里的pos是绝对值
                openPrice, pos, margin = self.__shortMarginList[0]
                if thisClosedVolume <= pos:
                    self.__shortMarginList[0][1] -= thisClosedVolume
                    self.__shortMarginList[0][2] = margin*(1-thisClosedVolume/float(pos))
                    # 空头平仓利润=开仓价格-平仓价格
                    pnl = (openPrice - price) * thisClosedVolume
                    freedMargin = margin*thisClosedVolume/float(pos)
                    self.__pnl += pnl
                    self.__cashGetBack += freedMargin + pnl
                    self.__totalMargin -= freedMargin
                    # 这里position是带有符号的，空头是负的，平仓之后是+pos
                    self.__position += thisClosedVolume
                    break
                elif thisClosedVolume > pos:
                    self.__shortMarginList.pop(0)
                    # 空头平仓利润=开仓价格-平仓价格
                    pnl = (openPrice - price) * pos
                    freedMargin = margin
                    self.__pnl += pnl
                    self.__cashGetBack += freedMargin + pnl
                    self.__totalMargin -= freedMargin
                    # 这里position是带有符号的，空头是负的，平仓之后是+pos
                    self.__position += pos
                    thisClosedVolume -= pos

        # 原来是多头，现在空头平仓
        elif quantity < 0:
            thisClosedVolume = abs(quantity)
            while True:
                openPrice, pos, margin = self.__longMarginList[0]
                if thisClosedVolume <= pos:
                    self.__longMarginList[0][1] -= thisClosedVolume
                    self.__longMarginList[0][2] = margin*(1-thisClosedVolume/float(pos))
                    # 多头平仓利润=平仓价格-开仓价格
                    pnl = (price - openPrice) * thisClosedVolume
                    freedMargin = margin*thisClosedVolume/float(pos)
                    self.__pnl += pnl
                    self.__cashGetBack += freedMargin + pnl
                    self.__totalMargin -= freedMargin
                    # 这里position是带有符号的，多头是正的，平仓之后是-pos
                    self.__position -= thisClosedVolume
                    break
                elif thisClosedVolume > pos:
                    self.__longMarginList.pop(0)
                    # 多头平仓利润=平仓价格-开仓价格
                    pnl = (price - openPrice) * pos
                    freedMargin = margin
                    self.__pnl += pnl
                    self.__cashGetBack += freedMargin + pnl
                    self.__totalMargin -= freedMargin
                    # 这里position是带有符号的，多头是正的，平仓之后是-pos
                    self.__position -= pos
                    thisClosedVolume -= pos
                


    def update(self, quantity, price, commission, marginRate):
        assert quantity != 0, "Invalid quantity"
        assert price > 0, "Invalid price"
        assert commission >= 0, "Invalid commission"
        
        assert marginRate >0. and marginRate <= 1.0
        self.__marginRate = marginRate

        if self.__position == 0:
            self.__openNewPosition(quantity, price)
        else:
            # Are we extending the current position or going in the opposite direction ?
            currPosDirection = math.copysign(1, self.__position)
            tradeDirection = math.copysign(1, quantity)

            if currPosDirection == tradeDirection:
                self.__extendCurrentPosition(quantity, price)
            else:
                # If we're going in the opposite direction we could be:
                # 1: Partially reducing the current position.
                # 2: Completely closing the current position.
                # 3: Completely closing the current position and opening a new one in the opposite direction.
                if abs(quantity) <= abs(self.__position):
                    self.__reduceCurrentPosition(quantity, price)
                else:
                    newPos = self.__position + quantity
                    self.__reduceCurrentPosition(self.__position*-1, price)
                    self.__openNewPosition(newPos, price)

        self.__commissions += commission

    def buy(self, quantity, price, commission=0.0, marginRate=0.2):
        assert quantity > 0, "Invalid quantity"
        self.update(quantity, price, commission, marginRate)

    def sell(self, quantity, price, commission=0.0, marginRate=0.2):
        assert quantity > 0, "Invalid quantity"
        self.update(quantity * -1, price, commission, marginRate)
########PositionTracker####


class Commission(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def calculate(self, order, price, quantity):
        raise NotImplementedError()

    
class NoCommsion(Commission):
    def calculate(self, order, price, quantity):
        return 0

class FixedPerTrade(Commission):
    def __init__(self,amount):
        super(FixedPerTrade, self).__init__()
        self.__amount = amount

    def calculate(self, order, price, quantity):
        return self.__amount

class TradePercentage(Commission):
    def __init__(self, percentage):
        super(TradePercentage, self).__init__()
        assert(percentage < 1)
        self.__percentage = percentage

    def calculate(self, order, price, quantity):
        return price * quantity * self.__percentage

###############Order ###################

class Order(object):
    class Action(object):
        BUY = 1
        BUY_TO_COVER = 2
        SELL = 3
        SELL_SHORT = 4

    class State(object):
        INITIAL = 1  # Initial state.
        SUBMITTED = 2  # Order has been submitted.
        ACCEPTED = 3  # Order has been acknowledged by the broker.
        CANCELED = 4  # Order has been canceled.
        PARTIALLY_FILLED = 5  # Order has been partially filled.
        FILLED = 6  # Order has been completely filled.

        @classmethod
        def toString(cls, state):
            if state == cls.INITIAL:
                return "INITIAL"
            elif state == cls.SUBMITTED:
                return "SUBMITTED"
            elif state == cls.ACCEPTED:
                return "ACCEPTED"
            elif state == cls.CANCELED:
                return "CANCELED"
            elif state == cls.PARTIALLY_FILLED:
                return "PARTIALLY_FILLED"
            elif state == cls.FILLED:
                return "FILLED"
            else:
                raise Exception("Invalid state")

    class Type(object):
        MARKET = 1
        LIMIT = 2
        STOP = 3
        STOP_LIMIT = 4
        NEXT_CUSTOM_TYPE = 1000

    # Valid state transitions.
    VALID_TRANSITIONS = {
        State.INITIAL: [State.SUBMITTED, State.CANCELED],
        State.SUBMITTED: [State.ACCEPTED, State.CANCELED],
        State.ACCEPTED: [State.PARTIALLY_FILLED, State.FILLED, State.CANCELED],
        State.PARTIALLY_FILLED: [State.PARTIALLY_FILLED, State.FILLED, State.CANCELED],
    }

    def __init__(self, type_, action, instrument, quantity, instrumentTraits):
        if quantity is not None and quantity <= 0:
            pdb.set_trace()
            raise Exception("Invalid quantity")

        self.__id = None
        self.__type = type_
        self.__action = action
        self.__instrument = instrument
        self.__quantity = quantity
        self.__instrumentTraits = instrumentTraits
        self.__filled = 0
        self.__avgFillPrice = None
        self.__executionInfo = None
        self.__goodTillCanceled = False
        self.__commissions = 0
        self.__allOrNone = False
        self.__state = Order.State.INITIAL
        self.__submitDateTime = None
        self.__marginRate = None

    def _setQuantity(self, quantity):
        assert self.__quantity is None, "Can only change the quantity if it was undefined"
        assert quantity > 0, "Invalid quantity"
        self.__quantity = quantity

    def getInstrumentTraits(self):
        return self.__instrumentTraits

    def getId(self):
        return self.__id

    def getType(self):
        return self.__type

    def getSubmitDateTime(self):
        """Returns the datetime when the order was submitted."""
        return self.__submitDateTime

    def setSubmitted(self, orderId, dateTime):
        assert(self.__id is None or orderId == self.__id)
        self.__id = orderId
        self.__submitDateTime = dateTime

    def getAction(self):
        return self.__action

    def getState(self):
        return self.__state

    def isActive(self):
        """Returns True if the order is active."""
        return self.__state not in [Order.State.CANCELED, Order.State.FILLED]

    def isInitial(self):
        """Returns True if the order state is Order.State.INITIAL."""
        return self.__state == Order.State.INITIAL

    def isSubmitted(self):
        """Returns True if the order state is Order.State.SUBMITTED."""
        return self.__state == Order.State.SUBMITTED

    def isAccepted(self):
        """Returns True if the order state is Order.State.ACCEPTED."""
        return self.__state == Order.State.ACCEPTED

    def isCanceled(self):
        """Returns True if the order state is Order.State.CANCELED."""
        return self.__state == Order.State.CANCELED

    def isPartiallyFilled(self):
        """Returns True if the order state is Order.State.PARTIALLY_FILLED."""
        return self.__state == Order.State.PARTIALLY_FILLED

    def isFilled(self):
        """Returns True if the order state is Order.State.FILLED."""
        return self.__state == Order.State.FILLED

    def getInstrument(self):
        """Returns the instrument identifier."""
        return self.__instrument

    def getQuantity(self):
        """Returns the quantity."""
        return self.__quantity

    def getFilled(self):
        """Returns the number of shares that have been executed."""
        return self.__filled

    def getRemaining(self):
        """Returns the number of shares still outstanding."""
        return self.__instrumentTraits.roundQuantity(self.__quantity - self.__filled)

    def getAvgFillPrice(self):
        """Returns the average price of the shares that have been executed, or None if nothing has been filled."""
        return self.__avgFillPrice

    def getCommissions(self):
        return self.__commissions

    def getMarginRate(self):
        return self.__marginRate

    def getGoodTillCanceled(self):
        """Returns True if the order is good till canceled."""
        return self.__goodTillCanceled

    def setGoodTillCanceled(self, goodTillCanceled):
        if self.__state != Order.State.INITIAL:
            raise Exception("The order has already been submitted")
        self.__goodTillCanceled = goodTillCanceled

    def getAllOrNone(self):
        """Returns True if the order should be completely filled or else canceled."""
        return self.__allOrNone

    def setAllOrNone(self, allOrNone):
        if self.__state != Order.State.INITIAL:
            raise Exception("The order has already been submitted")
        self.__allOrNone = allOrNone

    def addExecutionInfo(self, orderExecutionInfo):
        if orderExecutionInfo.getQuantity() > self.getRemaining():
            raise Exception("Invalid fill size. %s remaining and %s filled" % \
                    (self.getRemaining(), orderExecutionInfo.getQuantity()))

        if self.__avgFillPrice is None:
            self.__avgFillPrice = orderExecutionInfo.getPrice()
        else:
            self.__avgFillPrice = (self.__avgFillPrice * self.__filled + \
                    orderExecutionInfo.getPrice() * orderExecutionInfo.getQuantity()) \
                    / float(self.__filled + orderExecutionInfo.getQuantity())

        self.__executionInfo = orderExecutionInfo
        self.__filled = self.getInstrumentTraits()\
                .roundQuantity(self.__filled + orderExecutionInfo.getQuantity())
        self.__commissions += orderExecutionInfo.getCommission()
        self.__marginRate = orderExecutionInfo.getMarginRate()

        if self.getRemaining() == 0:
            self.switchState(Order.State.FILLED)
        else:
            assert(not self.__allOrNone)
            self.switchState(Order.State.PARTIALLY_FILLED)

    def switchState(self, newState):
        validTransitions = Order.VALID_TRANSITIONS.get(self.__state, [])
        if newState not in validTransitions:
            raise Exception("Invalid order state transition from %s to %s" % \
                    (Order.State.toString(self.__state), Order.State.toString(newState)))
        else:
            self.__state = newState

    def setState(self, newState):
        self.__state = newState

    def getExecutionInfo(self):
        return self.__executionInfo

    # Returns True if this is a BUY or BUY_TO_COVER order.
    def isBuy(self):
        return self.__action in [Order.Action.BUY, Order.Action.BUY_TO_COVER]

    # Returns True if this is a SELL or SELL_SHORT order.
    def isSell(self):
        return self.__action in [Order.Action.SELL, Order.Action.SELL_SHORT]


class OrderExecutionInfo(object):
    """Execution information for an order."""
    def __init__(self, price, quantity, commission, marginRate, dateTime):
        self.__price = price
        self.__quantity = quantity
        self.__commission = commission
        self.__dateTime = dateTime
        self.__marginRate = marginRate

    def __str__(self):
        return "%s - Price: %s - Amount: %s - Fee: %s" % \
                (self.__dateTime, self.__price, self.__quantity, self.__commission)

    def getPrice(self):
        """Returns the fill price."""
        return self.__price

    def getQuantity(self):
        """Returns the quantity."""
        return self.__quantity

    def getCommission(self):
        """Returns the commission applied."""
        return self.__commission

    def getMarginRate(self):
        return self.__marginRate

    def getDateTime(self):
        """Returns the :class:`datatime.datetime` when the order was executed."""
        return self.__dateTime


class OrderEvent(object):
    class Type:
        SUBMITTED = 1  # Order has been submitted.
        ACCEPTED = 2  # Order has been acknowledged by the broker.
        CANCELED = 3  # Order has been canceled.
        PARTIALLY_FILLED = 4  # Order has been partially filled.
        FILLED = 5  # Order has been completely filled.

    def __init__(self, order, eventyType, eventInfo):
        self.__order = order
        self.__eventType = eventyType
        self.__eventInfo = eventInfo

    def getOrder(self):
        return self.__order

    def getEventType(self):
        return self.__eventType

    # This depends on the event type:
    # ACCEPTED: None
    # CANCELED: A string with the reason why it was canceled.
    # PARTIALLY_FILLED: An OrderExecutionInfo instance.
    # FILLED: An OrderExecutionInfo instance.
    def getEventInfo(self):
        return self.__eventInfo

class BaseMarketTickOrder(Order):
    def __init__(self, action, instrument, quantity, instrumentTraits):
        super(BaseMarketTickOrder, self).__init__(Order.Type.MARKET, 
                action, instrument, quantity, instrumentTraits)

class BaseLimitTickOrder(Order):
    def __init__(self, action, instrument, limitPrice, quantity, instrumentTraits):
        super(BaseLimitTickOrder, self).__init__(Order.Type.LIMIT, 
                action, instrument, quantity, instrumentTraits)
        self.__limitPrice = limitPrice

    def getLimitPrice(self):
        return self.__limitPrice

class BaseStopTickOrder(Order):
    def __init__(self, action, instrument, stopPrice, quantity, instrumentTraits):
        super(BaseStopTickOrder, self).__init__(Order.Type.STOP,
                action,instrument, quantity, instrumentTraits)
        self.__stopPrice = stopPrice

    def getStopPrice(self):
        return self.__stopPrice

class BaseStopLimitTickOrder(Order):
    def __init__(self, action, instrument, stopPrice, limitPrice, quantity, instrumentTraits):
        super(BaseStopLimitTickOrder, self).__init__(Order.Type.STOP_LIMIT,
                action, instrument, quantity, instrumentTraits)
        self.__stopPrice = stopPrice 
        self.__limitPrice = limitPrice

    def getStopPrice(self):
        return self.__stopPrice

    def getLimitPrice(self):
        return self.__limitPrice

###

class BacktestingTickOrder(object):
    def __init__(self, *args, **kwargs):
        self.__accepted = None

    def setAcceptedDateTime(self, dateTime):
        self.__accepted = dateTime

    def getAcceptedDateTime(self):
        return self.__accepted

    def process(self, tickBroker, tick):
        raise NotImplementedError()

class MarketTickOrder(BaseMarketTickOrder, BacktestingTickOrder):
    def __init__(self, action, instrument, quantity, instrumentTraits):
        super(MarketTickOrder, self).__init__(action, instrument, quantity, instrumentTraits)

    def process(self, tickBroker, tick):
        return tickBroker.getFillStrategy().fillMarketOrder(tickBroker, self, tick)

class LimitTickOrder(BaseLimitTickOrder, BacktestingTickOrder):
    def __init__(self, action, instrument, limitPrice, quantity, instrumentTraits):
        super(LimitTickOrder, self).__init__(action, instrument, limitPrice, quantity, instrumentTraits)

    def process(self, tickBroker, tick):
        return tickBroker.getFillStrategy().fillLimitOrder(tickBroker, self, tick)

class StopTickOrder(BaseStopTickOrder, BacktestingTickOrder):
    def __init__(self, action, instrument, stopPrice, quantity, instrumentTraits):
        super(StopTickOrder, self).__init__(action,instrument, stopPrice, quantity, instrumentTraits)

    def process(self, tickBroker, tick):
        return tickBroker.getFillStrategy().fillStopOrder(tickBroker, self, tick)

    def setStopHit(self, stopHit):
        self.__stopHit = stopHit

    def getStopHit(self):
        return self.__stopHit

class StopLimitTickOrder(BaseStopLimitTickOrder, BacktestingTickOrder):
    def __init__(self, action, instrument, stopPrice, limitPrice, quantity, instrumentTraits):
        super(StopLimitTickOrder, self).__init__(action, instrument,
                stopPrice, limitPrice, quantity, instrumentTraits)

    def setStopHit(self, stopHit):
        self.__stopHit = stopHit

    def getStopHit(self):
        return self.__stopHit

    def isLimitOrderActive(self):
        return self.__stopHit

    def process(self, tickBroker, tick):
        return tickBroker.getFillStrategy().fillStopLimitOrder(tickBroker, self, tick)


################FillStrategy#####
class TickFillInfo(object):
    def __init__(self, price, quantity):
        self.__price = price
        self.__quantity = quantity

    def getPrice(self):
        return self.__price
    
    def getQuantity(self):
        return self.__quantity


class TickFillStrategy(object):
    __metaclass__ = abc.ABCMeta
    def onTicks(self, broker, ticks):
        pass

    def onOrderFilled(self, broker, order):
        pass

    @abc.abstractmethod
    def fillMarketOrder(self, broker, order, tick):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def fillLimitOrder(self, broker, order, tick):
        raise NotImplementedError()

    @abc.abstractmethod
    def fillStopOrder(self, broker, order, tick):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def fillStopLimitOrder(self, broker, order ,tick):
        raise NotImplementedError()

class DefaultTickFillStrategy(TickFillStrategy):
    def __init__(self, volumeLimit=0.25):
        super(DefaultTickFillStrategy, self).__init__()
        self.__volumeLeft = {}
        self.__volumeUsed = {}
        self.setVolumeLimit(volumeLimit)

    def onTicks(self, broker, ticks):
        volumeLeft = {}
        for instrument in ticks.getInstruments():
            tick = ticks[instrument]
            volumeLeft[instrument] = tick.getVolume() * self.__volumeLimit
            self.__volumeUsed[instrument] = 0.0
        self.__volumeLeft = volumeLeft

    def setVolumeLimit(self, volumeLimit):
        assert(volumeLimit > 0 and volumeLimit <= 1.)
        self.__volumeLimit = volumeLimit

    def getVolumeLeft(self):
        return self.__volumeLeft

    def getVolumeUsed(self):
        return self.__volumeUsed

    def onOrderFilled(self, broker, order):
        volumeLeft = order.getInstrumentTraits().roundQuantity(self.__volumeLeft[order.getInstrument()])
        fillQuantity = order.getExecutionInfo().getQuantity()
        assert volumeLeft >= fillQuantity, \
                "Invalid fill quantity %s. Not enough volume left %s" %\
                (fillQuantity, volumeLeft)

        self.__volumeLeft[order.getInstrument()] = order.getInstrumentTraits().roundQuantity(
                volumeLeft - fillQuantity)
        
        self.__volumeUsed[order.getInstrument()] = order.getInstrumentTraits().roundQuantity(
                self.__volumeUsed[order.getInstrument()] + order.getExecutionInfo().getQuantity())

    def __calculateFillSize(self, broker, order, tick):
        ret = 0

        maxVolume = self.__volumeLeft.get(order.getInstrument(),0)
        maxVolume = order.getInstrumentTraits().roundQuantity(maxVolume)

        if not order.getAllOrNone():
            ret = min(maxVolume, order.getRemaining())
        elif order.getRemaining() <= maxVolume:
            ret = order.getRemaining()

        return ret

    def fillMarketOrder(self, broker, order, tick):
        fillSize = self.__calculateFillSize(broker, order, tick)
        if fillSize == 0:
            broker.getLogger().debug(
                    "Not enough volume to fill %s market order [%s] for %s share/s" % (
                        order.getInstrument(),
                        order.getId(),
                        order.getRemaining()))
            return None

        if order.isSell():
            price = tick.getBid()
        else:
            price = tick.getAsk()

        return TickFillInfo(price, fillSize)

    def fillLimitOrder(self, broker, order, tick):
        fillSize = self.__calculateFillSize(broker, order, tick)
        if fillSize == 0:
            broker.getLogger().debug(
                    "Not enough volume to fill %s market order [%s] for %s share/s" % (
                        order.getInstrument(),
                        order.getId(),
                        order.getRemaining()))
            return None

        ret = None
        limitPriceTrigger = self.get_limit_price_trigger(
                order.getAction(),
                order.getLimitPrice(),
                tick)
        if limitPriceTrigger is not None:
            ret = TickFillInfo(limitPriceTrigger, fillSize)

        return ret

            
            

    def fillStopOrder(self, broker, order, tick):
        ret = None
        
        stopPriceTrigger = None
        if not order.getStopHit():
            stopPriceTrigger = self.get_stop_price_trigger(
                    order.getAction(),
                    order.getStopPrice(),
                    tick)
            order.setStopHit(stopPriceTrigger is not None)

        if order.getStopHit():
            fillSize = self.__calculateFillSize(broker, order, tick)
            if fillSize == 0:
                broker.getLogger().debug(
                        "Not enough volume to fill %s market order [%s] for %s share/s" % (
                            order.getInstrument(),
                            order.getId(),
                            order.getRemaining()))
                return None

            ret = TickFillInfo(stopPriceTrigger, fillSize)

        return ret


    def fillStopLimitOrder(self, broker, order, tick):
        ret = None

        stopPriceTrigger = None
        if not order.getStopHit():
            stopPriceTrigger = self.get_stop_price_trigger(
                    order.getAction(),
                    order.getStopPrice(),
                    tick)
            order.setStopHit(stopPriceTrigger is not None)

        if order.getStopHit():
            fillSize = self.__calculateFillSize(broker, order, tick)
            if fillSize == 0:
                broker.getLogger().debug(
                        "Not enough volume to fill %s market order [%s] for %s share/s" % (
                            order.getInstrument(),
                            order.getId(),
                            order.getRemaining()))
                return None

            limitPriceTrigger = self.get_limit_price_trigger(
                    order.getAction(),
                    order.getLimitPrice(),
                    tick)
            if limitPriceTrigger is not None:
                ret = TickFillInfo(limitPriceTrigger, fillSize)
        return ret


    def get_stop_price_trigger(self, action, stopPrice, tick):
        if action in (Order.Action.BUY, Order.Action.BUY_TO_COVER) and stopPrice <= tick.getBid():
            return tick.getBid() 
        if action in (Order.Action.SELL, Order.Action.SELL_SHORT) and stopPrice >= tick.getAsk():
            return tick.getAsk()

        return None

    def get_limit_price_trigger(self, action, limitPrice, tick):
        if action in (Order.Action.BUY, Order.Action.BUY_TO_COVER) and limitPrice >= tick.getLast():
            return tick.getLast()

        if action in (Order.Action.SELL, Order.Action.SELL_SHORT) and limitPrice <= tick.getLast():
            return tick.getLast()

        return None
        
#################Position##############
class PositionState2(object):
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

        
class WaitingEntryState2(PositionState2):
    def canSubmitOrder(self, position, order):
        if position.entryActive():
            raise Exception("The entry order is still active")

    def onOrderEvent(self, position, orderEvent):
        assert(position.getEntryOrder().getId() == orderEvent.getOrder().getId())

        if orderEvent.getEventType() in (OrderEvent.Type.FILLED, OrderEvent.Type.PARTIALLY_FILLED):
            position.switchState(OpenState2())
        elif orderEvent.getEventType() == orderEvent.Type.CANCELED:
            assert(position.getEntryOrder().getFilled() == 0)
            position.switchState(ClosedState2())

    def isOpen(self, position):
        return True

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        assert(position.getShares() == 0)
        try:
            assert(position.getEntryOrder().isActive())
        except:
            pdb.set_trace()
        position.getBroker().cancelOrder(position.getEntryOrder())

class OpenState2(PositionState2):
    def onEnter(self, position):
        entryDateTime = position.getEntryOrder().getExecutionInfo().getDateTime()
        position.setEntryDateTime(entryDateTime)

    def canSubmitOrder(self, position, order):
        pass

    def onOrderEvent(self, position, orderEvent):
        if position.getExitOrder() and position.getExitOrder().getId() == orderEvent.getOrder().getId():
            if orderEvent.getEventType() == OrderEvent.Type.FILLED:
                if position.getShares() == 0:
                    position.switchState(ClosedState2())
            elif orderEvent.getEventType() == OrderEvent.Type.CANCELED:
                assert(position.getShares() != 0)
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
            position.getBroker().cancelOrder(position.getEntryOrder())

        position._submitExitOrder(stopPrice, limitPrice, goodTillCanceled)


class ClosedState2(PositionState2):
    def onEnter(self, position):
        if position.exitFilled():
            exitDateTime = position.getExitOrder().getExecutionInfo().getDateTime()
            position.setExitDateTime(exitDateTime)

        assert(position.getShares() == 0)
        position.getBroker().unregisterPosition(position)

    def canSubmitOrder(self, position, order):
        raise Exception("The position is closed")

    def onOrderEvent(self, position, orderEvent):
        raise Exception("Invalid order event '%s' in ClosedState" % (orderEvent.getEventType()))

    def isOpen(self, position):
        return False

    def exit(self, position, stopPrice=None, limitPrice=None, goodTillCanceled=None):
        pass


class Position2(object):
    def __init__(self, broker, entryOrder, goodTillCanceled, allOrNone):
        assert(entryOrder.isInitial())

        self.__state = None
        self.__activeOrders = {}
        self.__shares = 0
        self.__broker = broker
        self.__entryOrder = None
        self.__entryDateTime = None
        self.__exitOrder = None
        self.__exitDateTime = None
        #self.__posTracker = returns.PositionTracker(entryOrder.getInstrumentTraits())
        self.__posTracker = PositionTrackerLeveled(entryOrder.getInstrumentTraits())
        self.__allOrNone = allOrNone

        self.switchState(WaitingEntryState2())
        
        entryOrder.setGoodTillCanceled(goodTillCanceled)
        entryOrder.setAllOrNone(allOrNone)
        self.__submitAndRegisterOrder(entryOrder)
        self.__entryOrder = entryOrder

    def __submitAndRegisterOrder(self, order):
        self.__state.canSubmitOrder(self, order)

        self.getBroker().submitOrder(order)

        self.__activeOrders[order.getId()] = order
        self.__broker.registerPositionOrder(self, order)

    def setEntryDateTime(self, dateTime):
        self.__entryDateTime = dateTime

    def setExitDateTime(self, dateTime):
        self.__exitDateTime = dateTime

    def switchState(self, newState):
        self.__state = newState
        self.__state.onEnter(self)

    def getBroker(self):
        return self.__broker

    def getLastPrice(self):
        return self.__broker.getLastPrice(self.getInstrument())

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

    def getTotalMargin(self):
        return self.__posTracker.getMargin()

    def getCashBack(self):
        return self.__posTracker.getCashBack()

    def getCashOccupied(self):
        return self.__posTracker.getCashOccupied()

    def cancelEntry(self):
        if self.entryActive():
            self.getBroker().cancelOrder(self.getEntryOrder())

    def cancelExit(self):
        if self.exitActive():
            self.getBroker().cancelOrder(self.getExitOrder())

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
                self.__posTracker.buy(execInfo.getQuantity(), execInfo.getPrice(),
                        execInfo.getCommission(), execInfo.getMarginRate())
            else:
                self.__posTracker.sell(execInfo.getQuantity(), execInfo.getPrice(),
                        execInfo.getCommission(), execInfo.getMarginRate())
       
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
                last = self.__broker.getCurrentDateTime()
            ret = last - self.__entryDateTime
        return ret

class LongPosition2(Position2):
    def __init__(self, broker, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone):
        if limitPrice is None and stopPrice is None:
            entryOrder = broker.createMarketOrder(Order.Action.BUY, instrument, quantity)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = broker.createLimitOrder(Order.Action.BUY, instrument, limitPrice, 
                    quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = broker.createStopOrder(Order.Action.BUY, instrument, stopPrice,
                    quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = broker.createStopLimitOrder(Order.Action.BUY, instrument,
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        super(LongPosition2, self).__init__(broker, entryOrder, goodTillCanceled, allOrNone)

    def buildExitOrder(self, stopPrice, limitPrice):
        quantity = self.getShares()
        assert(quantity > 0)
        if limitPrice is None and stopPrice is None:
            ret = self.getBroker().createMarketOrder(Order.Action.SELL, self.getInstrument(),
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getBroker().createLimitOrder(Order.Action.SELL, self.getInstrument(),
                    limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getBroker().createStopOrder(Order.Action.SELL, self.getInstrument(), 
                    stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getBroker().createStopLimitOrder(Order.Action.SELL, self.getInstrument(),
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret


class ShortPosition2(Position2):
    def __init__(self, broker, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone):
        if limitPrice is None and stopPrice is None:
            entryOrder = broker.createMarketOrder(Order.Action.SELL_SHORT, instrument, 
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = broker.createLimitOrder(Order.Action.SELL_SHORT, instrument, limitPrice, 
                    quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = broker.createStopOrder(Order.Action.SELL_SHORT, instrument, stopPrice,
                    quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = broker.createStopLimitOrder(Order.Action.SELL_SHORT, instrument,
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        super(ShortPosition2, self).__init__(broker, entryOrder, goodTillCanceled, allOrNone)

    def buildExitOrder(self, stopPrice, limitPrice):
        quantity = self.getShares() * -1
        assert(quantity > 0)
        if limitPrice is None and stopPrice is None:
            ret = self.getBroker().createMarketOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    quantity)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getBroker().createLimitOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getBroker().createStopOrder(Order.Action.BUY_TO_COVER, self.getInstrument(), 
                    stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getBroker().createStopLimitOrder(Order.Action.BUY_TO_COVER, self.getInstrument(),
                    stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret

###############Broker#####
class InstrumentTraits(object):
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def roundQuantity(self, quantity):
        raise NotImplementedError()

class IntegerTraits(InstrumentTraits):
    def roundQuantity(self, quantity):
        return int(quantity)

class Broker(observer.Subject):
    __metaclass__ = abc.ABCMeta
    
    def __init__(self):
        super(Broker, self).__init__()
        self.__orderEvent = observer.Event()

    def getDispatchPriority(self):
        return dispatchprio.BROKER

    def notifyOrderEvent(self, orderEvent):
        self.__orderEvent.emit(self, orderEvent)

    def getOrderUpdatedEvent(self):
        return self.__orderEvent

    @abc.abstractmethod
    def getInstrumentTraits(self, instrument):
        raise NotImplementedError()

    @abc.abstractmethod
    def getCash(self, includeShort=True):
        raise NotImplementedError()

    @abc.abstractmethod
    def getShares(self, instrument):
        raise NotImplementedError()

    @abc.abstractmethod
    def getPositions(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def getActiveOrders(self, instrument=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def submitOrder(self, order):
        raise NotImplementedError()

    @abc.abstractmethod
    def createMarketOrder(self, action, instrument, quantity):
        raise NotImplementedError()

    @abc.abstractmethod
    def createLimitOrder(self, action, instrument, limitPrice, quantity):
        raise NotImplementedError()

    @abc.abstractmethod
    def createStopOrder(self, action, instrument, stopPrice, quantity):
        raise NotImplementedError()

    @abc.abstractmethod
    def createStopLimitOrder(self, action, instrument, stopPrice, limitPrice, quantity):
        raise NotImplementedError()

    @abc.abstractmethod
    def cancelOrder(self, order):
        raise NotImplementedError()





######Broker########
class TickBroker(Broker):
    LOGGER_NAME = "broker.backtestTick"

    def __init__(self, cash, tickFeed):
        super(TickBroker, self).__init__()

        assert(cash >=0)
        self.__initialCash = cash

        self.__shares = {}
        self.__activeOrders = {}
        self.__tickFillStrategy = DefaultTickFillStrategy()
        self.__logger = logger.getLogger(TickBroker.LOGGER_NAME) 
        tickFeed.getNewValuesEvent().subscribe(self.onTicks)
        self.__tickFeed = tickFeed
        self.__allowNegativeCash = False
        self.__nextOrderId = 1
        
        self.__marginRateDict = {}
        self.__commissionDict = {}

        self.__activePositions = set()
        self.__closedPositions = set()
        self.__orderToPosition = {}
        self.getOrderUpdatedEvent().subscribe(self.__onOrderEvent)

        #self.__frozenMargin = {}
        self.__PnL_RL = {}
        self.__PnL_MM = {}
        self.__pnl = 0.0
        self.__freeCash = self.__initialCash


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

    def getLastPrice(self, instrument):
        ret = None
        tick = self.__tickFeed.getLastTick(instrument)
        if tick is not None:
            ret = tick.getLast()
        return ret

    def getCurrentDateTime(self):
        return self.__tickFeed.getCurrentDateTime()


    def enterLong(self, instrument, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition2(self, instrument, None, None, quantity, goodTillCanceled, allOrNone)

    def enterShort(self, instrument, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition2(self, instrument, None, None, quantity, goodTillCanceled, allOrNone)

    def enterLongLimit(self, instrument, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition2(self, instrument, None, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterShortLimit(self, instrument, limitPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition2(self, instrument, None, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterLongStop(self, instrument, stopPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return LongPosition2(self, instrument, stopPrice, None, quantity, goodTillCanceled, allOrNone)

    def enterShortStop(self, instrument, stopPrice, quantity, goodTillCanceled=False, allOrNone=False):
        return ShortPosition2(self, instrument, stopPrice, None, quantity, goodTillCanceled, allOrNone)

    def enterLongStopLimit(self, instrument, stopPrice, limitPrice, quantity, 
            goodTillCanceled=False, allOrNone=False):
        return LongPosition2(self, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone)

    def enterShortStopLimit(self, instrument, stopPrice, limitPrice, quantity, 
            goodTillCanceled=False, allOrNone=False):
        return ShortPosition2(self, instrument, stopPrice, limitPrice, quantity, goodTillCanceled, allOrNone)

    def getActivePositions(self):
        return self.__activePositions

    def getClosedPositions(self):
        return self.__closedPositions


    def __onOrderEvent(self, broker, orderEvent):
        order = orderEvent.getOrder()

        pos = self.__orderToPosition.get(order.getId(), None)
        if pos is not None:
            if not order.isActive():
                self.unregisterPositionOrder(pos, order)

            pos.onOrderEvent(orderEvent)

############new__above
    def setMarginRate(self, instrument, marginRate):
        self.__marginRateDict[instrument] = marginRate

    def getMarginRate(self, instrument):
        return self.__marginRateDict.get(instrument, 0.1)

    def setCommission(self, instrument, commission):
        self.__commissionDict[instrument] = commission

    def getCommission(self, instrument):
        return self.__commissionDict.get(instrument, NoCommsion())

    def _getNextOrderId(self):
        ret = self.__nextOrderId
        self.__nextOrderId += 1
        return ret
        
    def _getTick(self, ticks, instrument):
        ret = ticks.getTick(instrument)
        if ret is None:
            ret = self.__tickFeed.getLastTick(instrument)
        return ret

    def _registerOrder(self, order):
        assert(order.getId() not in self.__activeOrders)
        assert(order.getId() is not None)
        self.__activeOrders[order.getId()] = order

    def _unregisterOrder(self, order):
        assert(order.getId() in self.__activeOrders)
        assert(order.getId() is not None)
        del self.__activeOrders[order.getId()]

    def getLogger(self):
        return self.__logger

    def setAllowNegativeCash(self, allowNegativeCash):
        self.__allowNegativeCash = allowNegativeCash

    def getCash(self, includeShort=True):
        ret = self.__initialCash
        return ret

    def getFreeCash(self):
        return self.__freeCash

    def setCash(self, cash):
        self.__initialCash = cash

    def setFillStrategy(self, strategy):
        self.__tickFillStrategy = strategy

    def getFillStrategy(self):
        return self.__tickFillStrategy

    def getActiveOrders(self, instrument=None):
        if instrument is None: ret = self.__activeOrders.values()
        else:
            ret = [order for order in self.__activeOrders.values() if order.getInstrument() == instrument]
        return ret

    def _getCurrentDateTime(self):
        return self.__tickFeed.getCurrentDateTime()

    def getInstrumentTraits(self, instrument):
        return IntegerTraits()

    def getShares(self, instrument):
        return self.__shares.get(instrument, 0)

    def getPositions(self):
        return self.__shares

    def getActiveInstruments(self):
        return [instrument for instrument, shares in self.__shares.iteritems() if shares != 0]

    def getTotalMargin(self):
        #ret = 0.
        #for i in self.__frozenMargin.values():
            #ret += i
        #return ret
        return self.__totalMargin


    def __getEquityWithTicks(self, ticks):
        ret = self.getCash()
        #ret += self.getTotalMargin()
        if ticks is not None:
            for instrument, shares in self.__shares.iteritems():
                instrumentPrice = self._getTick(ticks,instrument).getLast()
                ret += instrumentPrice * shares
        return ret

    def getEquity(self):
        #pdb.set_trace()
        #return self.__getEquityWithTicks(self.__tickFeed.getCurrentTicks())
        return self.__initialCash + self.__pnl

    def commitOrderExecution(self, order, dateTime, fillInfo):
        ### Need to consider the margin ...
        price = fillInfo.getPrice()
        quantity = fillInfo.getQuantity()
        marginRate = self.getMarginRate(order.getInstrument())

        if order.isBuy():
            cost = price * quantity * -1 * marginRate
            assert(cost < 0)
            sharesDelta = quantity
            #self.__frozenMargin[order.getInstrument()] = -1*cost
        elif order.isSell():
            cost = price * quantity * marginRate * -1
            assert(cost < 0)
            sharesDelta = quantity * -1
            #self.__frozenMargin[order.getInstrument()] = -1*cost
        else:
            assert(False)

        commission = self.getCommission(order.getInstrument()).calculate(order, price, quantity)
        cost -= commission
#####
        ###getCashOccupied这个里面含有浮动盈亏，所以，不适合放在orderEvent这里
        ###应该放在onTikc里面
        #freeCash = self.__initialCash
        #pnl = 0.0
        #if self.__activePositions:
            #for i in self.__activePositions:
                #freeCash -= i.getCashOccupied()
                #pnl += i.getPnL()
        #if self.__closedPositions:
            #for i in self.__closedPositions:
                #freeCash -= i.getCashOccupied()
                #pnl += i.getPnL()
        
# openNewPosition: 1. newInstrument; 2. oldPosition, extend
# newPosition or extendPosition Order must afford openMargin cost
# closeOldPosition: all or partially close old position
# closeOldPosition never need addtional cost
        #pdb.set_trace()
        ### freeCash + cost >=0 开新仓位，自由现金要大于新开仓成本
        ### 平仓回收保证金，不在乎损益，没办法该平得平。
        if self.__freeCash + cost >=0. or order in [i.getExitOrder() for i in self.__activePositions]: 
            orderExecutionInfo = OrderExecutionInfo(price, quantity, commission, marginRate, dateTime)
            order.addExecutionInfo(orderExecutionInfo)

            updatedShares = order.getInstrumentTraits().roundQuantity(
                    self.getShares(order.getInstrument()) + sharesDelta)
            if updatedShares == 0:
                del self.__shares[order.getInstrument()]
            else:
                self.__shares[order.getInstrument()] = updatedShares

            self.__tickFillStrategy.onOrderFilled(self,order)

            if order.isFilled():
                self._unregisterOrder(order)
                self.notifyOrderEvent(OrderEvent(order, OrderEvent.Type.FILLED, orderExecutionInfo))
            elif order.isPartiallyFilled():
                self.notifyOrderEvent(
                        OrderEvent(order, OrderEvent.Type.PARTIALLY_FILLED, orderExecutionInfo))
            else:
                assert(False)
        else:
            self.__logger.debug("Not enough cash to fill %s order [%s] for %s share/s" % (
                order.getInstrument(),
                order.getId(),
                order.getRemaining()))

    def submitOrder(self, order):
        if order.isInitial():
            order.setSubmitted(self._getNextOrderId(), self._getCurrentDateTime())
            self._registerOrder(order)
            order.switchState(Order.State.SUBMITTED)
            self.notifyOrderEvent(OrderEvent(order, OrderEvent.Type.SUBMITTED, None))
        else:
            raise Exception("The order was already processed")

    def __preProcessOrder(self, order, tick):
        ret = True

        if not order.getGoodTillCanceled():
            ###### night market is belong to the next day's market?           
            expired = tick.getDateTime().date() > order.getAcceptedDateTime().date()
            if expired:
                ret = False
                self._unregisterOrder(order)
                order.switchState(Order.State.CANCELED)
                self.notifyOrderEvent(OrderEvent(order, OrderEvent.Type.CANCELED, "Expired"))

        return ret

    def __postProcessOrder(self, order, tick):
        if not order.getGoodTillCanceled():
            expired = tick.getDateTime().date() > order.getAcceptedDateTime().date()
            if expired:
                ret = False
                self._unregisterOrder(order)
                order.switchState(Order.State.CANCELED)
                self.notifyOrderEvent(OrderEvent(order, OrderEvent.Type.CANCELED, "Expired"))

    def __processOrder(self, order, tick):
        if not self.__preProcessOrder(order, tick):
            return

        fillInfo = order.process(self, tick)
        if fillInfo is not None:
            self.commitOrderExecution(order, tick.getDateTime(), fillInfo)

        if order.isActive():
            self.__postProcessOrder(order, tick)
    
    def __onTicksImpl(self, order, ticks):
        tick = ticks.getTick(order.getInstrument())
        if tick is not None:
            if order.isSubmitted():
                order.setAcceptedDateTime(tick.getDateTime())
                order.switchState(Order.State.ACCEPTED)
                self.notifyOrderEvent(OrderEvent(order,OrderEvent.Type.ACCEPTED,None))

            if order.isActive():
                self.__processOrder(order, tick)
            else:
                assert(order.isCanceled())
                assert(order not in self.__activeOrders)

    def onTicks(self, dateTime, ticks):
        self.__tickFillStrategy.onTicks(self, ticks)
        ordersToProcess = self.__activeOrders.values()

        for order in ordersToProcess:
            self.__onTicksImpl(order, ticks)

        ##实时计算盈亏以及freeCash
        self.__freeCash = self.__initialCash
        self.__pnl = 0.0
        self.__totalMargin = 0.0
        if self.__activePositions:
            for i in self.__activePositions:
                self.__freeCash -= i.getCashOccupied()
                self.__pnl += i.getPnL()
                self.__totalMargin += i.getTotalMargin()
        if self.__closedPositions:
            for i in self.__closedPositions:
                self.__freeCash -= i.getCashOccupied()
                self.__pnl += i.getPnL()

    def start(self):
        super(TickBroker, self).start()

    def stop(self):
        pass

    def join(self):
        pass

    def eof(self):
        return self.__tickFeed.eof()

    def dispatch(self):
        pass

    def peekDateTime(self):
        return None

    def createMarketOrder(self, action, instrument, quantity):
        return MarketTickOrder(action, instrument, quantity, self.getInstrumentTraits(instrument))

    def createLimitOrder(self, action, instrument, limitPrice, quantity):
        return LimitTickOrder(action, instrument, limitPrice, quantity,self.getInstrumentTraits(instrument))

    def createStopOrder(self, action, instrument, stopPrice, quantity):
        return StopTickOrder(action, instrument, stopPrice, quantity, self.getInstrumentTraits(instrument))

    def createStopLimitOrder(self, action, instrument, stopPrice, limitPrice, quantity):
        return StopLimitTickOrder(action, instrument, stopPrice, limitPrice, quantity, self.getInstrumentTraits(instrument))

    def cancelOrder(self, order):
        activeOrder = self.__activeOrders.get(order.getId())
        if activeOrder is None:
            raise Exception("The order is not active anymore")
        if activeOrder.isFilled():
            raise Exception("Can't cancel order that has already been filled")

        self._unregisterOrder(activeOrder)
        activeOrder.switchState(Order.State.CANCELED)
        self.notifyOrderEvent(
                OrderEvent(activeOrder, OrderEvent.Type.CANCELED, "User requested cancellation"))



########Strategy
class BaseLeveledTickStrategy(object):
    __metaclass__ = abc.ABCMeta
    LOGGER_NAME = "leveled tick strategy"
    def __init__(self, tickFeed, broker):
        self.__tickFeed = tickFeed
        self.__broker = broker

        self.__ticksProcessedEvent = observer.Event()
        self.__analyzers = []
        self.__namedAnalyzers = {}
        self.__resampledTickFeeds = []
        self.__dispatcher = dispatcher.Dispatcher()
        self.__tickFeed.getNewValuesEvent().subscribe(self.__onTicks)

        self.__dispatcher.getStartEvent().subscribe(self.onStart)
        self.__dispatcher.getIdleEvent().subscribe(self.__onIdle)

        self.__dispatcher.addSubject(self.__broker)
        self.__dispatcher.addSubject(self.__tickFeed)

        self.__logger = logger.getLogger(BaseLeveledTickStrategy.LOGGER_NAME)

    def _setBroker(self, broker):
        self.__broker = broker

    def setUseEventDateTimeInLogs(self, useEventDateTime):
        if useEventDateTime:
            logger.Formatter.DATETIME_HOOK = self.getDispatcher().getCurrentDateTime
        else:
            logger.Formatter.DATETIME_HOOK = None

    def getLogger(self):
        return self.__logger

    def getDispatcher(self):
        return self.__dispatcher

    def getResult(self):
        return self.__broker.getEquity()

    def getTicksProcessedEvent(self):
        return self.__ticksProcessedEvent

    def __notifyAnalyzers(self, lambdaExpression):
        for s in self.__analyzers:
            lambdaExpression(s)

    def attachAnalyzerEx(self, strategyAnalyzer, name=None):
        if strategyAnalyzer not in self.__analyzers:
            if name is not None:
                if name in self.__namedAnalyzers:
                    raise Exception("A different analyzer named '%s' was already attached" % name)
                self.__namedAnalyzers[name] = strategyAnalyzer

            strategyAnalyzer.beforeAttach(self)
            self.__analyzers.append(strategyAnalyzer)
            strategyAnalyzer.attached(self)

    def getFeed(self):
        return self.__tickFeed
    
    def getBroker(self):
        return self.__broker

    def onEnterOk(self):
        pass

    def onEnterCanceled(self):
        pass

    def onExitOk(self):
        pass

    def onExitCanceled(self):
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
            resampledTickFeed.checkNow(self.__broker.getCurrentDateTime())

        self.onIdle()

    def __onTicks(self, dateTime, ticks):
        self.__notifyAnalyzers(lambda s: s.beforeOnTicks(self, ticks))
        self.onTicks(ticks)
        self.__ticksProcessedEvent.emit(self,ticks)

    def run(self):
        self.__dispatcher.run()

        if self.__tickFeed.getCurrentTicks() is not None:
            self.onFinish(self.__tickFeed.getCurrentTicks())
        else:
            raise Exception("Feed was empty")

    def stop(self):
        self.__dispatcher.stop()

    def attachAnalyzer(self, strategyAnalyzer):
        self.attachAnalyzerEx(strategyAnalyzer)

    def getNamedAnalyzer(self, name):
        return self.__namedAnalyzers.get(name,None)

    def debug(self,msg):
        self.getLogger().debug(msg)

    def info(self,msg):
        self.getLogger().info(msg)

    def warning(self,msg):
        self.getLogger().warning(msg)

    def error(self,msg):
        self.getLogger().error(msg)

    def critical(self,msg):
        self.getLogger().critical(msg)

    def resampledTickFeed(self, frequency, callback):
        pass

class BacktestingLeveledTickStrategy(BaseLeveledTickStrategy):
    def __init__(self, tickFeed, cash_or_brk = 1000000):
        if isinstance(cash_or_brk, TickBroker):
            broker = cash_or_brk
        else:
            broker = TickBroker(cash_or_brk, tickFeed)

        BaseLeveledTickStrategy.__init__(self, tickFeed, broker)
        self.setUseEventDateTimeInLogs(True)
        self.setDebugMode(True)

    def setDebugMode(self, debugOn):
        level = logging.DEBUG if debugOn else logging.INFO
        self.getLogger().setLevel(level)
        self.getBroker().getLogger().setLevel(level)

