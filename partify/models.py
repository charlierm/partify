# Copyright 2011 Fred Hatfull
#
# This file is part of Partify.
#
# Partify is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Partify is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Partify.  If not, see <http://www.gnu.org/licenses/>.

"""Contains a bunch of SQLAlchemy Models for the data that Partify stores."""

import datetime

from werkzeug.security import generate_password_hash

from database import db

class User(db.Model):
    """Represents a :class:`User` account.

    * **id**: The :class:`User`'s unique ID
    * **name**: The :class:`User`'s display name
    * **username**: The username of the user
    * **password**: The user's password. Stored as a pass generated by
        Werkzeug's generate_password_hash function, which computes an HMAC'd SHA1 hash
        of the input.
    * **privs**: A bitfield of the user's privileges. See :mod:`priv` for definitions
    """
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64))
    username = db.Column(db.String(36), unique=True)
    password = db.Column(db.String(256))
    privs = db.Column(db.Integer)

    def __init__(self, name=None, username=None, password=None):
        self.name = name
        self.username = username
        self.password = generate_password_hash(password)
        self.privs = 0

    def __repr__(self):
        return "<User %r with id %d>" % (self.name, self.id)

class Track(db.Model):
    """Represents track metadata. Used as a foreign key in :class:`PlayQueueEntry` and :class:`PlayHistoryEntry`.
    These should stick around forever and aid in faster metadata retrieval.

    * **id**: The :class:`Track`'s unique ID.
    * **title**: The title of the track.
    * **artist**: The artist that performs the track.
    * **album**: The album the track is found on.
    * **length**: The length of the track in seconds.
    * **date**: The date the track was released.
    * **spotify_url**: The URL of the track in Spotify's catalog
    """
    __tablename__ = "track"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.Text)
    artist = db.Column(db.Text)
    album = db.Column(db.Text)
    length = db.Column(db.Integer)
    date = db.Column(db.Text)
    spotify_url = db.Column(db.Text, unique=True)

    def __repr__(self):
        return "<%r by %r (from %r) - %r>" % (self.title, self.artist, self.album, self.spotify_url)

class PlayQueueEntry(db.Model):
    """Represents a playlist queue entry. These only live until the track they represent is played,
    then they are deleted.

    * **id**: The :class:`PlayQueueEntry`'s unique ID
    * **track, track_id**: The track that is represented by this :class:`PlayQueueEntry`
    * **user, user_id**: The user that queued this track
    * **mpd_id**: The ID used by Mopidy internally for this queue entry
    * **time_added**: The datetime that this track was queued
    * **user_priority**: The priority of this track in the user's queue
    * **playback_priority**: The playback priority in the global queue
    """
    __tablename__ = "play_queue_entry"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))
    track = db.relationship("Track")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship("User")
    mpd_id = db.Column(db.Integer)    # This SHOULD be unique... but since ensuring consistency isn't atomic yet we'll have to just best-effort it
    time_added = db.Column(db.DateTime, default=datetime.datetime.now)
    user_priority = db.Column(db.Integer, default=lambda: (db.session.query(db.func.max(PlayQueueEntry.user_priority)).first()[0] or 0) + 1)
    playback_priority = db.Column(db.BigInteger, default=lambda: (db.session.query(db.func.max(PlayQueueEntry.playback_priority)).first()[0] or 0) + 1)

    def __repr__(self):
        return "<Track %r (MPD %r) queued by %r at %r with priority %r (queue position %r)>" % (self.track, self.mpd_id, self.user, self.time_added, self.user_priority, self.playback_priority)

    def as_dict(self):
        # I'm not sure why a list comprehension into a dict doesn't work here...
        d = {}
        for attr in ('title', 'artist', 'album', 'spotify_url', 'date', 'length'):
            d[attr] = getattr(self.track, attr)
        for attr in ('id', 'mpd_id', 'playback_priority', 'user_priority'):
            d[attr] = getattr(self, attr)
        d['time_added'] = self.time_added.ctime()
        d['user'] = getattr(self.user, 'name', 'Anonymous')
        d['username'] = getattr(self.user, 'username', 'anonymous')
        d['user_id'] = self.user_id
        return d

class PlayHistoryEntry(db.Model):
    """Represents a log entry for a track that was played by a user. Used to generate statistics.
    These should stick around forever.

    * **id**: The :class:`PlayHistoryEntry`'s unique ID
    * **track, track_id**: The :class:`Track` that was played
    * **user, user_id**: The :class:`User` that played the track
    * **time_played**: The datetime that the :class:`Track` started playing
    """
    __tablename__ = "play_history_entry"

    id = db.Column(db.Integer, primary_key = True, autoincrement=True)

    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))
    track = db.relationship("Track")

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship("User")

    time_played = db.Column(db.DateTime, default=datetime.datetime.now)

    def __repr__(self):
        return "<%r played by %r at %r>" % (self.track, self.user, self.time_played)

class Vote(db.Model):
    """Represents a vote that was taken by a user on the track. Once created these should
    not be removed, but instead simply updated.

    * **id**: The :class:`Vote`'s unique ID
    * **user, user_id**: The :class:`User` that made this vote
    * **pqe, pqe_id**: The :class:`PlayQueueEntry` (if any) which the user voted on
    * **phe, phe_id**: The :class:`PlayHistoryEntry` (if any) which the user voted on
    * **direction**: The direction of the vote. Defaults to zero. ``-1`` is down, ``1`` is up.
    """
    __tablename__ = "vote"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship("User")

    pqe_id = db.Column(db.Integer, db.ForeignKey('play_queue_entry.id'))
    pqe = db.relationship('PlayQueueEntry')

    phe_id = db.Column(db.Integer, db.ForeignKey('play_history_entry.id'))
    phe = db.relationship('PlayHistoryEntry')

    direction = db.Column(db.Integer, default=0)
