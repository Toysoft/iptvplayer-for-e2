# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSearchHistoryHelper, GetDefaultLang, GetLogoDir, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import time
import re
import urllib
import string
import random
import base64
from copy import deepcopy
from hashlib import md5
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
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
config.plugins.iptvplayer.mrpiracy_loginmode = ConfigSelection(default = "simple", choices = [("simple", _("Simple (e-mail, password)")),("advance", _("Advance (cookie item)"))]) 
config.plugins.iptvplayer.mrpiracy_login     = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mrpiracy_password  = ConfigText(default = "", fixed_size = False)

config.plugins.iptvplayer.mrpiracy_cookiename  = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mrpiracy_cookievalue = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mrpiracy_username    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.mrpiracy_userid      = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Login mode"), config.plugins.iptvplayer.mrpiracy_loginmode))
    if config.plugins.iptvplayer.mrpiracy_loginmode.value == 'simple':
        optionList.append(getConfigListEntry('    ' + _("e-mail"), config.plugins.iptvplayer.mrpiracy_login))
        optionList.append(getConfigListEntry('    ' + _("Password"), config.plugins.iptvplayer.mrpiracy_password))
    else:
        optionList.append(getConfigListEntry('    ' + _("Secure cookie name"), config.plugins.iptvplayer.mrpiracy_cookiename))
        optionList.append(getConfigListEntry('    ' + _("Secure cookie value"), config.plugins.iptvplayer.mrpiracy_cookievalue))
        optionList.append(getConfigListEntry('    ' + _("Name"), config.plugins.iptvplayer.mrpiracy_username))
        optionList.append(getConfigListEntry('    ' + _("ID"), config.plugins.iptvplayer.mrpiracy_userid))
    return optionList
###################################################

def gettytul():
    return 'http://mrpiracy.site/'

