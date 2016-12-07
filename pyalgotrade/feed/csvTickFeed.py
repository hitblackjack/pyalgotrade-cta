#coding=utf8
import pdb
###############
import sys
sys.path.append('/home/lifeng/opensource/pyalgotrade')
from pyalgotrade import observer
from pyalgotrade import dataseries
import datetime
import csv
import abc


#############Tick
class BaseTick(object):
    __metaclass__ = abc.ABCMeta
    def getAsk(self):
        raise NotImplementedError()
    def getAsize(self):
        raise NotImplementedError()
    def getBid(self):
        raise NotImplementedError()
    def getBsize(self):
        raise NotImplementedError()
    def getVolume(self):
        raise NotImplementedError()
    def getLast(self):
        raise NotImplementedError()

class Tick(BaseTick):
    __slots__ =(
            '__dateTime',
            '__ask1',
            '__asize1',
            '__bid1',
            '__bsize1',
            '__volume',
            '__last')
    def __init__(self, dateTime, ask1, asize1, bid1, bsize1, volume, last):
        if ask1 < bid1:
            raise Exception("ask1 < bid on %s" % (dateTime))
        self.__dateTime = dateTime
        self.__ask1 = ask1
        self.__asize1 = asize1
        self.__bid1 = bid1
        self.__bsize1 = bsize1
        self.__volume = volume
        self.__last = last

    def __setstate__(self, state):
        (self.__dateTime,
                self.__ask1,
                self.__asize1,
                self.__bid1,
                self.__bsize1,
                self.__volume,
                self.__last) = state

    def __getstate__(self, state):
        return (self.__dateTime,
                self.__ask1,
                self.__asize1,
                self.__bid1,
                self.__bsize1,
                self.__volume,
                self.__last)

    def getDateTime(self):
        return self.__dateTime

    def getAsk(self):
        return self.__ask1

    def getAsize(self):
        return self.__asize1

    def getBid(self):
        return self.__bid1

    def getBsize(self):
        return self.__bsize1

    def getVolume(self):
        return self.__volume

    def getLast(self):
        return self.__last


class Ticks(object):
    def __init__(self, tickDict):
        if len(tickDict) == 0:
            raise Exception("No ticks supplied")

        # check that tick datetimes are in sync
        firstDateTime = None
        firstInstrument = None
        for instrument, currentTick in tickDict.iteritems():
            if firstDateTime is None:
                firstDateTime = currentTick.getDateTime()
                firstInstrument = instrument
            elif currentTick.getDateTime() != firstDateTime:
                raise Exception("Tick data times are not in sync. %s %s != %s %s" % (
                    instrument,
                    currentTick.getDateTime(),
                    firstInstrument,
                    firstDateTime))
        self.__tickDict = tickDict
        self.__dateTime = firstDateTime

    def __getitem__(self, instrument):
        return self.__tickDict[instrument]

    def __contains__(self, instrument):
        return instrument in self.__tickDict

    def items(self):
        return self.__tickDict.items()

    def keys(self):
        return self.__tickDict.keys()

    def getInstruments(self):
        return self.__tickDict.keys()

    def getDateTime(self):
        return self.__dateTime

    def getTick(self, instrument):
        return self.__tickDict.get(instrument, None)
    

############Parser

