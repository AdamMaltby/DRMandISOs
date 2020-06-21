#
# _author_ = Adam Maltby <adam_maltby@dell.com>
# _version_ = 0.1
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# By downloading any software from the Dell website via this script, you
# accept the terms of the Dell Software License Agreement:
# https://www.dell.com/learn/us/en/uscorp1/terms-of-sale-consumer-license-agreements
#
"""
SYNOPSIS:
    getDellRepoManComponentsAndISOs is designed to get DRM Compoenent links or download.

DESCRIPTION:
    Designed for sites where DRM sits in a dark site (no internet) and
    components, firmwares, plugins etc have to be pulled manually from
    Dells Website. This system reads various catalogues and pages to
    extrapolate the latest links for download off all required
    components and either presents relevant links back to the user
    or downloads to a storage folder automatically.

EXAMPLE:
    python getDellRepoManComponentsAndISOs.py -l -v -wb displayOnly drminstaller-linux suu-linux

EXAMPLE:
    python getDellRepoManComponentsAndISOs.py -wb drminstaller-windows suu-windows plugins -pa 192.168.268.254:3128
"""
import argparse
import getpass
import logging
import logging.handlers
import os
import requests
import sys
import tarfile
import warnings
import traceback
from copy import copy
from enum import Enum
from io import BytesIO
from json import loads
from time import sleep
from bs4 import BeautifulSoup
from lxml import html

# import agentheaders

# enable colour vt100 support in windows dos/cmd/powershell windows for python output
if os.name == 'nt':
    import ctypes
    kernel32 = ctypes.WinDLL('kernel32')
    hStdOut = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
    mode.value |= 4
    kernel32.SetConsoleMode(hStdOut, mode)


class TxtFormat(object):
    """Class to define a set of console colours and formatting options."""

    # add __next__ to the classes for yield/next looping at later date
    def __init__(self, attr):
        """__init__ of top level formatter key value pairs and sub classes fg and bg."""
        self.name = 'TxtFormat'
        self.attr = attr

    class style:
        """Style subclass."""

        def __init__(self, attr):
            """__init__ of fg name and attr."""
            self.name = 'style'
            self.attr = attr
        reset = "\033[m"
        bold = "\033[01m"
        disable = "\033[02m"
        underline = "\033[04m"
        reverse = "\033[07m"
        strikethrough = "\033[09m"
        invisible = "\033[08m"

    class fg:
        """fg - Foreground colour key value pairs."""

        def __init__(self, attr):
            """__init__ of fg name and attr."""
            self.name = 'foreground'
            self.attr = attr
        black = "\033[30m"
        red = "\033[31m"
        green = "\033[32m"
        orange = "\033[33m"
        blue = "\033[34m"
        magenta = "\033[35m"
        cyan = "\033[36m"
        lightgrey = "\033[37m"
        darkgrey = "\033[90m"
        lightred = "\033[91m"
        lightgreen = "\033[92m"
        yellow = "\033[93m"
        lightblue = "\033[94m"
        lightmagenta = "\033[95m"
        lightcyan = "\033[96m"
        brightwhite = "\033[97m"

    class bg:
        """bg - Background colour key value pairs."""

        def __init__(self, attr):
            """__init__ of bg name and attr."""
            self.name = 'background'
            self.attr = attr
        black = "\033[40m"
        red = "\033[41m"
        green = "\033[42m"
        orange = "\033[43m"
        blue = "\033[44m"
        magenta = "\033[45m"
        cyan = "\033[46m"
        lightgrey = "\033[47m"
        darkgrey = "\033[100m"
        lightred = "\033[101m"
        lightgreen = "\033[102m"
        yellow = "\033[103m"
        lightblue = "\033[104m"
        lightmagenta = "\033[105m"
        lightcyan = "\033[106m"
        brightwhite = "\033[107m"

    class symbols:
        """Uncode characters."""

        def __init__(self, attr):
            """__init__ of fg name and attr."""
            self.name = 'symbols'
            self.attr = attr
        arrow_curved_down_right = "\u2BA9"
        bullet_circle = "\u2022"