class MRPiracyGQ(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'mrpiracy.gq', 'cookie':'mrpiracygq.cookie', 'cookie_type':'MozillaCookieJar', 'min_py_ver':(2,7,9)})
        self.DEFAULT_ICON_URL = 'https://pbs.twimg.com/profile_images/790277002544766976/w_TjhbiK.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = None
        self.cacheLinks    = {}
        self.cacheFilters  = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.cookiename  = ''
        self.cookievalue = ''
        self.username    = ''
        self.userid      = ''
        
        self.login    = ''
        self.password = ''
        
        self.loggedIn = False
        
    def selectDomain(self):
        domain = None
        for url in ['http://mrpiracy.site/', 'http://mrpiracy.gq/']:
            sts, data = self.getPage(url)
            if not sts: continue
            tmp = self.cm.ph.getSearchGroups(data, '<a[^>]+?href="(https?://[^"]+?)"[^>]*?>[^>]+?site')[0]
            if self.cm.isValidUrl(tmp):
                domain = tmp
                if not domain.endswith('/'):
                    domain += '/'
                break
        
        printDBG("DOMAN: [%s]" % domain)
            
        if domain == None:
            domain = 'http://v1.mrpiracy.xyz/'
        
        domain = domain.replace('http://', 'https://')
        self.MAIN_URL = domain
    
        self.MAIN_CAT_TAB = [{'category':'list_filters',      'mode':'movie',   'title': 'Movies',       'url':self.getFullUrl('filmes.php') },
                             {'category':'list_filters',      'mode':'serie',   'title': 'TV Shows',     'url':self.getFullUrl('series.php') },
                             {'category':'list_filters',      'mode':'anime',   'title': 'Animes',       'url':self.getFullUrl('animes.php') },
                             
                             {'category':'search',            'title': _('Search'), 'search_item':True,                                    },
                             {'category':'search_history',    'title': _('Search history'),                                                } 
                            ]
    
        
    def getFullUrl(self, url):
        if url.startswith('..'): url = url[2:]
        return CBaseHostClass.getFullUrl(self, url)
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
            
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if sts:
            encoding = self.cm.ph.getDataBeetwenMarkers(data, 'charset=', '"', False)[1]
            if encoding != '':
                try: data = data.decode(encoding).encode('utf-8')
                except Exception: printExc()
        return sts, data
    
    def fillCacheFilters(self, cItem):
        printDBG("MRPiracyGQ.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        def addFilter(data, marker, key, addAny=True, titleBase=''):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''=([0-9]+?)[^0-9]''')[0]
                if value == '': continue
                title = self.cleanHtmlStr(item)
                if titleBase == '': title = title.title()
                self.cacheFilters[key].append({'title':titleBase + title, key:value})
            if len(self.cacheFilters[key]):
                if addAny: self.cacheFilters[key].insert(0, {'title':_('All')})
                self.cacheFiltersKeys.append(key)
        
        # clas
        self.cacheFilters['f_class'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="estado">', 'list"')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<label', '</label>')
        addFilter(tmp, 'e', 'f_class')
        
        # categories
        self.cacheFilters['f_cat'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="genres-caption">', 'list"')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<label', '</label>')
        addFilter(tmp, 'categoria', 'f_cat')
        
        # years
        self.cacheFilters['f_year'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="years-caption">', 'movies-order')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<label', '</label>')
        addFilter(tmp, 'anos', 'f_year')
        
        # sort
        self.cacheFilters['sort_by'] = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '-order"', '-order"')[1]
        printDBG(data)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            key = self.cm.ph.getSearchGroups(item, '\?([^=]+?)=')[0]
            self.cacheFilters['sort_by'].append({'title': self.cleanHtmlStr(item), 'sort_by': key})
        
        # add order to sort_by filter
        orderLen = len(self.cacheFilters['sort_by'])
        for idx in range(orderLen):
            item = deepcopy(self.cacheFilters['sort_by'][idx])
            # desc
            self.cacheFilters['sort_by'][idx].update({'title':'\xe2\x86\x93 ' + self.cacheFilters['sort_by'][idx]['title'], 'order':'2'})
            # asc
            item.update({'title': '\xe2\x86\x91 ' + item['title'], 'order':'1'})
            self.cacheFilters['sort_by'].append(item)
        if len(self.cacheFilters['sort_by']): self.cacheFiltersKeys.append('sort_by')
        
        printDBG(self.cacheFilters)
        
    def listFilters(self, cItem, nextCategory):
        printDBG("MRPiracyGQ.listFilters")
        cItem = dict(cItem)
        
        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0: self.fillCacheFilters(cItem)
        
        if f_idx >= len(self.cacheFiltersKeys): return
        
        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx  == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)
        
    def listItems(self, cItem, nextCategory=None):
        printDBG("MRPiracyGQ.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        
        uriParams = {}
        if page > 1: uriParams['pagina'] = page
        
        for item in [('f_class','e'),('f_cat','categoria'),('f_year','anos')]:
            if item[0] in cItem:
                uriParams[item[1]] = cItem[item[0]]
        
        if 'sort_by' in cItem and 'order' in cItem:
            uriParams[cItem['sort_by']] = cItem['order']
        
        uriParams = urllib.urlencode(uriParams)
        if '?' in url: url += '&' + uriParams
        else: url += '?' + uriParams
        
        sts, data = self.getPage(url)
        if not sts: return
        
        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'pagination-aux', '</div>', False)[1]
        if ('>%s<' % (page+1)) in nextPage: 
            nextPage = True
            m2 = '<div class="pagination-aux">'
        else: 
            nextPage = False
            m2 = '<footer>'
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="movies-list"', m2)[1]
        data = re.split('<div id="movie[0-9]+?"[^>]+?class="item"[^>]*?>', data)
        for item in data:
            item = re.sub('<script.+?</script>', '', item)
            item = item.split('<div class="clear">')
            url  = self.getFullUrl( self.cm.ph.getSearchGroups(item[0], 'href="([^"]+?)"')[0] )
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullUrl( self.cm.ph.getSearchGroups(item[0], 'src="([^"]+?)"')[0] )
            title = self.cleanHtmlStr( item[0] )
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[0], '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[0], '''title=['"]([^'^"]+?)['"]''')[0])
            descTab = []
            try:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<div', '</div>')
                tmp.insert(0, self.cleanHtmlStr(item[2]))
                descTab.append('[/br]'.join( [self.cleanHtmlStr(x) for x in tmp]))
                descTab.append(self.cleanHtmlStr(item[3]))
            except Exception: printExc()

            params = {'good_for_fav': True, 'title':title, 'url':url, 'desc':'[/br]'.join(descTab), 'info_url':url, 'icon':icon}
            if '/filme.php' in url:
                self.addVideo(params)
            else:
                params['category'] = nextCategory
                params2 = dict(cItem)
                params2.update(params)
                self.addDir(params2)
        
        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title':_("Next page"), 'page':page+1})
            self.addDir(params)
            
    def listSeasons(self, cItem, nextCategory='list_episodes'):
        printDBG("MRPiracyGQ.listSeasons")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        seriesTitle = self.cleanHtmlStr( self.cm.ph.getSearchGroups(data, '<a[^>]+?class="movie-name"[^>]*?>([^<]+?)</a>')[0] )
        if seriesTitle != '': seriesTitle = cItem['title']
        
        seasonLabel = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="season-Label">', '</div>', False)[1])
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="seasonsLeftArrow"', '<div id="seasonsRightArrow"')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>', withMarkers=True)
        for item in data:
            num = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = '%s: %s %s' % (seriesTitle, seasonLabel, num)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category':nextCategory, 'title':title, 'url':url, 's_num':num, 's_title':seriesTitle})
            self.addDir(params)
    
    def listEpisodes(self, cItem):
        printDBG("MRPiracyGQ.listEpisodes")
        
        sNum = cItem.get('s_num', '')
        seriesTitle = cItem.get('s_title', '')
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="episodes-list"', '<div class="season-info">')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>', withMarkers=True)
        for item in data:
            eNum = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="episode-number">', '</div>')[1])
            if eNum != '': eNum = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0])
            url  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0].split('#')[0])
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=["']([^"^']+?)["']''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="semlegendaimg">', '</div>')[1])
            title = '%s: s%se%s %s' % (seriesTitle, sNum.zfill(2), eNum.zfill(2), title)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':title, 'url':url, 'icon':icon})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MRPiracyGQ.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if searchType == 'movie':
            type = 'procurarf'
        elif searchType == 'serie':
            type = 'procurars'
        elif searchType == 'anime':
            type = 'procuraranime'
        else:
            printDBG("MRPiracyGQ.listSearchResul - wrong search type")
            return
        
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('%s.php?&searchBox=' % type) + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'list_seasons')
        
    def getLinksForVideo(self, cItem):
        printDBG("MRPiracyGQ.getLinksForVideo [%s]" % cItem)
        urlTab = self.cacheLinks.get(cItem['url'], [])
        
        if len(urlTab): return urlTab
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return urlTab
        
        trailerUrl = self.cm.ph.getSearchGroups(data, '''trailer\(\s*["'](https?://youtube.com/[^"^']+?)["']''')[0]
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="deleted">', '</center>')[1]
        
        errorMsg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h2', '</h2>')[1])
        errorMsg += ' ' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<p', '</p>')[1])
        SetIPTVPlayerLastHostError(errorMsg)
        
        token = self.cm.ph.getSearchGroups(data, '''var\s+form_data\s*=\s*['"]([^'^"]+?)['"]''')[0]
        linksData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a id="sv', '</a>')
        linksData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<span id="sv', '</span>'))
        for item in linksData:
            playerData = self.cm.ph.getDataBeetwenMarkers(item, 'player(', ')', False)[1]
            playerData = re.sub('''["'\s]''', '', playerData).split(',')
            if len(playerData) != 2: continue
            name = self.cm.ph.getSearchGroups(item, '''src=["']([^"^']+?)["']''')[0].split('/')[-1].replace('.png', '').title()
            playerData.append(token)
            playerData.append(cItem['url'])
            urlTab.append({'name':name, 'url':'|'.join(playerData), 'need_resolve':1})
        
        if self.cm.isValidUrl(trailerUrl):
            urlTab.append({'name':_('Trailer'), 'url':trailerUrl, 'need_resolve':1})
        
        if len(urlTab):
            self.cacheLinks[cItem['url']] = urlTab
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("MRPiracyGQ.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        
        playerData = videoUrl.split('|')
        url = playerData[-1]
        
        if not self.cm.isValidUrl(url) or len(playerData) != 4:
            return []
        
        if 'filme.php' in url:
            type = 'filme'
        elif 'series.php' in url:
            type = 'serie'
        else:
            type = 'serie'
        
        sts, data = self.getPage(url)
        if not sts: return urlTab
        
        token = self.cm.ph.getSearchGroups(data, '''var\s+[^=^\(^\)^\{^\}]+?=\s*['"]([0-9a-fA-F]+?)['"]''')[0]
        data  = self.cm.ph.getDataBeetwenMarkers(data, 'player(', '</script>')[1]
        data  = self.cm.ph.getDataBeetwenMarkers(data, '<script', '</script>', False)[1]
        data  = self.cm.ph.getDataBeetwenMarkers(data, '[', ']', False)[1]
        data  = re.compile('"([^"]*?)"').findall(data)
        
        uriTmp  = [] 
        canBeAdded = False
        try:
            for item in data:
                item = item.decode('string_escape').encode('utf-8')
                if '_player_' in item:
                    canBeAdded = True
                if canBeAdded: uriTmp.append(item)
        except Exception:
            uriTmp = []
            printExc()
        
        if len(uriTmp) >= 3:
            url = self.getFullUrl(uriTmp[0] + playerData[1] + uriTmp[1] + playerData[0] + uriTmp[2] + token)
        else:
            url = self.getFullUrl('%s_player_include_welele.php?imdb=%s&p=%s&token=%s' % (type, playerData[1], playerData[0], token))
        
        sts, data = self.getPage(url)
        if not sts: return urlTab
        
        SetIPTVPlayerLastHostError(self.cleanHtmlStr(data))
        
        printDBG("+++++++++++++++++++++++++")
        printDBG(data)
        printDBG("+++++++++++++++++++++++++")
        
        subTrack = self.cm.ph.getSearchGroups(data, '''subs\:([^'^"]+?\.srt)''')[0]
        if subTrack == '': subTrack = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?/subs/[^'^"]*?\.srt)['"]''')[0]
        subTrack = self.getFullUrl(subTrack)
        
        url = self.cm.ph.getSearchGroups(data, '''src=["']([^"^']+?)["']''')[0]
        if url == '': url = self.cm.ph.getSearchGroups(data, '''['"]?link['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
        url = self.getFullUrl(url)
        
        if self.up.getDomain(url) in self.getMainUrl():
            sts, data = self.getPage(url)
            if not sts: return urlTab
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=["']([^"^']+?)["']''')[0])
        else:
            videoUrl = url
        
        urlTab = self.up.getVideoLinkExt(videoUrl)
        if self.cm.isValidUrl(subTrack):
            format = subTrack[-3:]
            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'])
                if 'external_sub_tracks' not in urlTab[idx]['url'].meta: urlTab[idx]['url'].meta['external_sub_tracks'] = []
                urlTab[idx]['url'].meta['external_sub_tracks'].append({'title':'', 'url':subTrack, 'lang':'pt', 'format':format})
        
        return urlTab
    
    def getFavouriteData(self, cItem):
        printDBG('MRPiracyGQ.getFavouriteData')
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'desc':cItem['desc'], 'icon':cItem['icon']}
        return json.dumps(params) 
        
    def getLinksForFavourite(self, fav_data):
        printDBG('MRPiracyGQ.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MRPiracyGQ.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
        
    def getArticleContent(self, cItem):
        printDBG("MRPiracyGQ.getArticleContent [%s]" % cItem)
        retTab = []
        
        sts, data = self.getPage(cItem.get('url', ''))
        if not sts: return retTab
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<[^>]+?id="movie-synopsis"[^>]*?>'), re.compile('</div>'))[1])
        if desc == '': desc  = self.cleanHtmlStr( self.cm.ph.getSearchGroups(data, '<meta property="og:description"[^>]+?content="([^"]+?)"')[0] )
        
        title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0] )
        icon  = self.getFullUrl( self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0] )
        
        if title == '': title = cItem['title']
        if desc == '':  title = cItem['desc']
        if icon == '':  title = cItem['icon']
        
        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-detailed-info">', '<div class="clear">', False)[1] 
        descTabMap = {"genre":         "genre",
                      "year":          "year",
                      "original-name": "alternate_title"}
        
        otherInfo = {}
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(descData, '<span', '</span>')
        for item in tmp:
            key = self.cm.ph.getSearchGroups(item, '''class=['"]([^'^"]+?)['"]''')[0]
            if key in descTabMap:
                try: otherInfo[descTabMap[key]] = self.cleanHtmlStr(item)
                except Exception: continue
                
        status = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, 'Estado:', '</span>', False)[1])
        if status != '': otherInfo['status'] = status
        
        year = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(descData, '<span class="year">', '<span class="', False)[1], '[^0-9]([0-9]+?)[^0-9]')[0]
        if year != '': otherInfo['year'] = year
        
        director = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(descData, re.compile('Realizador:\s*</span>'), re.compile('</span>'), False)[1])
        if director != '': otherInfo['director'] = director
        
        creator = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(descData, re.compile('Criador:\s*</span>'), re.compile('</span>'), False)[1])
        if creator != '': otherInfo['creator'] = creator
        
        actors = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(descData, re.compile('Elenco:\s*</span>'), re.compile('</span>'), False)[1])
        if actors != '': otherInfo['actors'] = actors
        
        imdb_rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<div class="imdb-rate">', '</span>', False)[1])
        if imdb_rating != '': otherInfo['imdb_rating'] = imdb_rating
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
    
    def tryTologin(self):
        printDBG('tryTologin start')
        connFailed = _('Connection to server failed!')
        
        # try to log on using user and password fields
        if 'simple' == config.plugins.iptvplayer.mrpiracy_loginmode.value:
            sts, data = self.getPage(self.getMainUrl())
            if not sts: return False, connFailed 
            
            if 'logout.php' in data:
                return True, 'OK'
                
            login  = config.plugins.iptvplayer.mrpiracy_login.value
            passwd = config.plugins.iptvplayer.mrpiracy_password.value
            
            post_data = {'email':login, 'password':passwd, 'lembrar_senha':'lembrar'}
            
            sitekey = self.cm.ph.getSearchGroups(data, 'fallback\?k=([^"]+?)"')[0]
            if sitekey != '':
                recaptcha = UnCaptchaReCaptcha(lang=GetDefaultLang())
                recaptcha.HTTP_HEADER['Referer'] = self.getMainUrl()
                recaptcha.HTTP_HEADER['User-Agent'] = self.USER_AGENT
                token = recaptcha.processCaptcha(sitekey)
                if token == '':
                    return False, 'NOT OK'
                post_data.update({'g-recaptcha-response':token, 'g-recaptcha-response2':token, 'url':'/'})
            
            data  = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>', False)[1]
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER)
            params['header']['Referer'] = self.getMainUrl()
            
            # login
            sts, data = self.cm.getPage(url, params, post_data)
            if not sts: return False, connFailed
        else:
            cookie = {}
            try: cookie[config.plugins.iptvplayer.mrpiracy_cookiename.value] = urllib.unquote(config.plugins.iptvplayer.mrpiracy_cookievalue.value)
            except Exception: cookie[config.plugins.iptvplayer.mrpiracy_cookiename.value] = config.plugins.iptvplayer.mrpiracy_cookievalue.value
            cookie['nome'] = config.plugins.iptvplayer.mrpiracy_username.value
            cookie['id_utilizador'] = config.plugins.iptvplayer.mrpiracy_userid.value
            cookie['admin'] = config.plugins.iptvplayer.mrpiracy_userid.value
            self.defaultParams['cookie_items'] = cookie
            
            #rm(self.COOKIE_FILE)
            sts, data = self.getPage(self.getMainUrl())
            if not sts: return False, connFailed 
        
        if 'logout.php' in data:
            return True, 'OK'
        else:
            return False, 'NOT OK'
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        if self.MAIN_URL == None:
            self.selectDomain()
        
        if ('simple' != config.plugins.iptvplayer.mrpiracy_loginmode.value and \
            (self.cookiename != config.plugins.iptvplayer.mrpiracy_cookiename.value or \
             self.cookievalue != config.plugins.iptvplayer.mrpiracy_cookievalue.value or \
             self.username != config.plugins.iptvplayer.mrpiracy_username.value or \
             self.userid != config.plugins.iptvplayer.mrpiracy_userid.value) and \
           '' != config.plugins.iptvplayer.mrpiracy_cookiename.value.strip() and \
           '' != config.plugins.iptvplayer.mrpiracy_cookievalue.value.strip() and \
           '' != config.plugins.iptvplayer.mrpiracy_username.value.strip() and \
           '' != config.plugins.iptvplayer.mrpiracy_userid.value.strip()) or \
           ('simple' == config.plugins.iptvplayer.mrpiracy_loginmode.value and \
            (self.login != config.plugins.iptvplayer.mrpiracy_login.value or \
             self.password != config.plugins.iptvplayer.mrpiracy_password.value) and \
            '' != config.plugins.iptvplayer.mrpiracy_login.value.strip() and \
            '' != config.plugins.iptvplayer.mrpiracy_password.value.strip()):
           
            self.loggedIn, msg = self.tryTologin()
            if not self.loggedIn:
                if 'simple' == config.plugins.iptvplayer.mrpiracy_loginmode.value:
                    userName = config.plugins.iptvplayer.mrpiracy_login.value
                else:
                    userName = config.plugins.iptvplayer.mrpiracy_username.value
                self.sessionEx.open(MessageBox, 'Login failed for user "%s".' % userName, type = MessageBox.TYPE_INFO, timeout = 10 )
            elif 'simple' != config.plugins.iptvplayer.mrpiracy_loginmode.value:
                self.cookiename  = config.plugins.iptvplayer.mrpiracy_cookiename.value
                self.cookievalue = config.plugins.iptvplayer.mrpiracy_cookievalue.value 
                self.username    = config.plugins.iptvplayer.mrpiracy_username.value 
                self.userid      = config.plugins.iptvplayer.mrpiracy_userid.value
            else:
                self.loogin   = config.plugins.iptvplayer.mrpiracy_login.value
                self.password = config.plugins.iptvplayer.mrpiracy_password.value
        elif ('simple' != config.plugins.iptvplayer.mrpiracy_loginmode.value and \
           ('' == config.plugins.iptvplayer.mrpiracy_cookiename.value.strip() or \
           '' == config.plugins.iptvplayer.mrpiracy_cookievalue.value.strip() or \
           '' == config.plugins.iptvplayer.mrpiracy_username.value.strip() or \
           '' == config.plugins.iptvplayer.mrpiracy_userid.value.strip())) or \
           ('simple' == config.plugins.iptvplayer.mrpiracy_loginmode.value and \
            ('' == config.plugins.iptvplayer.mrpiracy_login.value.strip() or \
            '' == config.plugins.iptvplayer.mrpiracy_password.value.strip())):
           self.sessionEx.open(MessageBox, 'Access to this service requires login.\nPlease register on the site \"%s\". Then log in and then put your login data in the host configuration under blue button.' % self.getMainUrl(), type=MessageBox.TYPE_INFO, timeout=20 )
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            if 'simple' == config.plugins.iptvplayer.mrpiracy_loginmode.value and \
               (config.plugins.iptvplayer.mrpiracy_login.value == '' or config.plugins.iptvplayer.mrpiracy_password.value == ''):
                rm(self.COOKIE_FILE)
            elif 'simple' != config.plugins.iptvplayer.mrpiracy_loginmode.value and \
               (self.cookiename == '' or self.cookievalue == '' or self.username == '' or self.userid == ''):
                rm(self.COOKIE_FILE)
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MRPiracyGQ(), True, [])
        
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"),  "movie"))
        searchTypesOptions.append((_("TV Show"), "serie"))
        searchTypesOptions.append((_("Anime"),   "anime"))
        return searchTypesOptions
        
    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'list_episodes' and cItem['category'] != 'list_seasons':
            return False
        return True
    
    