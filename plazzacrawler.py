#!/usr/bin/env python

#
# Required Modules
# - beautifulsoup4
# - html5lib
# - requests
#

import sys
import os
import re
import logging
import multiprocessing

from bs4 import BeautifulSoup
import unicodedata
import httplib

from debug import Debug
from apkhelper import ApkVersionInfo
from reporthelper import ReportHelper

# Debug.USE_SOCKS_PROXY = True
if Debug.USE_SOCKS_PROXY:
    import requesocks as requests
else:
    import requests

###################
# DEBUG VARS      #
###################

# Debug.DEBUG        = True
# Debug.READFROMFILE = True  # Read from file for debugging
# Debug.SAVELASTFILE = True  # Write to file upon each request

###################
# END: DEBUG VARS #
###################

###################
# Globals         #
###################

manager = multiprocessing.Manager()
Global  = manager.Namespace()
Global.report = None
Global.dlFiles     = []
Global.dlFilesBeta = []

# logging
logFile   = '{0}.log'.format(os.path.basename(__file__))
logLevel  = (logging.DEBUG if Debug.DEBUG else logging.INFO)
logFormat = '%(asctime)s %(levelname)s/%(funcName)s(%(process)-5d): %(message)s'


def downloadApk(avi, isBeta=False):
    """
    downloadApk(apkInfo): Download the specified URL to APK file name
    """
    apkname = '{0}-{1}.apk'.format(avi.name.replace('.beta', ''),
                                   avi.realver.replace(' ', '_'))

    logging.info('Downloading "{0}" from: {1}'.format(apkname,avi.download_src))

    try:
        if os.path.exists(apkname):
            logging.info('Downloaded APK already exists.')
            return

        if os.path.exists(os.path.join('.', 'apkcrawler', apkname)):
            logging.info('Downloaded APK already exists (in ./apkcrawler/).')
            return

        if os.path.exists(os.path.join('..', 'apkcrawler', apkname)):
            logging.info('Downloaded APK already exists (in ../apkcrawler/).')
            return

        # Open the url
        session = requests.Session()
        session.proxies = Debug.getProxy()

        r = session.get(avi.download_src,stream=True) #plazza blocks fetching it at one go, we need to stream it in chunks
        with open(apkname, 'wb') as local_file:
            for chunk in r.iter_content(1024):
                local_file.write(chunk)
        if isBeta:
            Global.dlFilesBeta.append(apkname)
            logging.debug('beta: ' + ', '.join(Global.dlFilesBeta))
        else:
            tmp = Global.dlFiles
            tmp.append(apkname)
            Global.dlFiles = tmp
            # Global.dlFiles.append(apkname)
            logging.debug('reg : ' + ', '.join(Global.dlFiles))
    except OSError:
        logging.exception('!!! Filename is not valid: "{0}"'.format(apkname))
# END: def downloadApk


def checkOneApp(apkid):
    """
    checkOneApp(apkid):
    """
    logging.info('Checking app: {0}'.format(apkid))

    url       = 'http://www.plazza.ir/app/' + apkid + '?hl=en'

    session = requests.Session()
    session.proxies = Debug.getProxy()
    logging.debug('Requesting: ' + url)
    try:
        resp    = session.get(url,allow_redirects=False) #we get a 302 if application is not found
        if resp.status_code == httplib.OK:
            html    = unicodedata.normalize('NFKD', resp.text).encode('ascii', 'ignore')
            Debug.writeToFile(html_name, html, resp.encoding)

            try:
                dom       = BeautifulSoup(html, 'html5lib')
                latesthref = dom.find('a', {'itemprop': 'downloadUrl'})['href']
                latestver = dom.find('div', {'itemprop': 'softwareVersion'}).contents[0]
                appid     = re.search('(^\/dl\/)([0-9]+)(\/1$)', latesthref).group(2)
                latesturl = session.head('http://www.plazza.ir' + latesthref,allow_redirects=True).url
                #latestvercode = re.search('(_)([0-9]+)(\.apk)$', latesturl).group(2) #apparently this is NOT a (reliable?) versioncode
                avi = ApkVersionInfo(name=apkid,
                                     ver=latestver,
                                     #vercode=latestvercode,
                                     download_src=latesturl
                                     )
                if Global.report.isThisApkNeeded(avi):
                    downloadApk(avi)

                #Fetching of older versions is not completed, because it requires VIP accounts
                #olderapks = dom.find('div', {'style': 'direction: rtl'}).findAll('a', {'target': '_blank'})
                #for apk in olderapks:
                #    apkver = re.search('(\/)([0-9]+)(\?.*$|$)', apk['href']).group(2) #number is either end of string or there can be an ? for extra GET parameters
                #    apkurl = session.head('http://www.plazza.ir/dl_version/' + appid + '/' + apkver + '/1',allow_redirects=True).url

            except:
                logging.exception('!!! Error parsing html from: "{0}"'.format(url))
        else:
            logging.info('{0} not available on plazza.ir'.format(apkid))
    except:
        logging.exception('Connection error to plazza.ir when checking {0} at {1}'.format(apkid,url))

# END: def checkOneApp:


def main(param_list):
    """
    main(): single parameter for report_sources.sh output
    """
    lines = ''
    if len(param_list) == 1:
        with open(param_list[0]) as report:
            lines = report.readlines()
    else:
        lines = sys.stdin.readlines()

    Global.report = ReportHelper(lines)
    keys = Global.report.dAllApks.keys()

    if len(keys) == 0:
        print('ERROR: expecting:')
        print(' - 1 parameter (report file from output of report_sources.sh)')
        print(' or ')
        print(' - stdin from report_sources.sh')
        return

    # Start checking all apkids ...
    p = multiprocessing.Pool(3) #lower pool, those servers are less well routed from most of the globe
    p.map(checkOneApp, keys)

    logging.debug('Just before outputString creation')

    outputString = ' '.join(Global.dlFiles)
    if Global.dlFilesBeta:
        outputString += ' beta ' + ' '.join(Global.dlFilesBeta)

    logging.debug('Just after outputString creation')

    if outputString:
        print(outputString)
        sys.stdout.flush()

    logging.debug('Done ...')

# END: main():

###################
# END: Functions  #
###################

if __name__ == "__main__":
    logging.basicConfig(filename = logFile, filemode = 'w', level = logLevel, format = logFormat)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("requesocks").setLevel(logging.WARNING)

    main(sys.argv[1:])