# Provide a tidier choice list for download options. Future updates for components can just be added to this dict.
# Not done this as a class as it is for this script only, not part of my standard template.
whichbits = {'displayOnly': 'The default choice if the argument is not passed.\nCan be used with other choices to limit output.\nNot using displayOnly when using -wb in conjucntion with components invokes downloading automatically.',
             'drminstaller-linux': 'Display or download the current DRM Installer for Linux.',
             'drminstaller-windows': 'Display or download the current DRM Installer for Windows.',
             'plugins': 'Display or download DRM plugins only.',
             'suu-linux': 'Display or download the SUU for Linux inband firmware updates',
             'suu-windows': 'Display or download the SUU for Windows inband and oob firmware updates'}


#class Error(Exception):
#    """Base class for manually custom errors"""


class DownloadFailedWithoutStatusCode(requests.RequestException):
    """
    We will Raise this when an unknown download error occurs.

    Attribute:
      message - the message passed or the default message
    """

    def __init__(self, message="Download has failed. We recevied no bad status code so most likely the connection just stalled and died."):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message


class RawAndDefaultsFormatter(argparse.ArgumentDefaultsHelpFormatter,
                              argparse.RawDescriptionHelpFormatter):
    """
    Custom class to use mulitple formatters in argparser.

    No idea why python doesn't let us do multiples natively yet....
    We don't need to do anything else with this class inside it so just send a pass
    """

    pass


# setup arg parser
parser = argparse.ArgumentParser(description='Gets current DRM App and Plugin locations with optional download.\nSee Components Options section for download options.',
                                 formatter_class=RawAndDefaultsFormatter)
arggrp_logging = parser.add_argument_group('CLI and File logging options,')
arggrp_logging.add_argument(
    "-v", "--verbose", help='''Verbose display output to the CLI, default is none when not specified. Add v's (max 6) to increase verbosity. if unset, will set to WARNING.''', action="count", default=0, dest='v')
arggrp_logging.add_argument("-l", "--logfile", help='''Log output to file, in same directory as script. Logging will rotate every 1mb of logging unless deleted. Logging level will be based on -v argument.''', action="store_true", dest='l')

arggrp_downloads = parser.add_argument_group('Component Download Options')
arggrp_downloads.add_argument("-dp", "--downloadToPath", default="{}".format(os.path.dirname(os.path.abspath(__file__))), action='store',
                              help='''If unset or used but no path specified, saves will default to this script launch directory. Ignored if -wb argument contains display-Only option.''', dest='dp')
# whichBits to tie in with whichbits list below ion help and set above for actual items
parser.add_argument("-wb", "--whichBits", default='display-Only', nargs='*', metavar='Component', choices=whichbits.keys(), action='store', help='''Supplied as a space separated list. Default is displayOnly.''', dest='wb')
# generate format friendly list using argparser subparser as a short cut for display some formatted --help info. Not ideal, but quick (and dirty).....
bitsgrp_downloads = parser.add_subparsers(title='whichBits Component Options List for Display/Download using -wb / --whichBits')
for k in whichbits:
    bitsgrp_downloads.add_parser(k, help=whichbits[k])
# proxy info
#TODO: Add secure password option from CLI for automated use via Proxy.
arggrp_proxy = parser.add_argument_group(
    'Proxy Details - note for security, password is promtped for during running. Not an parameter option prior to launch.')
arggrp_proxy.add_argument("-pa", "--proxyaddress", default=None, help='''Specify Proxy Address inc port if not port 80 or 443, e.g. myproxy.dom.local:8080 or 192.168.234.254''', action="store",  dest='pa')
arggrp_proxy.add_argument("-pu", "--proxyusername", help='Enter Proxy Username', action="store", dest='pu')
args = parser.parse_args()


class LogitLevelColours():
    """Map Log Levels to Colour."""

    def __init__(self, attr):
        """__init__ of self name and attr."""
        self.name = 'logitLevelColours'
        self.attr = attr
    DEBUG = TxtFormat.fg.cyan
    INFO = TxtFormat.fg.lightgrey
    SUCCESS = TxtFormat.fg.green
    WARNING = TxtFormat.fg.yellow
    ERROR = TxtFormat.fg.red
    CRITICAL = TxtFormat.bg.red+TxtFormat.fg.brightwhite
    ENFORCED = TxtFormat.fg.magenta


