# Librivox plugin for Plex media server
#
# This plugin provides searching by title, author, and general keyword
# searching, as well as managment of a simple library of saved audiobook
# metadata for returning to books
#
# All of the metadata scraping/parsing occurs in the classes in the Librivox
# module, this code manages the interface. The librivox search service links
# in to the AudioBookTracks method via a plex route to hand things off
# to this part of the plugin

import Librivox

SEARCH_URL = 'https://catalog.librivox.org/search_xml.php?extended=1&'
SAVED_BOOKS_KEY = 'saved-books'

def Start():
    Plugin.AddPrefixHandler('/music/librivox', MainMenu, 'Librivox', 'icon-default.png', 'art-default.jpg')
    Plugin.AddViewGroup("InfoList", viewMode="InfoList", mediaType="items")
    Plugin.AddViewGroup("List", viewMode="List", mediaType="items")
    ObjectContainer.content = 'Items'
    ObjectContainer.art = R('art-default.jpg')
    DirectoryObject.thumb=R('icon-default.png')
    DirectoryObject.art=R('art-default.png')
    PopupDirectoryObject.thumb=R('icon-default.png')
    PopupDirectoryObject.art=R('art-default.png')
    InputDirectoryObject.thumb=R('icon-default.png')
    InputDirectoryObject.art=R('art-default.png')
    PrefsObject.thumb=R('icon-default.png')
    PrefsObject.art=R('art-default.png')
    HTTP.CacheTime = CACHE_1DAY

    if not SAVED_BOOKS_KEY in Dict:
        Dict[SAVED_BOOKS_KEY] = []

def MainMenu():
    oc = ObjectContainer(title1 = L("Librivox"))

    oc.add(InputDirectoryObject(
        key = Callback(LibrivoxSearchTitle),
        title = L('Title...'),
        summary = L('Search for audiobooks by title'),
        prompt = L('Title Keyword')))

    oc.add(InputDirectoryObject(
        key = Callback(LibrivoxSearchAuthors),
        title = L('Author...'),
        summary = L('Search for audiobooks by author'),
        prompt = L('Author Keyword')))

    oc.add(InputDirectoryObject(
        key = Callback(LibrivoxSearchGeneral),
        title = 'Search...',
        summary = L('Search for audiobooks'),
        prompt = L('Keyword')))

    oc.add(DirectoryObject(
        key = Callback(MyLibrary),
        title = L('My Library')))

    oc.add(PrefsObject(
        title = L('Preferences...')))

    return oc

def LibrivoxSearch(querytype, query, pagenumber=0):
    oc = ObjectContainer(title1 = L('Search Results'))
    pagesize = int(Prefs['pagesize'])

    results = XML.ElementFromURL(SEARCH_URL + querytype + "=" + query)

    resnum = -1
    for book in results.xpath("//book"):
        resnum = resnum + 1
        if resnum < (pagenumber * pagesize):
            continue
        if resnum >= ((pagenumber+1) * pagesize):
            oc.add(
                DirectoryObject(
                    key = Callback(LibrivoxSearch, querytype=querytype, query=query, pagenumber=pagenumber+1),
                    title = L("More...")))
            break

        book_object = Librivox.GetBook(metadata=book)

        oc.add(
            DirectoryObject(
                key = Callback(AudioBookTracks, librivox_id=book_object.librivox_id),
                title = book_object.Title(),
                summary = book_object.Description(),
                art = Callback(Art, librivox_id=book_object.librivox_id),
                thumb = Callback(Thumb, librivox_id=book_object.librivox_id)))
        book_object = None
    return oc

def Thumb(librivox_id):
    try:
        return Redirect(Librivox.GetBook(librivox_id).Thumb())
    except:
        return R('icon-default.png')

def Art(librivox_id):
    try:
        return Redirect(Librivox.GetBook(librivox_id).Thumb())
    except:
        return R('art-default.png')

def LibrivoxSearchTitle(query):
    return LibrivoxSearch("title", query)

def LibrivoxSearchAuthors(query):
    return LibrivoxSearch("author", query)

def LibrivoxSearchGeneral(query):
    return LibrivoxSearch("simple", query)

@route("/music/librivox/{librivox_id}/tracks")
def AudioBookTracks(librivox_id, replace_parent = False):
    Log("Generating tracks for book: " + librivox_id)

    book = Librivox.GetBook(librivox_id)

    ret = ObjectContainer(
        title1 = book.Title(),
        title2 = book.Author(),
        art = book.Art(),
        replace_parent = replace_parent)

    for track in book.Tracks():
        link = track.URLs()[0]['url']
        ret.add(
            TrackObject(
                index = track.Index(),
                key = link,
                rating_key = link,
                title = track.Title(),
                duration = track.Duration(),
                album = book.Title()))

    if librivox_id not in Dict[SAVED_BOOKS_KEY]:
        ret.add(
            DirectoryObject(
                key = Callback(AddToLibrary, librivox_id=librivox_id),
                title = L('Add to Library')))
    else:
        ret.add(
            DirectoryObject(
                key = Callback(RemoveFromLibrary, librivox_id=librivox_id),
                title = L('Remove from Library')))
            
    return ret

def AddToLibrary(librivox_id):
    if SAVED_BOOKS_KEY not in Dict:
        Dict[SAVED_BOOKS_KEY] = []

    library = Dict[SAVED_BOOKS_KEY]
    library.append(librivox_id)

    Dict[SAVED_BOOKS_KEY] = library
    Dict.Save()

    return AudioBookTracks(librivox_id, True)

def RemoveFromLibrary(librivox_id):
    if SAVED_BOOKS_KEY not in Dict:
        Dict[SAVED_BOOKS_KEY] = []

    library = [(bookid) for bookid in Dict[SAVED_BOOKS_KEY] \
        if(bookid != librivox_id)]

    Dict[SAVED_BOOKS_KEY] = library
    Dict.Save()
    return AudioBookTracks(librivox_id, True)

def MyLibrary():
    oc = ObjectContainer(
        title1 = L('My Library'),
        no_cache = True,
        no_history = True)

    for librivox_id in Dict[SAVED_BOOKS_KEY]:
        book_object = Librivox.GetBook(librivox_id = librivox_id)

        oc.add(
            DirectoryObject(
                key = Callback(AudioBookTracks, librivox_id = librivox_id),
                title = book_object.Title(),
                summary = book_object.Description(),
                art = Callback(Art, librivox_id=librivox_id),
                thumb = Callback(Thumb, librivox_id=librivox_id)))

    return oc
