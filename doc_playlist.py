"""
This script lists the playlists from the libary XML exported from Rekordbox and
prompts the user to select a specific playlist. The comments and hot cue details 
for each track in the playlist will be printed.

Tested with library XML exported from Rekordbox 6.80 on Windows.
"""
import argparse
import pathlib

import sys
from xml.dom.minidom import parse

class LibraryReader:
    """
    LibraryReader parses the Rekordbox library XML file to extract track and
    playlist info
    """
    # TODO: Test vs large Rekordbox libraries of 10K + tracks
    def __init__(self, filename):
        self.filename = filename

    def load(self):
        try:
            f = open(self.filename, "r")
        except FileNotFoundError:
            sys.stderr.write("Library file %s not found\n" % self.filename)
            return False
        except Exception as e:
            sys.stderr.write("Library file %s cannot be read, exception: %s\n" %
                    (self.filename, e))
            return False

        # Parse library XML file
        try:
            doc = parse(f)
        except Exception as e:
            sys.stderr.write("Library file %s cannot be parsed as XML, exception: %s\n" %
                (self.filename, e))
        finally:
            f.close()

        # Look for COLLECTION which contains a list of TRACK
        elems = doc.getElementsByTagName("COLLECTION")
        if len(elems) != 1:
            sys.stderr.write("Library file cannot be parsed for COLLECTION tag\n")
            return False

        collection = elems[0]
        self.tracks = collection.getElementsByTagName("TRACK")


        # Look for PLAYLISTS which contains a list of NODE that represent
        # actual playlists
        elems = doc.getElementsByTagName("PLAYLISTS")
        if len(elems) != 1:
            sys.stderr.write("Library file cannot be parsed for PLAYLIST tag\n")
            return False

        playlist_root = elems[0]
        elems = playlist_root.getElementsByTagName("NODE")

        self.playlists = []
        for pl in elems:
            # Type 0 playlists are just folders of playlists, we only care
            # about Type 1 playlists which contain actual tracks
            if pl.getAttribute("Type") != "1":
                continue

            self.playlists.append(Playlist(pl))

        if len(self.playlists) == 0:
            sys.stderr.write("Library file contains 0 playlists\n")
            return False

        return True

    def generateDocs(self, playlist_id):
        """
        Print playlist info and tracklist
        """
        if playlist_id < 0:
            return False

        if playlist_id >= len(self.playlists):
            return False

        pl = self.playlists[playlist_id]
        print(pl.generateInfo(self))
        print(pl.generateTracklist(self))

    def findTrack(self, track_id):
        """
        Enumerate track elements to find one with TrackID attribute that
        matches the specified track_id string
        """
        # TODO: Probably a faster way to do this than enumerating through all
        # tracks
        for t in self.tracks:
            if t.getAttribute("TrackID") == track_id:
                return Track(t)
        return None

class Playlist:
    """
    Playlist represents a playlist and associated tracks
    """
    def __init__(self, elem):
        self.name = elem.getAttribute("Name")

        # Each playlist contains TRACK tags which correspond to the ordered
        # sequence of tracks in the playlist
        track_elems = elem.getElementsByTagName("TRACK")
        self.tracks = []

        # Key attribute in TRACK tag maps to TrackID for TRACK tags in
        # COLLECTION
        for t in track_elems:
            self.tracks.append(t.getAttribute("Key"))

    def generateInfo(self, lib):
        """
        Generate information for each track with commments and hotcue info
        """
        doc = "Track Info\n----------\n"
        tracks = self.tracks
        for t in self.tracks:
            track = lib.findTrack(t)
            if track is not None:
                doc += str(track)
        return doc

    def generateTracklist(self, lib):
        """
        Generate just artist and track title as a basic tracklist
        """
        tlist = "Tracklist\n---------\n"
        tracks = self.tracks
        for i, t in enumerate(self.tracks):
            track = lib.findTrack(t)
            if track is not None:
                tlist += "%s - %s\n" % (track.artist, track.title)
        return tlist

class Track:
    """
    Track represents a single track with associated hotcues
    """
    def __init__(self, elem):
        self.artist = elem.getAttribute("Artist")
        self.title = elem.getAttribute("Name")
        self.comment = elem.getAttribute("Comments")
        self.hotcues = []

        hc_elems = elem.getElementsByTagName("POSITION_MARK")
        for hc in hc_elems:
            self.hotcues.append(HotCue(hc))

        # Sort hotcues in ascending order as they are saved by Rekordbox in
        # order of creation?
        self.hotcues.sort(key=lambda hc: hc.letter)

    def __str__(self):
        hotcues_str = "".join("  - %s" % hc for hc in self.hotcues)
        return "%s - %s\n* Comments: %s\n* Hot Cues\n%s\n" % \
            (self.artist, self.title, self.comment, hotcues_str)

class HotCue:
    """
    HotCue represents a single hot cue
    """
    def __init__(self, elem):
        self.letter = chr(int(elem.getAttribute("Num")) + ord("A"))
        self.comment = elem.getAttribute("Name")
        self.start_time = self.convert_time(elem.getAttribute("Start"))

        # TODO: Not sure what Type 4 is, looks like only used for loops
        if elem.getAttribute("Type") == "4":
            self.is_loop = True
            self.end_time = self.convert_time(elem.getAttribute("End"))
        else:
            self.is_loop = False
            self.end_time = self.start_time

    def convert_time(self, s_time):
        """
        Convert time in default sec format to mins and secs for easier reference
        """
        temp_time = float(s_time)
        temp_mins = int(temp_time/60)
        temp_secs = int(temp_time) % 60
        tokens = s_time.split(".")
        if len(tokens) == 2:
            temp_millis = tokens[1]
        else:
            temp_millis = ".000"

        return "%02d:%02d.%s" % (temp_mins, temp_secs, temp_millis)

    def __str__(self):
        if self.is_loop:
            return "%s: %s (%s - %s)\n" % \
                (self.letter, self.comment, self.start_time, self.end_time)
        else:
            return "%s: %s (%s)\n" % \
                (self.letter, self.comment, self.start_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="Prints track info and hot cues for a Rekordbox playlist")
    parser.add_argument('filename', type=pathlib.Path,
            help="Rekordbox Library exported as XML file")
    args = parser.parse_args()

    lib = LibraryReader(args.filename)
    if not lib.load():
        exit()

    # Print list of playlists
    print("\nID: Title (Track Count)")
    for i, pl in enumerate(lib.playlists):
        print("%003d: %s (%d)" % (i + 1, pl.name, len(pl.tracks)))

    # Print prompt
    playlist_id = -1
    while(True):
        playlist_id = input("\nPlease enter playlist ID or 'q' to quit: ")

        if playlist_id == "q":
            exit()

        try:
            playlist_id = int(playlist_id)
        except ValueError:
            print("Invalid ID. Please retry!")
            continue

        if playlist_id <= 0 or playlist_id > len(lib.playlists):
            print("Invalid ID. Please retry!")
            continue

        playlist_id -= 1
        break

    print("\n")

    # Generate docs for selected playlist
    lib.generateDocs(playlist_id)