class OverrideLoggingLevel:
    """
    Temporarily changes logging context.

    Technically a bit of a smell this one is.
    Class provides enforced messages outside the scope of the normal logging levels.
    They probably should be info messages, but it's purely for limited messages
    outside of normal output scope so for the odd few, it'll do.
    """

    def __init__(self, logger, level=None, handler=None, close=True):
        """__init__ to create the logger items for overriding standard logger process."""
        self.logger = logger
        self.level = level
        self.handler = handler
        self.close = close

    def __enter__(self):
        """__enter__ to make a note on entry of previous settings so we have them to revert back to after."""
        if self.level is not None:
            self.old_level = self.logger.level
            self.logger.setLevel(self.level)
        if self.handler:
            self.logger.addHandler(self.handler)

    def __exit__(self, et, ev, tb):
        """__exit__ process sets the logger back to previous settings."""
        if self.level is not None:
            self.logger.setLevel(self.old_level)
        if self.handler:
            self.logger.removeHandler(self.handler)
        if self.handler and self.close:
            self.handler.close()
        # implicit return of None => don't swallow exceptions


class LogitFormatting(logging.Formatter):
    """Custom colour logging output for logger function."""

    # handleIndex = HandleIndex()
    # hi = 0

    def __init__(self, recordMsg):
        """__init__ to setup this class with the inherited class."""
        logging.Formatter.__init__(self, recordMsg)

    def format(self, record):
        """Format the record detail to output."""
        c_record = copy(record)
        levelname = c_record.levelname
        # message = c_record.msg
        levelColour = LogitLevelColours.__dict__[levelname]
        c_levelname = ('{}{:^10}{}').format(levelColour, levelname, TxtFormat.style.reset)
        c_record.levelname = c_levelname
        return logging.Formatter.format(self, c_record)


warnings.filterwarnings("ignore")
logit = logging.getLogger("logit")

# define success message level
logging.SUCCESS = 25  # between WARNING and INFO
logging.addLevelName(logging.SUCCESS, 'SUCCESS')
def success(self, message, *args, **kwargs):
    """Success Custom Log Level Implementer"""

    if self.isEnabledFor(logging.SUCCESS):
        self._log(logging.SUCCESS, message, args, **kwargs)

logging.Logger.success = success


logging.ENFORCED = 100
logging.addLevelName(logging.ENFORCED, 'ENFORCED')
def enforced(self, message, *args, **kwargs):
    """Enforced ustom Log Level Implementer"""

    if self.isEnabledFor(logging.ENFORCED):
        self._log(logging.ENFORCED, message, args, **kwargs)

logging.Logger.enforced = enforced

if args.v >= 6:
    logit.setLevel(logging.DEBUG)
if args.v == 5:
    logit.setLevel(logging.INFO)
if args.v == 4:
    logit.setLevel(logging.SUCCESS)
if args.v == 3:
    logit.setLevel(logging.WARNING)
if args.v == 2:
    logit.setLevel(logging.ERROR)
if args.v == 1:
    logit.setLevel(logging.CRITICAL)
if args.v == 0:
    # change this to use a different default level.
    logit.setLevel(logging.WARNING)

csh = logging.StreamHandler()
cshLF = LogitFormatting('[%(asctime)s][%(levelname)s][Line:%(lineno)d] %(message)s')
csh.setFormatter(cshLF)
logit.addHandler(csh)

if args.l:  # only create file & handler if -l is specified and logit level is > notset or 0
    logit.debug("Log file requested. Setting up....")
    logitFileName = os.path.splitext(os.path.abspath(__file__))[0]+'.log'
    logit.debug("Log file path: {}".format(logitFileName))
    rfh = logging.handlers.RotatingFileHandler(
        logitFileName, maxBytes=1048576, backupCount=20)
    rfhLF = logging.Formatter('%(asctime)s|%(levelname)s|Line:%(lineno)d|%(message)s')
    rfh.setFormatter(rfhLF)
    logit.addHandler(rfh)
    # with OverrideLoggingLevel(logit, level=logging.ENFORCED):
    logit.enforced("****** New Execution Run Started ******")