class RowParser(object):
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def parseTick(self, csvRowDict):
        raise NotImplementedError()

    @abc.abstractmethod
    def getFieldNames(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def getDelimiter(self):
        raise NotImplementedError()

class TickFilter(object):
    def includeTick(self, tick_):
        raise NotImplementedError()

class DateTimeRangeFilter(TickFilter):
    def __init__(self,fromDateTime=None, toDateTime=None):
        self.__fromDateTime = fromDateTime
        self.__toDateTime = toDateTime

    def includeTick(self, tick_):
        if self.__toDateTime and tick_.getDateTime() > self.__toDateTime:
            return False
        if self.__fromDateTime and tick_.getDateTime() < self.__fromDateTime:
            return False

        return True

class TickRowParser(RowParser):
    def __init__(self, columnNames, dateTimeFormat):
        self.__dateTimeFormat = dateTimeFormat
        # Column names.
        self.__dateTimeColName = columnNames["datetime"]
        self.__ask1ColName = columnNames["ask1"]
        self.__asize1ColName = columnNames["asize1"]
        self.__bid1ColName = columnNames["bid1"]
        self.__bsize1ColName = columnNames["bsize1"]
        self.__volumeColName = columnNames["volume"]
        self.__lastColName = columnNames["last"]
        self.__columnNames = columnNames

    def _parseDate(self, dateString):
        ret = datetime.datetime.strptime(dateString, self.__dateTimeFormat)
        return ret

    def getFieldNames(self):
        # It is expected for the first row to have the field names.
        return None

    def getDelimiter(self):
        return ","

    def parseTick(self, csvRowDict):
        dateTime = self._parseDate(csvRowDict[self.__dateTimeColName])
        ask1 = float(csvRowDict[self.__ask1ColName])
        asize1 = float(csvRowDict[self.__asize1ColName])
        bid1 = float(csvRowDict[self.__bid1ColName])
        bsize1 = float(csvRowDict[self.__bsize1ColName])
        volume = float(csvRowDict[self.__volumeColName])
        last = float(csvRowDict[self.__lastColName])

        return Tick(dateTime, ask1, asize1, bid1, bsize1, volume, last)

##############TickDataSeries

class TickDataSeries(dataseries.SequenceDataSeries):
    def __init__(self, maxLen=None):
        super(TickDataSeries, self).__init__(maxLen)
        self.__ask1DS = dataseries.SequenceDataSeries(maxLen)
        self.__asize1DS = dataseries.SequenceDataSeries(maxLen)
        self.__bid1DS = dataseries.SequenceDataSeries(maxLen)
        self.__bsize1DS = dataseries.SequenceDataSeries(maxLen)
        self.__volumeDS = dataseries.SequenceDataSeries(maxLen)
        self.__lastDS = dataseries.SequenceDataSeries(maxLen)

    def append(self, tick):
        self.appendWithDateTime(tick.getDateTime(),tick)

    def appendWithDateTime(self, dateTime, tick):
        assert(dateTime is not None)
        assert(tick is not None)
        super(TickDataSeries, self).appendWithDateTime(dateTime, tick)

        self.__ask1DS.appendWithDateTime(dateTime, tick.getAsk())
        self.__asize1DS.appendWithDateTime(dateTime, tick.getAsize())
        self.__bid1DS.appendWithDateTime(dateTime, tick.getBid())
        self.__bsize1DS.appendWithDateTime(dateTime, tick.getBsize())
        self.__volumeDS.appendWithDateTime(dateTime, tick.getVolume())
        self.__lastDS.appendWithDateTime(dateTime, tick.getLast())

    def getAskDataSeries(self):
        return self.__ask1DS

    def getAsizeDataSeries(self):
        return self.__asize1DS

    def getBidDataSeries(self):
        return self.__bid1DS

    def getBsizeDataSeries(self):
        return self.__bsize1DS

    def getVolumeDataSeries(self):
        return self.__volumeDS

    def getLastDataSeries(self):
        return self.__lastDS


##########Feed
def feed_iterator(feed):
    feed.start()
    try:
        while not feed.eof():
            yield feed.getNextValuesAndUpdateDS()
    finally:
        feed.stop()
        feed.join()

class BaseFeed(observer.Subject):
    def __init__(self, maxLen):
        super(BaseFeed, self).__init__()

        maxLen = dataseries.get_checked_max_len(maxLen)

        self.__ds = {}
        self.__event = observer.Event()
        self.__maxLen = maxLen

    def reset(self):
        keys = self.__ds.keys()
        self.__ds = {}
        for key in keys:
            self.registerDataSeries(key)

    @abc.abstractmethod
    def createDataSeries(self, key, maxLen):
        raise NotImplementedError()

    @abc.abstractmethod
    def getNextValues(self):
        raise NotImplementedError()

    def registerDataSeries(self, key):
        if key not in self.__ds:
            self.__ds[key] = self.createDataSeries(key, self.__maxLen)

    def getNextValuesAndUpdateDS(self):
        dateTime, values = self.getNextValues()
        if dateTime is not None:
            for key, value in values.items():
                try:
                    ds = self.__ds[key]
                except KeyError:
                    ds = self.createDataSeries(key, self.__maxLen)
                    self.__ds[key] = ds
                ds.appendWithDateTime(dateTime, value)
        return (dateTime, values)

    def __iter__(self):
        return feed_iterator(self)

    def getNewValuesEvent(self):
        return self.__event

    def dispatch(self):
        dateTime, values = self.getNextValuesAndUpdateDS()
        if dateTime is not None:
            self.__event.emit(dateTime, values)
        return dateTime is not None

    def getKeys(self):
        return self.__ds.keys()

    def __getitem__(self, key):
        return self.__ds[key]

    def __contains__(self, key):
        return key in self.__ds

class BaseTickFeed(BaseFeed):
    def __init__(self,maxLen=None):
        super(BaseTickFeed, self).__init__(maxLen)
        self.__defaultInstrument = None
        self.__currentTicks = None
        self.__lastTicks = {}

    def reset(self):
        self.__currentTicks = None
        self.__lastTicks = {}
        super(BaseTickFeed, self).reset()

    @abc.abstractmethod
    def getCurrentDateTime(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def getNextTicks(self):
        raise NotImplementedError()

    def createDataSeries(self, key, maxLen):
        ret = TickDataSeries(maxLen)
        return ret

    def getNextValues(self):
        dateTime = None
        ticks = self.getNextTicks()
        if ticks is not None:
            dateTime = ticks.getDateTime()

            if self.__currentTicks is not None and self.__currentTicks.getDateTime() >= dateTime:
                raise Exception(
                        "Tick date times are not in order. Previous datetime was %s and current datetime is %s" % (
                            self.__currentTicks.getDateTime(),
                            dateTime))
            self.__currentTicks = ticks
            for instrument in ticks.getInstruments():
                self.__lastTicks[instrument] = ticks[instrument]
        return (dateTime, ticks)

    def getCurrentTicks(self):
        return self.__currentTicks

    def getLastTick(self, instrument):
        return self.__lastTicks.get(instrument, None)

    def getDefaultInstrument(self):
        return self.__defaultInstrument

    def getRegisteredInstruments(self):
        return self.getKeys()

    def registerInstrument(self, instrument):
        self.__defaultInstrument = instrument
        self.registerDataSeries(instrument)

    def getDataSeries(self, instrument=None):
        if instrument is None:
            instrument = self.__defaultInstrument
        return self[instrument]

    def getDispatchPriority(self):
        return 0

def safe_min(left, right):
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return min(left,right)

class TickMemFeed(BaseTickFeed):
    def __init__(self,maxLen=None):
        super(TickMemFeed, self).__init__(maxLen)

        self.__ticks = {}
        self.__nextPos = {}
        self.__started = False
        self.__currDateTime = None

    def reset(self):
        self.__nextPos = {}
        for instrument in self.__ticks.keys():
            self.__nextPos.setdefault(instrument,0)
        self.__currDateTime = None
        super(TickMemFeed, self).reset()

    def getCurrentDateTime(self):
        return self.__currDateTime

    def start(self):
        super(TickMemFeed, self).start() #### have?
        self.__started = True

    def stop(self):
        pass

    def join(self):
        pass

    def addTicksFromSequence(self, instrument, ticks):
        if self.__started:
            raise Exception("Can't add more ticks once you started consuming ticks")

        self.__ticks.setdefault(instrument,[])
        self.__nextPos.setdefault(instrument,0)

        self.__ticks[instrument].extend(ticks)
        tickCmp = lambda x,y: cmp(x.getDateTime(), y.getDateTime())
        self.__ticks[instrument].sort(tickCmp)

        self.registerInstrument(instrument)

    def eof(self):
        ret = True
        for instrument, ticks in self.__ticks.iteritems():
            nextPos = self.__nextPos[instrument]
            if nextPos < len(ticks):
                ret = False
                break
        return ret

    def peekDateTime(self):
        ret = None

        for instrument, ticks in self.__ticks.iteritems():
            nextPos = self.__nextPos[instrument]
            if nextPos < len(ticks):
                ret = safe_min(ret, ticks[nextPos].getDateTime())

        return ret

    def getNextTicks(self):
        smallestDateTime = self.peekDateTime()

        if smallestDateTime is None:
            return None

        ret = {}
        for instrument, ticks in self.__ticks.iteritems():
            nextPos = self.__nextPos[instrument]
            if nextPos < len(ticks) and ticks[nextPos].getDateTime() == smallestDateTime:
                ret[instrument] = ticks[nextPos]
                self.__nextPos[instrument] += 1

        if self.__currDateTime == smallestDateTime:
            raise Exception("Duplicate ticks found for %s on %s" % (ret.keys(), smallestDateTime))

        self.__currDateTime = smallestDateTime
        return Ticks(ret)

class FastDictReader(object):
    def __init__(self, f, fieldnames=None, dialect="excel", *args, **kwargs):
        self.__fieldNames = fieldnames
        self.reader = csv.reader(f,dialect,*args,**kwargs)
        if self.__fieldNames is None:
            self.__fieldNames = self.reader.next()
        self.__dict = {}

    def __iter__(self):
        return self

    def next(self):
        row = self.reader.next()
        while row == []:
            row = self.reader.next()

        assert(len(self.__fieldNames) == len(row))
        for i in xrange(len(self.__fieldNames)):
            self.__dict[self.__fieldNames[i]] = row[i]

        return self.__dict

class TickCsvFeed(TickMemFeed):
    def __init__(self,maxLen=None):
        super(TickCsvFeed, self).__init__(maxLen)
        self.__tickFilter = None

    def setTickFilter(self, tickFilter):
        self.__tickFilter = tickFilter

    def getTickFilter(self):
        return self.__tickFilter
            

    def addTicksFromCSV(self, instrument, path, rowParser):
        loadedTicks = []
        reader = FastDictReader(open(path,"r"),fieldnames=rowParser.getFieldNames(),
                delimiter=rowParser.getDelimiter())
        for row in reader:
            tick_ = rowParser.parseTick(row)
            if tick_ is not None and (self.__tickFilter is None or self.__tickFilter.includeTick(tick_)):
                loadedTicks.append(tick_)

        self.addTicksFromSequence(instrument,loadedTicks)


######
class GenericTickFeed(TickCsvFeed):
    def __init__(self , maxLen=None):
        super(GenericTickFeed, self).__init__(maxLen)


        self.__dateTimeFormat = "%Y%m%d %H:%M:%S:%f"
        self.__columnNames = {
            "datetime": "dateTime",
            "ask1": "ask1",
            "asize1": "asize1",
            "bid1": "bid1",
            "bsize1": "bsize1",
            "volume": "volume",
            "last": "last",
        }

    def setColumnName(self, col, name):
        self.__columnNames[col] = name

    def setDateTimeFormat(self, dateTimeFormat):
        self.__dateTimeFormat = dateTimeFormat

    def addTicksFromCSV(self, instrument, path):

        rowParser = TickRowParser(
            self.__columnNames, self.__dateTimeFormat)

        super(GenericTickFeed, self).addTicksFromCSV(instrument, path, rowParser)
