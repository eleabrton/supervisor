##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

"""
Logger implementation loosely modeled on PEP 282.  We don't use the
PEP 282 logger implementation in the stdlin ('logging') because it's
idiosyncratic and a bit slow for our purposes (we don't use threads).
"""

# This module must not depend on any non-stdlib modules to
# avoid circular import problems

import os
import errno
import sys
import time
import StringIO
import traceback

class LevelsByName:
    CRIT = 50
    ERRO = 40
    WARN = 30
    INFO = 20
    DEBG = 10
    TRAC = 5

class LevelsByDescription:
    critical = LevelsByName.CRIT
    error = LevelsByName.ERRO
    warn = LevelsByName.WARN
    info = LevelsByName.INFO
    debug = LevelsByName.DEBG
    trace = LevelsByName.TRAC

def _levelNumbers():
    bynumber = {}
    for name, number in LevelsByName.__dict__.items():
        bynumber[number] = name
    return bynumber

LOG_LEVELS_BY_NUM = _levelNumbers()

def getLevelNameByNumber(number):
    return LOG_LEVELS_BY_NUM[number]

def getLevelNumByDescription(description):
    num = getattr(LevelsByDescription, description, None)
    return num

class Handler:
    fmt = '%(message)s'
    level = LevelsByName.INFO
    def setFormat(self, fmt):
        self.fmt = fmt

    def setLevel(self, level):
        self.level = level

    def flush(self):
        self.stream.flush()

    def close(self):
        self.stream.close()

    def emit(self, record):
        try:
            msg = self.fmt % record.asdict()
            try:
                self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            self.flush()
        except:
            self.handleError(record)

    def handleError(self, record):
        ei = sys.exc_info()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
        del ei

class FileHandler(Handler):
    """File handler which supports reopening of logs.
    """

    def __init__(self, filename, mode="a"):
        self.stream = open(filename, mode)
        self.baseFilename = filename
        self.mode = mode

    def reopen(self):
        self.close()
        self.stream = open(self.baseFilename, self.mode)

    def remove(self):
        try:
            os.remove(self.baseFilename)
        except OSError, why:
            if why[0] != errno.ENOENT:
                raise

class StreamHandler(Handler):
    def __init__(self, strm=None):
        self.stream = strm
        
    def remove(self):
        if hasattr(self.stream, 'clear'):
            self.stream.clear()

    def reopen(self):
        pass

class BoundIO:
    def __init__(self, maxbytes, buf=''):
        self.maxbytes = maxbytes
        self.buf = buf

    def flush(self):
        pass

    def close(self):
        self.clear()

    def write(self, s):
        slen = len(s)
        if len(self.buf) + slen > self.maxbytes:
            self.buf = self.buf[slen:]
        self.buf += s

    def getvalue(self):
        return self.buf

    def clear(self):
        self.buf = ''
            
class RotatingFileHandler(FileHandler):
    def __init__(self, filename, mode='a', maxBytes=512*1024*1024,
                 backupCount=10):
        """
        Open the specified file and use it as the stream for logging.

        By default, the file grows indefinitely. You can specify particular
        values of maxBytes and backupCount to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly maxBytes in
        length. If backupCount is >= 1, the system will successively create
        new files with the same pathname as the base file, but with extensions
        ".1", ".2" etc. appended to it. For example, with a backupCount of 5
        and a base file name of "app.log", you would get "app.log",
        "app.log.1", "app.log.2", ... through to "app.log.5". The file being
        written to is always "app.log" - when it gets filled up, it is closed
        and renamed to "app.log.1", and if files "app.log.1", "app.log.2" etc.
        exist, then they are renamed to "app.log.2", "app.log.3" etc.
        respectively.

        If maxBytes is zero, rollover never occurs.
        """
        if maxBytes > 0:
            mode = 'a' # doesn't make sense otherwise!
        FileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.counter = 0
        self.every = 10

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        if self.shouldRollover(record):
            self.doRollover()
        FileHandler.emit(self, record)

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.baseFilename, dfn)
        self.stream = open(self.baseFilename, 'w')

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.maxBytes > 0:                   # are we rolling over?
            msg = self.fmt % record.asdict()
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0

class LogRecord:
    def __init__(self, level, msg, **kw):
        self.level = level
        self.msg = msg
        self.kw = kw
        self.dictrepr = None

    def asdict(self):
        if self.dictrepr is None:
            now = time.time()
            msecs = (now - long(now)) * 1000
            part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
            asctime = '%s,%03d' % (part1, msecs)
            levelname = getLevelNameByNumber(self.level)
            if self.kw:
                msg = self.msg % self.kw
            else:
                msg = self.msg
            self.dictrepr = {'message':msg, 'levelname':levelname,
                             'asctime':asctime}
        return self.dictrepr

class Logger:
    def __init__(self, level=None, handlers=None):
        self.level = level
        if handlers is None:
            self.handlers = []
        else:
            self.handlers = handlers

    def trace(self, msg, **kw):
        if LevelsByName.TRAC >= self.level:
            self._log(LevelsByName.TRAC, msg, **kw)
    
    def debug(self, msg, **kw):
        if LevelsByName.DEBG >= self.level:
            self._log(LevelsByName.DEBG, msg, **kw)
    
    def info(self, msg, **kw):
        if LevelsByName.INFO >= self.level:
            self._log(LevelsByName.INFO, msg, **kw)

    def warn(self, msg, **kw):
        if LevelsByName.WARN >= self.level:
            self._log(LevelsByName.WARN, msg, **kw)

    def error(self, msg, **kw):
        if LevelsByName.ERRO >= self.level:
            self._log(LevelsByName.ERRO, msg, **kw)

    def critical(self, msg, **kw):
        if LevelsByName.CRIT >= self.level:
            self._log(LevelsByName.CRIT, msg, **kw)

    def log(self, level, msg, **kw):
        self._log(level, msg, **kw)

    def _log(self, level, msg, **kw):
        record = LogRecord(level, msg, **kw)
        for handler in self.handlers:
            if record.level >= handler.level:
                handler.emit(record)

    def addHandler(self, hdlr):
        self.handlers.append(hdlr)

    def getvalue(self):
        raise NotImplementedError

def getLogger(filename, level, fmt, rotating=False, maxbytes=0, backups=0,
              stdout=False):

    handlers = []

    logger = Logger(level)
    
    if filename is None:
        if not maxbytes:
            maxbytes = 1<<21 #2MB
        io = BoundIO(maxbytes)
        handlers.append(StreamHandler(io))
        logger.getvalue = io.getvalue

    else:
        if rotating is False:
            handlers.append(FileHandler(filename))
        else:
            handlers.append(RotatingFileHandler(filename,'a',maxbytes,backups))

    if stdout:
        handlers.append(StreamHandler(sys.stdout))

    for handler in handlers:
        handler.setFormat(fmt)
        handler.setLevel(level)
        logger.addHandler(handler)

    return logger