if args.v == 0:
    ln = logging.getLevelName(logit.getEffectiveLevel()).lower()
    lnColour = LogitLevelColours.__dict__[ln.upper()]
    # with LoggingContext(logit, level=logging.ENFORCED): #temp override logging conext for one message only.
    logit.enforced("Logging level not set at CLI. Defaulting to {} level output. ENFORCED messages will always be shown.".format(ln.upper()))



class DictWalkerMode(Enum):
    """
    A class to validate the dictWalker mode.

    Ensures mode passed to dictWalker matched one of the predefined
    values listed in this class. Otherwise dictWalker will not work.
    Overrides _missing_ so if value is not passed, returns display
    mode.... junt in case I have a blank moment and for the prop...
    """

    display = 'display'
    dictBuild = 'dictBuild'

    @classmethod
    def _missing_(cls, value):
        return DictWalkerMode.display


def dictWalker(d, dwMode=DictWalkerMode, u=None, indent=-4):
    """
    Loops through data supplied to determine structure.

    Examines the content of dicts and lists recursively to build out the
    filtered list of requirements.
    Insert custom actions in each if as required inside the if/elifs.
    In this build we have added process to update a recursive dictionary
    or just simply print to screen based on the mode.
    """
    indent += 4
    if indent == 0:
        logit.debug("Entering: def {}({}, {}, {}, {})".format(str(sys._getframe().f_code.co_name), d, str(dwMode), u, indent))
    else:
        logit.debug("Entering: def {}({}, {}, {}, {}): Recursive level {}".format(str(sys._getframe().f_code.co_name), d, str(dwMode), u, indent, indent // 4))

    if u:
        logit.debug('Updating variable u with: {}'.format(u))
        u.update(u)
    else:
        u = {}

    global dpath
    # cehe
    for k, v in d.items():
        if isinstance(v, str) or isinstance(v, int) or isinstance(v, float):
            dpath.append(k)
            if dwMode.value == 'dictBuild':
                p = ".".join(dpath)
                logit.debug("Updating u variable with {}={}".format(p, v))
                u.update({p:v})
            elif dwMode.value == 'display':
                logit.debug("{}={}".format(".".join(dpath), v))
                print(indent * ' ', "{} {} = {}".format(TxtFormat.symbols.arrow_curved_down_right, k, v))
                # print(("{}={}".format(".".join(path), v)))
            dpath.pop()
        elif v is None:
            dpath.append(k)
            # nothing to do for this particular script. Will/Should never get called.
            logit.warning("dictWalker got passed a key with no value information from {}. Depending on the data being walked this might cause issues further in to execution.".format(k))
            dpath.pop()
        elif isinstance(v, list):
            dpath.append(k)
            if dwMode.value == 'dictBuild':
                for v_int in v:
                    logit.debug('Recursing into dictWalker passing params; {}, {}, {}, {}'.format(v_int, str(dwMode), u, indent))
                    dictWalker(v_int, DictWalkerMode.dictBuild, u=u, indent=indent)
            elif dwMode.value == 'display':
                for v_int in v:
                    logit.debug('Recursing into dictWalker with params; {}, {}, {}'.format(v_int, str(dwMode), indent))
                    dictWalker(v_int, DictWalkerMode.display, indent=indent)
            dpath.pop()
        elif isinstance(v, dict):
            dpath.append(k)
            if dwMode.value == 'dictBuild':
                logit.debug('Recursing into dictWalker passing params; {}, {}, {}, {}'.format(v, str(dwMode), u, indent))
                u.update(dictWalker(v, DictWalkerMode.dictBuild, u=u, indent=indent))
            elif dwMode.value == 'display':
                print(indent * " ", "{} {}".format(TxtFormat.symbols.arrow_curved_down_right, k))
                logit.debug('Recursing into dictWalker with params; {}, {}, {}'.format(v, str(dwMode), indent))
                dictWalker(v, DictWalkerMode.display, indent=indent)
            dpath.pop()
        else:
            logit.error("Data type {} not recognized: {}.{}={}".format(type(v), ".".join(dpath), k, v))

    if indent == 0:
        logit.debug("Exiting def {}".format(str(sys._getframe().f_code.co_name)))
    else:
        logit.debug("Exiting def {}: Recursive level {}".format(str(sys._getframe().f_code.co_name), indent // 4))
    return u


def buildComponentSets(wb, drmJson=None, suuIso=None):
    """Build component sets from json and web scrapes to match -wb selections."""
    logit.debug("Entering def {}:".format(str(sys._getframe().f_code.co_name)))
    CSets = {}

    # if displayOnly with no components, reset wb to full component set from whichBits keys
    if len(wb) == 1 and "displayOnly" in wb:
        wb = list(whichbits.keys())

    if drmJson: drmJsonBaseLocation = "https://"+jsonCatalog['RMPlugins']['_baselocation']+"/"

    for k in wb:
        if k in whichbits:
            # make shift switch equivalent. Pass dictionary portions to walker process to get relevant k/v pairs for whichbits/wb sets
            if k == 'displayOnly':
                pass
            if k == 'suu-linux':
                logit.info("suu-linux requested")
                if CSets.get('SUU') is None:
                    CSets['SUU'] = {}
                CSets['SUU'].update({'Linux 64 bit':suuIso['Linux 64 bit']['Download Link']})
            if k == 'suu-windows':
                logit.info("suu-windows requested")
                if CSets.get('SUU') is None:
                    CSets['SUU'] = {}
                CSets['SUU'].update({'Windows 64 bit':suuIso['Windows 64 bit']['Download Link']})
            if k == 'plugins':
                logit.info("plugins requested")
                CSets['Plugin'] = {}
                for d in drmJson['RMPlugins']['Plugin']:
                    for e in d:
                        if e == "Description":
                            p = d[e]
                            CSets['Plugin'][p] = {}
                        if e == "FileLocation" or e == "SignFileLocation":
                            url = str(drmJsonBaseLocation+d[e]).replace('\\', '/')
                            CSets['Plugin'][p].update({e:url})
            if k == 'drminstaller-windows':
                logit.info("drminstaller-windows requested")
                if CSets.get('DRM Installer') is None:
                    CSets['DRM Installer'] = {}
                CSets['DRM Installer'].update({"Windows 64 bit":drmJson['AppUpdateInfo']['WindowsInstaller']})
            if k == 'drminstaller-linux':
                logit.info("drminstaller-linux requested")
                if CSets.get('DRM Installer') is None:
                    CSets['DRM Installer'] = {}
                CSets['DRM Installer'].update({"Linux 64 bit":drmJson['AppUpdateInfo']['LinuxInstaller']})
        else:
            logit.critical("Given there are plenty of checks in place for component selection, if you have got here then something has gone horribly wrong... whichBits option {} not recognised. Exiting,".format(k))
            sys.exit(1)
    return CSets


# set base url locations for the catalog download
baseURLs = ('https://downloads.dell.com','https://dl.dell.com')
catalogURL = {
    'DRMVersion Info': 'https://downloads.dell.com/catalog/DRMVersion.tar.gz'}
suuWebPageURL = {
    'SUUpage': 'https://www.dell.com/support/article/en-uk/sln285500/dell-emc-server-update-utility-suu-guide-and-download?lang=en'}


def download(urls, saveTo=None, chunkSize=8192):
    """Download the item(s) passed in via urls paramter lst."""

    logit.debug("Entering def {}:".format(str(sys._getframe().f_code.co_name)))
    global s

    for url in urls:
        if s.proxies:
            logit.info('Accessing ' + urls[url] + ' via' + s.proxies.values)
        else:
            logit.info('Accessing ' + urls[url] + ' via direct internet connection')

        if not saveTo:
            # anything not saved to disk goes straught to memory, only catalogs and webscrape retreivals use this.
            i = 0
            r = None
            url = urls[url]
            while not r and i < 2:
                # if we are dealing with the catalog file on second iteration
                if i == 1 and os.path.basename(url) == os.path.basename(catalogURL):
                    if baseURLs[0] in url:
                        url = url.replace(baseURLs[0], baseURLs[1])
                    elif baseURLs[1] in url:
                        url = url.replace(baseURLs[1], baseURLs[0])
                    logit.info('First download failed. Swapping URL Location to {}'.format(url))
                # if we are dealing with the suu pages scrape on second iteration, note url is dynamic discovery so may not match a set variable, hence the static text.
                elif i == 1 and 'dell.com/support' in url:
                    logit.critical('URL source failed. Exiting script.')
                    sys.exit(1)
                try:
                    if i == 1:
                        logit.info('Original URL failed, trying alternate URL {}'.format(url))
                    r = s.get(url, stream=True)
                    logit.success('Content retreived to RAM.')
                    return r.content
                except (requests.exceptions.HTTPError,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.RequestException,
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ProxyError,
                        requests.exceptions.SSLError,
                        requests.exceptions.InvalidURL,
                        requests.exceptions.InvalidHeader,
                        requests.exceptions.InvalidProxyURL,
                        requests.exceptions.RetryError,
                        DownloadFailedWithoutStatusCode) as err:
                    print('')
                    logit.error(repr(err))
                    i =+ 1
                    r = None
                except:
                    print('')
                    logit.error(traceback.print_exc())
                    i =+ 1
                    r=None
        else:
            if not os.path.exists(saveTo):
                logit.warning("Save path specified does not exist, defaulting to current script directory.")
                saveTo = os.path.dirname(os.path.abspath(__file__))

            fName = os.path.basename(urls[url])
            saveAs = os.path.join(saveTo, fName)
            i = 0
            r = None
            url = urls[url]
            if os.path.exists(saveAs)                                                                        :
                logit.enforced("Skipping {}. File already exists in target directory.".format(fName))
            else:
                while not r and i < 2:
                    if i == 1:
                        if baseURLs[0] in url:
                            url = url.replace(baseURLs[0], baseURLs[1])
                        elif baseURLs[1] in url:
                            url = url.replace(baseURLs[1], baseURLs[0])
                    try:  # try download, catch is for remote server errors only, not early download termination due to issues script side.
                        if i == 1:
                            logit.info('Original URL failed, trying alternate URL {}'.format(url))
                        logit.info('Making Header request to get file size for {} and check file is available for download.'.format(fName))
                        r = s.get(url, stream=True).headers
                        expectedLength = int(r['Content-Length'])  # .headers.get('content-length')
                        logit.info("Expected Content Download Size: " + str(expectedLength))
                        with s.get(url, stream=True, timeout=60) as r:
                            with open(saveAs+'.downloading', 'wb') as f:
                                for chunk in r.iter_content(chunk_size=chunkSize):
                                    if chunk:
                                        f.write(chunk)
                                    # receivedChunkSize = len(chunk)
                                    receivedLength = r.raw.tell()
                                    remainingBytes = expectedLength - receivedLength
                                    pctComplete = 100 / expectedLength * receivedLength
                                    if remainingBytes > 0 :
                                        print("\rDownloading {} : Downloaded {:0>6.2f}% : Bytes remaining {:0>11}".format(fName,pctComplete,remainingBytes),end='')
                                    else:
                                        print("\rDownloading {} : Downloaded {:0>6.2f}% : Bytes remaining {:0>11}".format(fName,pctComplete,remainingBytes))
                            if receivedLength < expectedLength:
                                print('')
                                logit.error('{} download incomplete. Received {} bytes, expected {}, missing {}.'.format(fName, receivedLength, expectedLength, expectedLength - receivedLength))
                                logit.debug('Last http status before failure was: {}'.format(r.status_code))
                                r.raise_for_status()
                                raise DownloadFailedWithoutStatusCode()
                            else:
                                logit.success('{} downloaded.'.format(fName))
                                try:
                                    os.rename(saveAs+'.downloading', saveAs)
                                except IOError as err:
                                    logit.error('Could not rename {} to {}'.format(saveAs+'.downloading',saveAs)) # should be picked up by IOError
                                    logit.error(repr(err))
                                except:
                                    logit.error('Could not rename {} to {}'.format(saveAs+'.downloading',saveAs)) # should be picked up by IOError
                                    logit.error(repr(err))
                    except (requests.exceptions.HTTPError,
                            requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout,
                            requests.exceptions.RequestException,
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ProxyError,
                            requests.exceptions.SSLError,
                            requests.exceptions.InvalidURL,
                            requests.exceptions.InvalidHeader,
                            requests.exceptions.InvalidProxyURL,
                            requests.exceptions.RetryError,
                            IOError,
                            EnvironmentError,
                            DownloadFailedWithoutStatusCode) as err:
                        print('')
                        logit.error(repr(err))
                        i =+ 1
                        r = None
                    except:
                        print('')
                        logit.error(traceback.print_exc())
                        i =+ 1
                        r=None
                if i == 2:
                    #Move on to next file. Not hard exit since we may still get the rest.
                    logit.error('All URL sources failed for {}'.format(url))


def extractJsonFromGzip(gzdata):
    """Extract gzip file to memory for json data retreival."""
    logit.debug("Entering def {}:".format(str(sys._getframe().f_code.co_name)))
    with tarfile.open(fileobj=BytesIO(gzdata), mode='r:gz') as t:
        logit.debug('Extracting gz')
        f = t.getmember('DRMVersion.json')
        logit.debug("Got {} from extracted gz".format(f.name))
        j = loads(t.extractfile(f).read().decode('utf-8'))
        logit.debug('Extracted info: {}'.format(j))
        t.close()
        logit.debug("Returning var j from def {}:".format(str(sys._getframe().f_code.co_name)))
        return j


def globalProxySessionSetup(proxy=None, proxyuser=None):
    """Create global proxy setup and return any necessary session keys if required."""
    logit.debug("Entering def {}:".format(str(sys._getframe().f_code.co_name)))
    global proxylist
    global proxypass
    global s
    s = requests.Session()
    if proxy:
        proxylist = {
            "http": "http://"+args.pa,
            "https": "https://"+args.pa
        }
        s.proxies = proxylist
        logit.debug('Proxy List: {}'.format(s.proxies))
    if proxyuser:
        proxypass = getpass.getpass("Enter Proxy Password")
    if proxy and proxyuser and proxypass:
        auth = requests.auth.HTTPProxyAuth(proxyuser, proxypass)
        s.auth = auth
        logit.debug('Received Proxy Credentials')


# main
if __name__ == "__main__":
    '''main code block'''
    logit.debug("Starting main code block.")
    # Define some global level vars, yes I know global vars are also a smell.....
    s = None
    proxylist = {}
    proxypass = None
    dpath = []

    # Check for Python version relese info and report as enforced, just in case.
    if float(sys.version[:3]) < 3.7:
        logit.warning("This script has not been tested on below Python 3.7")

    if args.pa: logit.info("Proxy Address Specified: " + args.pa)
    if args.pu: logit.info("Proxy User Specified: "  + args.pa)

    # Log Debug Info Messages regarding paramters selected
    if args.l:
        logit.info("Logging to file {}".format(logitFileName))

    if args.wb != 'display-Only':
        logit.info("Save location set to:"+args.dp)

    if 'display-Only' in args:
        logit.info("Getting URLs for items requested: "+",".join(map(str, args.wb)))
    else:
        logit.info("Download Selected Components for items requested: "+",".join(map(str, args.wb)))

    # run this even if no proxy, we are doing this because we are using Requests sessions
    # this allows us to keep the requetss all going through the same code base rather than
    # implement an alternate approach in the same code.
    globalProxySessionSetup(args.pa, args.pu)

    # check for string partial match or args.wb only having displayOnly and no other value
    if [a for a in args.wb if a.startswith('drm') or a.startswith('plug')] or (len(args.wb) == 1 and 'displayOnly' in args.wb):
        jsonCatalog = extractJsonFromGzip(download(catalogURL))

    if [a for a in args.wb if a.startswith('suu')] or (len(args.wb) == 1 and 'displayOnly' in args.wb) :
        #Download SUU Landing Page HTML
        suupage=download(suuWebPageURL)

        ###get SUU landing page###
        html = BeautifulSoup(suupage,'lxml')
        targetTable = html.select('table.table.table-striped.table-bordered') #target table
        soupTable = BeautifulSoup(str(targetTable), 'lxml')
        thead = soupTable.find('thead')
        colIdx={}
        for htr in thead.findAll('tr'):
            th=htr.findAll('th')
            for td in th:
                colIdx[td.text.strip()] = th.index(td)
        logit.debug("colIdx: "+str(colIdx))

        suuLinkMap={}
        tbody = soupTable.find('tbody')
        for btr in tbody.findAll('tr'):
            cells=btr.findAll('td')
            o_s=cells[colIdx['Operating System']].text.strip()
            suuLinkMap[o_s] = {}
            for ci in colIdx:
                if ci == 'Operating System':
                    pass
                elif ci == 'Download Link' or ci =='Documentation':
                    suuLinkMap[o_s].update({ci:cells[colIdx[ci]].find('a').get('href')})
                else:
                    suuLinkMap[o_s].update({ci:cells[colIdx[ci]].text.strip()})

        logit.debug("suuLinkMap: "+str(suuLinkMap))
        ### end suu landing page ###

        ### Get SUU ISO Page Links based on args in SUU type
        # Get landing page links
        for link in suuLinkMap:
            logit.info("Link extracted "+suuLinkMap[link]['Download Link'])
            suuLinkMap[link]['Download Link'] = download({link:suuLinkMap[link]['Download Link']})

        # Follow landing page links to get ISO links
        for link in suuLinkMap:
            html = BeautifulSoup(suuLinkMap[link]['Download Link'],'lxml')
            targetTable = html.select('div.my-5:nth-child(1) > div:nth-child(5) > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > a:nth-child(1)') #target table
            soupTable = BeautifulSoup(str(targetTable), 'lxml')
            logit.info("Found ISO URL: "+soupTable.find('a').get('href'))
            suuLinkMap[link]['Download Link'] = soupTable.find('a').get('href')
        ### End Get SUU ISO Links

    if len(args.wb) == 1 and 'displayOnly' in args.wb:
        # no params specified so get all
        cSets = buildComponentSets(args.wb, jsonCatalog, suuLinkMap)
    elif (any('drm' or 'plug' in a for a in args.wb) and (all('suu' not in a for a in args.wb))):
        # if has drm or plugins specified but not suu
        cSets = buildComponentSets(args.wb, drmJson=jsonCatalog)
    elif (any('drm' or 'plug' not in a for a in args.wb) and (all('suu' in a for a in args.wb))):
        # if only has suu specified
        cSets = buildComponentSets(args.wb, suuIso=suuLinkMap)
    else:
        # fallback get all
        cSets = buildComponentSets(args.wb, jsonCatalog, suuLinkMap)

    #downloads = dictWalker(cSets)
    if 'displayOnly' in args.wb:
        #dictWalker2(cSets) # print to screen
        dictWalker(cSets, DictWalkerMode.display)
    else:
        logit.debug('Collated Components to Download')
        #logit.debug(dictWalker2(cSets))
        #dictWalker2(cSets)  # print to screen
        dictWalker(cSets, DictWalkerMode.display)
        logit.enforced('About to start auto download. Waiting for 10 seconds for user cancellation.')
        try:
            sleep(10)
            #download(downloads, args.dp)
            #download(dictWalker(cSets), args.dp)
            download(dictWalker(cSets, DictWalkerMode.dictBuild), args.dp)
        except KeyboardInterrupt:
            logit.critical('User Cancelled Operations. Exiting.')
            sys.stderr = open(os.devnull, 'w')

    logit.enforced("End of Script.")
