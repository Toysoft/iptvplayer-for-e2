﻿# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import re
import urllib
import random
import string
try:    import json
except Exception: import simplejson as json

from os import path as os_path
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################


class CanlitvliveIoApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL_TV      = 'http://www.canlitvlive.io/'
        self.MAIN_URL_RADIO   = 'http://www.canliradyolive.com/'
        self.MAIN_URL = self.MAIN_URL_TV
        self.DEFAULT_ICON_URL = 'http://www.canlitvlive.io/images/footer_simge.png'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.COOKIE_FILE = GetCookieDir('canlitvlive.io.cookie')
        
        self.defaultParams = {}
        self.defaultParams.update({'header':self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        
    def getCategories(self, cItem, nextCategory):
        printDBG("CanlitvliveIoApi.getCategories")
        itemsList = []
        
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return []
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'class="ct_cont"'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        if cItem.get('priv_category', '') == 'tv': data.insert(0, '<a href="/a-z-tum-tv-kanallari.html">A-Z')
        else:  data.insert(0, '<a href="/tum-radyolar.html">All')
        for item in data:
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0] )
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr( item )
            params = {'name':cItem['name'], 'priv_category':nextCategory, 'type':'dir', 'title':title, 'url':url, 'icon':self.DEFAULT_ICON_URL}
            itemsList.append(params)
        
        return itemsList
        
    def getChannelsList(self, cItem):
        printDBG("CanlitvliveIoApi.getChannelsList")
        itemsList = []
        
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return []
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'kanallar'), ('</ul', '>'))
        for section in data:
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<li', '</li>')
            for item in section:
                url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0] )
                if not self.cm.isValidUrl(url): continue
                icon = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0] )
                if icon == '': icon = self.DEFAULT_ICON_URL
                title = self.cleanHtmlStr( item )
                params = {'name':cItem['name'], 'type':'video', 'title':title, 'url':url, 'icon':icon}
                itemsList.append(params)
        
        return itemsList
    
    def getList(self, cItem):
        printDBG("CanlitvliveIoApi.getList")
        itemsList = []
        
        category = cItem.get('priv_category', None)
        if category == None:
            itemsList.append({'name':cItem['name'], 'priv_category':'tv',    'type':'dir', 'title':_('TV'),    'url':self.MAIN_URL_TV,    'desc':self.MAIN_URL_TV,    'icon':self.DEFAULT_ICON_URL})
            itemsList.append({'name':cItem['name'], 'priv_category':'radio', 'type':'dir', 'title':_('RADIO'), 'url':self.MAIN_URL_RADIO, 'desc':self.MAIN_URL_RADIO, 'icon':self.DEFAULT_ICON_URL})
            return itemsList
        elif category == 'tv':
            self.MAIN_URL = self.MAIN_URL_TV
            return self.getCategories(cItem, 'priv_list_channels')
        elif category == 'radio':
            self.MAIN_URL = self.MAIN_URL_RADIO
            return self.getCategories(cItem, 'priv_list_channels')
        elif category == 'priv_list_channels':
            return self.getChannelsList(cItem)
        
        return itemsList
        
    def getVideoLink(self, cItem):
        printDBG("CanlitvliveIoApi.getVideoLink")
        urlsTab = []
        
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return urlsTab
        
        hlsUrl = self.cm.ph.getSearchGroups(data, '''["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']''', ignoreCase=True)[0]
        printDBG("hlsUrl||||||||||||||||| " + hlsUrl)
        if hlsUrl != '':
            hlsUrl = strwithmeta(hlsUrl, {'User-Agent':self.defaultParams['header']['User-Agent'], 'Referer':cItem['url']})
            urlsTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999)
        
        if 0 == len(urlsTab):
            data = self.cm.ph.getDataBeetwenMarkers(data, '.setup(', ')')[1]
            videoUrl = self.cm.ph.getSearchGroups(data, '''['"]?file['"]?\s*:\s*['"](https?://[^'^"]+?)['"]''')[0]
            if self.cm.isValidUrl(videoUrl):
                videoUrl = strwithmeta(videoUrl, {'User-Agent':self.defaultParams['header']['User-Agent'], 'Referer':cItem['url']})
                urlsTab.append({'name':'direct', 'url':videoUrl})
        return urlsTab
