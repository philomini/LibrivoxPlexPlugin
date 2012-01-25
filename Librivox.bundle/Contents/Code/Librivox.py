"""
The classes in this file contain a representation of librivox metadata so
that the albums and tracks can be processed by the rest of this plugin.
They rely on Plex API functions to do network I/O and XPath processing
to scrape HTML and extract data from XML documents, so this is not a general
purpose library.

In addition to relying on Plex http caching, XML metadata is cached in 
the plugin's Dict so that it won't need to be downloaded multiple times.
"""

import re

METADATA_URL = 'https://catalog.librivox.org/search_xml.php?extended=1&id='
DEFAULT_RSS_URL = 'http://librivox.org/rss/'
Books = {}

title_re = re.compile('(?:(.*?)\. )?"(.*?)(?:, (A|The))?(?: (\\(Version \d+\\)))?".*$')

"""
This acts as a caching factory for books
"""
def GetBook(librivox_id = None, metadata= None):
    global Books

    if librivox_id is None and metadata is None:
        raise(Exception("Require at least one of librivox_id or metadata"))

    if librivox_id is None:
        librivox_id = metadata.xpath(".//id")[0].text

    if librivox_id not in Dict and metadata is not None:
        Dict[librivox_id] = XML.StringFromElement(metadata)

    if librivox_id not in Books:
        Books[librivox_id] = Book(librivox_id, metadata)

    return Books[librivox_id]

class Book():
    """
    The Librivox.Book class lazily evaluates metadata as requested by its 
    accessors. It is able to derive all of its information from a single datum
    (the librivox id attribute). As a convenience, the constructor can also
    be passed a parsed XML element which contains the book element of a
    librivox XML search result, which is what the librivox id is resolved
    to anyway.

    The metadata parsing code is a little complicated, because it seems that
    not all of the interesting bits of metadata are available in each
    representation of the audiobooks available from the website. In particular,
    I've not found any way to locate book-related art or track titles aside
    from scraping the page pointed to by the xml search result's <url> element.
    """
    def __init__(self, librivox_id=None, metadata=None):
        if librivox_id is None and metadata is None:
            raise(Exception("Require at least one of librivox_id or metadata"))

        if librivox_id is None:
            librivox_id = metadata.xpath(".//id")[0].text

        if librivox_id not in Dict and metadata is not None:
            Dict[librivox_id] = XML.StringFromElement(metadata)


        self.librivox_id = librivox_id
        self.metadata = metadata
        self.description = None
        self.page = None
        self.feed = None
        self.title = None
        self.author = None
        self.genres = None
        self.thumb = None
        self.art = None

        self.tracks = None

    def load_metadata(self):
        """
        The metadata here is the book element in the extended form of the XML
        search result. It contains links to the various pages (html and rss)
        related to the audiobook as well as descriptive information.
        """
        if self.metadata is None:
            if self.librivox_id not in Dict:
                element = XML.ElementFromURL(METADATA_URL + self.librivox_id)
                xmls = XML.StringFromElement(element.xpath("book")[0])
                Dict[self.librivox_id] = xmls
                self.metadata = element
                return
            self.metadata = XML.ElementFromString(Dict[self.librivox_id])

    def load_page(self):
        """
        The page here is the html document pointed to by the librivox metadata
        above. It probably contains more information than either the feed or the
        metadata but is trickier to parse for a couple of reasons. It's html,
        and some of the data is embedded in text sections; and different
        generations of librivox books use different microformats to include
        information in the HTML.

        As far as I can tell, this is the only place where you can get the
        track titles (important for compilations) and art. The latter
        are available on archive.org, but aren't indexed as of 2012-01-24
        """
        if self.page is None:
            self.load_metadata()
            self.page = HTML.ElementFromURL(self.metadata.xpath(".//url")[0].text)

    def load_feed(self):
        """
        The feed here is the rss document pointed to by the librivox metadata
        above. It contains links to only the 64kbps mp3 files (not the 128kpbs
        ones or ogg vorbis which are hosted on archive.org), as well as
        there duration and some potentially interesting itunes podcasting tags.

        Unfortunately, the art in referenced in the feed is generic librivox
        art and not book-specific.
        """
        if self.feed is None:
            self.load_metadata()

            feed_url = self.metadata.xpath(".//rssurl")[0]
            if feed_url is '':
                # https://catalog.librivox.org/search_xml.php?id=5827 has
                # missing rssurl, but http://librivox.org/rss/{librivox_id}
                # works
                feed_url = DEFAULT_RSS_URL + self.librivox_id
            self.feed = HTML.ElementFromURL(feed_url)

    def parse_title(self, title):
        """
        Librivox search results conflate the author and title (as well as other
        bits of metadata) into a single string. This regexp is a bit ad-hoc
        to clean up parts of it. Specifically, it tries to separate author and
        title, keeps (Version x) strings at the end of the title and
        swaps a trailing ", A" or ", The" to the beginning of the
        title. It looks like librivox also encodes the language of the
        recording the title string (eg [Dutch] at the beginning of a name),
        but I'm not sure if that's ad-hoc convention or policy.

        For European names, it might make sense to swap Last, First parts,
        but then again, I'm not sure if multi-author works would confuse
        that, so I'm leaving them alone for now
        """
        m = title_re.match(title)

        author = m.group(1)

        title = m.group(2)
        if m.group(3) is not None:
            title = m.group(3) + " " + title
        if m.group(4) is not None:
            title = title + " " + m.group(4)
        return author, title

    def Title(self):
        if self.title is None:
            self.load_metadata()
            self.author, self.title = self.parse_title(self.metadata.xpath(".//title")[0].text)
        return self.title

    def Description(self):
        if self.description is None:
            self.load_metadata()
            self.description = String.StripTags(
                    self.metadata.xpath(".//description")[0].text)
        return self.description


    def Author(self):
        if self.title is None:
            self.load_metadata()
            self.author, self.title = self.parse_title(self.metadata.xpath(".//title")[0].text)
        return self.author

    def Thumb(self):
        if self.thumb is None:
            try:
                self.load_page()
                self.thumb = self.page.xpath(
                    "//div[@class='cd-cover']//img/@src")[0]
            except:
                self.thumb = R('icon-default.png')
        return self.thumb

    def Art(self):
        if self.art is None:
            try:
                self.load_page()
                self.art = self.page.xpath("//div[@class='cd-cover']//a[contains(@href,'.jpg')]/@href")[0]
            except:
                self.art = R('art-default.png')
        return self.art

    def Tracks(self):
        if self.tracks is None:
            self.load_page()
            self.load_feed()

            res = []
            for track in range(int(self.feed.xpath("count(//item)"))):
                index = track + 1
                nameinfo = None
                try:
                    nameinfo = self.page.xpath("//ul[@id='chapters']/li")[track]
                except:
                    # http://librivox.org/aesops-fables-volume-1-fables-1-25/
                    # is missing the chapters id attribute in the section
                    # containing the mp3 and ogg links, so we'll assume
                    # any ul that has an mp3 in it is ok
                    nameinfo = self.page.xpath(
                        "//ul/li[contains(./a/@href, '.mp3')]")[track]

                res.append(
                    Track(
                        index,
                        self.feed.xpath("//item["+str(index)+"]")[0],
                        nameinfo))
            self.tracks = res
        return self.tracks

