import math

class CGameHeader(object):
    """A generic header class that contains it's class ID."""
    def __init__(self, id):
        self.id = id


class CGameCtnCollectorList(object):
    """A header that holds a list of CollectorStock's."""
    def __init__(self, id):
        self.id = id
        self.stocks = []


class CollectorStock(object):
    """A header that holds a stock."""
    def __init__(self, block_name, collection, author):
        self.block_name = block_name
        self.collection = collection
        self.author = author


class MapBlock(object):
    """A header that holds information about a specific block contained within the Challenge data."""
    def __init__(self):
        self.name = None
        self.rotation = 0
        self.position = Vector3()
        self.speed = 0
        self.flags = 0
        self.params = 0
        self.skin_author = None
        self.skin = 0

    # 0b1000000000000
    # (flags & 0x1000) != 0     is on terrain
    # (flags & 0x1) != 0        connected once with another RoadMain
    # (flags & 0x2) != 0        connected twice with blocks (curve line)
    # (flags & 0x3) != 0        connected twice with blocks (straight line)
    # (flags & 0x4) != 0        connected three times with blocks
    # (flags & 0x5) != 0        connected four times with blocks
    # 6?
    # (flags & 0x7) == 0        not connected to any blocks
    def __str__(self):
        return (
            'Name: {}\n'
            'Rotation: {}\n'
            'Position: {}\n'
            'Flags: {}\n'
        ).format(self.name, self.rotation, self.position.as_array(), bin(self.flags))

class Vector3(object):
    """The Vector3 class represents a 3D vector, usually read directly from the GBX file."""
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __getitem__(self, key):
        if key == 0:
            return self.x
        elif key == 1:
            return self.y
        elif key == 2:
            return self.z
        return None

    def __eq__(self, other):
        if isinstance(other, list):
            return self.x == other[0] and self.y == other[1] and self.z == other[2]

        return self.x == other.x and self.y == other.y and self.z == other.z

    def as_array(self):
        """Returns the vector as a list.
        
        Returns:
            the vector as a list made of 3 elements
        """
        return [self.x, self.y, self.z]


class CGameChallenge(CGameHeader):
    """A header that contains data related to the CGameChallenge class."""
    def __init__(self, id):
        self.id = id
        self.times = {}
        self.map_uid = None
        self.environment = None
        self.map_author = None
        self.map_name = None
        self.mood = None
        self.env_bg = None
        self.env_author = None
        self.map_size = ()
        self.flags = 0
        self.req_unlock = 0
        self.blocks = []
        self.items = []
        self.password_hash = None
        self.password_crc = None


class CGameBlockItem(CGameHeader):
    """A header that contains data related to the CGameBlockItem class."""
    def __init__(self):
        self.id = id
        self.path = None
        self.collection = None
        self.author = None
        self.waypoint = None
        self.position = Vector3()
        self.rotation = 0.0


class CGameWaypointSpecialProperty(CGameHeader):
    """A header that contains data related to the CGameWaypointSpecialProperty class."""
    def __init__(self, id):
        self.id = id
        self.tag = None
        self.spawn = 0
        self.order = 0


class CGameCommon(CGameHeader):
    """A header that contains data related to the CGameCommon class."""
    def __init__(self, id):
        self.id = id
        self.track_name = None


class CGameReplayRecord(CGameCommon):
    """A header that contains data related to the CGameReplayRecord class."""
    def __init__(self, id):
        self.id = id
        self.track = None
        self.nickname = None
        self.driver_login = None


class CGameGhost(CGameHeader):
    """A header that contains data related to the CGameGhost class."""
    def __init__(self, id):
        self.id = id
        self.records = []
        self.sample_period = None


class CGameCtnGhost(CGameGhost):
    """A header that contains data related to the CGameCtnGhost class."""
    def __init__(self, id):
        self.id = id
        self.race_time = 0
        self.num_respawns = 0
        self.light_trail_color = Vector3()
        self.stunts_score = 0
        self.uid = None
        self.login = None
        self.cp_times = []
        self.control_entries = []
        self.game_version = ''
        self.control_names = []
        self.events_duration = 0
        self.is_maniaplanet = False
        super(CGameCtnGhost, self).__init__(id)

class ControlEntry(object):
    """A header that contains data related to the control entries contained within the CGameCtnGhost class."""
    def __init__(self, time, event_name, enabled, flags):
        self.time = time
        self.event_name = event_name
        self.enabled = enabled
        self.flags = flags

    """Copies the ControlEntry and all of its properties.
    
    Returns:
        the copied ControlEntry 
    """
    def copy(self):
        return ControlEntry(self.time, self.event_name, self.enabled, self.flags)

class GhostSampleRecord(object):
    """A header that contains a single sample out of the ghost data such as position, rotation of the car and more."""
    BLOCK_SIZE_XZ = 32
    BLOCK_SIZE_Y = 8

    def __init__(self, position, angle, axis_heading, axis_pitch, speed, vel_heading, vel_pitch):
        self.position = position
        self.angle = angle
        self.axis_heading = axis_heading
        self.axis_pitch = axis_pitch
        self.speed = speed
        self.vel_heading = vel_heading
        self.vel_pitch = vel_pitch

    @property
    def display_speed(self):
        """Returns the display speed, which would be shown in the race.

        Returns:
            an integer from 0 to 1000 that represents the display speed"""
        if self.speed == 0x8000:
            return 0

        return int(abs(math.exp(self.speed / 1000.0) * 3.6))

    def get_block_position(self, xoff=0, yoff=0, zoff=0):
        """Calculates the block coordinates that the car is currently passing through in this sample record.

        Returns:
            a Vector3 containing the block coordinates
        """
        x = int((self.position.x + xoff) / self.BLOCK_SIZE_XZ)
        y = int((self.position.y + yoff) / self.BLOCK_SIZE_Y)
        z = int((self.position.z + zoff) / self.BLOCK_SIZE_XZ)
        return Vector3(x, y, z)
