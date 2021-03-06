# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSearchHistoryHelper, GetPluginDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_js_execute
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta

###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
import urllib
import string
import random
import base64
from urlparse import urlparse
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from urlparse import urlparse, urljoin

from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from binascii import hexlify, unhexlify, a2b_hex
from hashlib import md5, sha256
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://www.meczyki.pl/'

class MeczykiPL(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'meczykipl', 'cookie':'meczykipl.cookie', 'cookie_type':'MozillaCookieJar'}) #, 'min_py_ver':(2,7,9)
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.DEFAULT_ICON_URL = 'http://www.meczyki.pl/images/logo.png'
        self.MAIN_URL = None
        
    def selectDomain(self):
        self.MAIN_URL = 'http://www.meczyki.pl/'
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem, nextCategory):
        printDBG("MeczykiPL.listMainMenu")
        
        params = dict(cItem)
        params.update({'category':nextCategory, 'title':_('--All--'), 'f_cat':'0'})
        self.addDir(params)
        
        sts, data = self.getPage(self.getFullUrl('/najnowsze_skroty.html'))
        if not sts: return 
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="content-box-text"', 'shortcuts-content-start')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            cat   = self.cm.ph.getSearchGroups(item, '''setCategory\(\s*([0-9]+?)\s*\)''')[0]
            icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''url\(\s*['"]([^'^"]+?)['"]\s*\)''')[0])
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'f_cat':cat})
            self.addDir(params)
    
    def listItems(self, cItem, nextCategory):
        printDBG("MeczykiPL.listItems |%s|" % cItem)
        
        baseUrl  = self.getFullUrl('/front/shortcut/get-shortcuts')
        page = cItem.get('page', 1)
        cat  = cItem.get('f_cat', '0')
        
        query = {'category':cat, 'page':page}
        url = baseUrl + '?' + urllib.urlencode(query)
        
        sts, data = self.getPage(url)
        if not sts: return
        
        try:
            data = byteify(json.loads(data))
            data = data['shortcuts']
            keys = list(data.keys())
            keys.sort(reverse=True)
            for key in keys:
                for item in data[key]['shortcuts']:
                    title = self.cleanHtmlStr(item['title']) + ' ' + item['score']
                    url   = self.getFullUrl(item['url'])
                    icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(item['title'], '''src=['"]([^'^"]+?)['"]''')[0])
                    if icon == '': icon = self.getFullIconUrl(item['area'])
                    desc  = '%s | %s' % (item['competition'], item['event_date'])
                    params = dict(cItem)
                    params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
                    self.addDir(params)
        except Exception:
            printExc()
        
        if 0 == len(self.currList): return
        
        query['page'] = page + 1
        url = baseUrl + '?' + urllib.urlencode(query)
        sts, data = self.getPage(url)
        if not sts: return
        
        try:
            if len(byteify(json.loads(data))['shortcuts'].keys()):
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':_('Next page'), 'page':page+1})
                self.addDir(params)
        except Exception:
            printExc()
            
    def exploreItem(self, cItem):
        printDBG("OkGoals.exploreItem")
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        titles = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="video-watch">', '</div>')[1].split('<BR>')
        for title in tmp:
            title = self.cleanHtmlStr(title) 
            if title != '': titles.append(title)
        
        tmp = re.compile('''['"]([^'^"]*?//config\.playwire\.com[^'^"]+?\.json)['"]''').findall(data)
        tmp.extend(re.compile('<iframe[^>]+?src="([^"]+?)"').findall(data))
        tmp.extend(re.compile('''<a[^>]+?href=['"](https?://[^'^"]*?ekstraklasa.tv[^'^"]+?)['"]''').findall(data))
        tmp.extend(re.compile('''<a[^>]+?href=['"](https?://[^'^"]*?polsatsport.pl[^'^"]+?)['"]''').findall(data))
        
        for idx in range(len(tmp)):
            url = self.getFullUrl(tmp[idx])
            if not self.cm.isValidUrl(url): continue
            if 'playwire.com' not in url and  self.up.checkHostSupport(url) != 1: continue
            title = cItem['title']
            if len(titles) == len(tmp): title += ' - ' + titles[idx]
            
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':title, 'url':url})
            self.addVideo(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("OkGoals.getLinksForVideo [%s]" % cItem)
        urlTab = []
        videoUrl = cItem['url']
        if 'playwire.com' in videoUrl:
            sts, data = self.cm.getPage(videoUrl)
            if not sts: return []
            try:
                data = byteify(json.loads(data))
                if 'content' in data:
                    url = data['content']['media']['f4m']
                else:
                    url = data['src']
                sts, data = self.cm.getPage(url)
                baseUrl = self.cm.ph.getDataBeetwenMarkers(data, '<baseURL>', '</baseURL>', False)[1].strip()
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<media ', '>')
                for item in data:
                    url  = self.cm.ph.getSearchGroups(item, '''url=['"]([^'^"]+?)['"]''')[0]
                    height = self.cm.ph.getSearchGroups(item, '''height=['"]([^'^"]+?)['"]''')[0]
                    bitrate = self.cm.ph.getSearchGroups(item, '''bitrate=['"]([^'^"]+?)['"]''')[0]
                    name = '[%s] bitrate:%s height: %s' % (url.split('.')[-1], bitrate, height)
                    if not url.startswith('http'):
                        url = baseUrl + '/' + url
                    if url.startswith('http'):
                        if 'm3u8' in url:
                            hlsTab = getDirectM3U8Playlist(url)
                            for idx in range(len(hlsTab)):
                                hlsTab[idx]['name'] = '[hls] bitrate:%s height: %s' % (hlsTab[idx]['bitrate'], hlsTab[idx]['height'])
                            urlTab.extend(hlsTab)
                        else:
                            urlTab.append({'name':name, 'url':url})
            except Exception:
                printExc()
        elif videoUrl.startswith('http'):
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))
        return urlTab

        
    def getVideoLinks(self, videoUrl):
        printDBG("OkGoals.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        return urlTab
    
    def getFavouriteData(self, cItem):
        printDBG('MeczykiPL.getFavouriteData')
        return json.dumps(cItem) 
        
    def getLinksForFavourite(self, fav_data):
        printDBG('MeczykiPL.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MeczykiPL.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'}, 'list_items')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'explore_item')
        elif 'explore_item' == category:
            self.exploreItem(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MeczykiPL(), True, [])

    