media_type_re = re.compile(r"(mp3|ogg vorbis)(?:@(\d+))?")

class Track():
    """
    The Librivox.Track class is less lazy and populates all its metadata
    right away. There is some HTML scaping for determining all of the URLs
    for a recording, as well as pulling out the track title.
    """
    
    def __init__(self, index, feedinfo, nameinfo):
        self.index = index
        self.duration = self.parse_duration(feedinfo)
        self.title = self.parse_title(nameinfo)
        self.urls = self.parse_urls(nameinfo)

    def Index(self):
        return self.index

    def Duration(self):
        return self.duration

    def Title(self):
        return self.title

    def URLs(self):
        return self.urls

    def parse_duration(self, feedinfo):
        duration_string = feedinfo.xpath(".//duration")[0].text
        duration_frags = duration_string.split(":")
        duration_time = 0

        if len(duration_frags) > 2:
            duration_time = int(duration_frags[0]) * 60 * 60 * 1000 + \
                            int(duration_frags[1]) * 60 * 1000 + \
                            int(duration_frags[2]) * 1000
        elif len(duration_frags) > 1:
            duration_time = int(duration_frags[0]) * 60 * 1000 + \
                            int(duration_frags[1]) * 1000
        elif len(duration_frags) > 0:
            duration_time = int(duration_frags[0]) * 1000
        return duration_time
        
    def parse_title(self, nameinfo):
        title = HTML.StringFromElement(nameinfo).replace("\n", " ")
        title = String.StripTags(re.sub("<br( */)?>.*", "", title))
        return title

    def parse_urls(self, nameinfo):
        mediaoffset = 0
        urls = []
        for media in nameinfo.xpath(".//a"):
            match = media_type_re.search(media.text)
            if match is not None:
                mo = {}
                mediaoffset = mediaoffset + 1

                if match.group(2) is not None:
                    mo['bitrate'] = int(match.group(2)) * 1000
                else:
                    mo['bitrate'] = None
                if match.group(1) == 'mp3':
                    mo['codec'] = AudioCodec.MP3
                else:
                    mo['codec'] = None
                mo['url'] = media.xpath("@href")[0]
                urls.append(mo)
        return urls
