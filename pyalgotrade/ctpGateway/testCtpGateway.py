from ctpGateway import CtpGateway
from vtGateway import VtSubscribeReq


def test():
    ctp = CtpGateway('CTP')
    ctp.connect()

    sub1 = VtSubscribeReq()
    sub1.symbol = 'rb1705'
    sub1.exchange = 'SHFE'
    ctp.subscribe(sub1)
    #ctp.close()


    logEvent = ctp.getLogEvent()
    logEvent.subscribe(printLog)
    tickEvent = ctp.getTickEvent()
    tickEvent.subscribe(printTick)


def printTick(tick):
    print tick.date

def printLog(log):
    print log.logContent


if __name__ == '__main__':
    test()
    while True:
        pass
