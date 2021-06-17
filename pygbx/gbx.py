import logging
from enum import IntEnum

from pygbx.lzo import LZO
import zlib

import pygbx.headers as headers
from pygbx.bytereader import ByteReader

class GbxType(IntEnum):
    """Represents the type of the main or auxiliary class contained within the GBX file.

    Some classes may have a different or multiple ID's, depending on what version of the GBX file is being parsed.
    """
    CHALLENGE = 0x03043000
    CHALLENGE_OLD = 0x24003000
    COLLECTOR_LIST = 0x0301B000
    CHALLENGE_PARAMS = 0x0305B000
    BLOCK_SKIN = 0x03059000
    WAYPOINT_SPECIAL_PROP = 0x0313B000
    ITEM_MODEL = 0x2E002000
    REPLAY_RECORD = 0x03093000
    REPLAY_RECORD_OLD = 0x02407E000
    GAME_GHOST = 0x0303F005
    CTN_GHOST = 0x03092000
    CTN_GHOST_OLD = 0x2401B000
    CTN_COLLECTOR = 0x0301A000
    CTN_OBJECT_INFO = 0x0301C000
    CTN_DECORATION = 0x03038000
    CTN_COLLECTION = 0x03033000
    GAME_SKIN = 0x03031000
    GAME_PLAYER_PROFILE = 0x0308C000
    MW_NOD = 0x01001000
    UNKNOWN = 0x0

class GbxLoadError(Exception):
    """Thrown when the Gbx class fails to parse the provided Gbx object"""
    def __init__(self, message):
        """Initializes the Exception instance with a message.

        Args:
            message (str): the message
        """
        self.message = message


class Gbx(object):
    """The Gbx class provides the main interface for parsing GBX files and retrieving data
    that is contained within these files. The class provides support primarily for parsing Challenges and Replays.
    The class should properly support most TMNF/TMUF files, with support for some TM2 files.

    It is not guaranteed that the class will parse all of the data in a GBX file. If an error is encountered,
    an error will be logged with the logging module, but the class will attempt to read until the end of the file, unless
    the file is not a GBX file, then a GbxLoadError is thrown.

    The class uses the ByteReader class which provides support for reading data types exposed by the GBX file format,
    found on https://wiki.xaseco.org/wiki/GBX.

    If the class does not provide support for reading a chunk you want to specifically read, use find_raw_chunk_id
    to obtain access to a ByteReader with the cursor positioned at the beggining of provided chunk ID.
    """

    def __init__(self, obj):
        """Creates the main Gbx instance from a file path or from bytes object.

        Parses the Gbx file sequentially, reading all supported chunks until no more chunks have
        been found. Parsing can fail depending on the what classes or chunks it contains and what
        version of the GBX file is being parsed. 

        Args:
            obj (str/bytes): a file path to the Gbx file or bytes object containing the Gbx data

        Raises:
            GbxLoadError: raised when the supplied object is not a GBX file or data
        """
        if isinstance(obj, str):
            self.f = open(obj, 'rb')
            self.root_parser = ByteReader(self.f)
        else:
            self.root_parser = ByteReader(obj)

        self.magic = self.root_parser.read(3, '3s')
        if self.magic.decode('utf-8') != 'GBX':
            raise GbxLoadError(f'obj is not a valid Gbx data: magic string is incorrect')
        self.version = self.root_parser.read(2, 'H')
        self.classes = {}
        self.root_classes = {}
        self.positions = {}
        self.__current_class = None
        self.__current_waypoint = None
        self.__replay_header_info = {}

        self.lzo = LZO()

        self.root_parser.skip(3)
        if self.version >= 4:
            self.root_parser.skip(1)

        if self.version >= 3:
            self.class_id = self.root_parser.read_uint32()
            try:
                self.type = GbxType(self.class_id)
            except ValueError:
                self.type = GbxType.UNKNOWN

            if self.version >= 6:
                self._read_user_data()

            self.num_nodes = self.root_parser.read_uint32()

        self.num_external_nodes = self.root_parser.read_uint32()
        if self.num_external_nodes > 0:
            self.root_parser.read_uint32()
            self.__read_sub_folder()
            for node in range(self.num_external_nodes):
                flags = self.root_parser.read_uint32()
                if (flags & 4) == 0:
                    self.root_parser.read_string()
                else:
                    self.root_parser.read_uint32()

                self.root_parser.skip(4)
                if self.version >= 5:
                    self.root_parser.skip(4)

                if (flags & 4) == 0:
                    self.root_parser.skip(4)

        self.root_parser.push_info()
        self.positions['data_size'] = self.root_parser.pop_info()

        uncompressed_size = self.root_parser.read_uint32()
        compressed_size = self.root_parser.read_uint32()
        compressed_data = self.root_parser.read(compressed_size)
        self.data = self.lzo.decompress(compressed_data, uncompressed_size)

        if not self.data:
            raise GbxLoadError(f'data decompression has failed')

        bp = ByteReader(self.data)
        self._read_node(self.class_id, -1, bp)

    def __read_sub_folder(self):
        num_sub_folders = self.root_parser.read_uint32()
        for folder in range(num_sub_folders):
            self.root_parser.read_string()
            self.__read_sub_folder()

    """Finds a raw chunk ID in the file, skipping through any data that does not match the chunk ID provided.

    It is not guaranteed that the chunk found is indeed the desired data, as it could be other unrelated
    chunk that bytes happened to form the chunk ID provided.

    Args:
        chunk_id (int): the chunk ID to search for

    Returns:
        ByteParser with the current position set right after the chunk ID, or None
        if no specified chunk ID was found
    """
    def find_raw_chunk_id(self, chunk_id):
        bp = ByteReader(self.data[:])
        for i in range(len(self.data) - 4):
            bp.pos = i
            if bp.read_uint32() == chunk_id:
                return bp

        return None

    def get_class_by_id(self, class_id):
        """Finds the header that corresponds to the provided class ID.
        
        This is a wrapper around get_classes_by_ids that returns the first
        element if any headers have been found for a single ID. See get_classes_by_ids for more details.

        Args:
            class_id (int): the class ID to be retrieved
        
        Returns:
            a single instance of the header corresponding to the provided class ID
        """
        classes = self.get_classes_by_ids([class_id])
        if len(classes) == 0:
            return None

        return classes[0]

    def get_classes_by_ids(self, class_ids):
        """Retrieves all headers that match any of the class ID's in the provided array.

        Searches through the list of parsed headers and returns an array of headers that match
        any of the provided ID's in the array. See GbxType for predefined class ID's that are supported.

        Args:
            class_ids (list): the class ID's that have to be matched

        Returns:
            a list of matched headers
        """        
        classes = []
        for cl in list(self.classes.values()) + list(self.root_classes.values()):
            if cl.id in class_ids:
                classes.append(cl)

        return classes

    def _read_user_data(self):
        entries = {}

        self.root_parser.push_info()
        self.user_data_size = self.root_parser.read_uint32()
        self.positions['user_data_size'] = self.root_parser.pop_info()

        user_data_pos = self.root_parser.pos
        num_chunks = self.root_parser.read_uint32()
        for _ in range(num_chunks):
            if self.root_parser.pos >= self.root_parser.size - 1:
                self.root_parser.pos = user_data_pos + self.user_data_size
                return

            cid = self.root_parser.read_uint32()
            self.root_parser.push_info()
            size = self.root_parser.read_uint32()
            self.positions[str(cid)] = self.root_parser.pop_info()
            entries[cid] = size

        for cid, size in entries.items():
            self._read_header_entry(cid, size)

        self.root_parser.pos = user_data_pos + self.user_data_size

    def _read_header_entry(self, cid, size):
        if cid == 0x03043002 or cid == 0x24003002:
            version = self.root_parser.read_byte()
            if version < 3:
                for _ in range(3):
                    self.root_parser.read_string_lookback()
                self.root_parser.read_string()

            self.root_parser.skip(4)
            if version >= 1:
                self.root_parser.skip(16)
                if version == 2:
                    self.root_parser.skip(4)

                if version >= 4:
                    self.root_parser.skip(4)
                    if version >= 5:
                        self.root_parser.skip(4)

                        if version == 6:
                            self.root_parser.skip(4)
                        
                        if version >= 7:
                            self.root_parser.read_uint32()

                            if version >= 9:
                                self.root_parser.skip(4)

                                if version >= 10:
                                    self.root_parser.skip(4)

                                    if version >= 11:
                                        self.root_parser.skip(4)
                                        
                                        if version >= 12:
                                            self.root_parser.skip(4)

                                            if version >= 13:
                                                self.root_parser.skip(8)

        elif cid == 0x03043003 or cid == 0x24003003:
            p = self.root_parser.pos
            self.root_parser.read_byte()
            for _ in range(3):
                self.root_parser.read_string_lookback()

            game_class = headers.CGameCommon(cid)

            self.root_parser.push_info()
            game_class.track_name = self.root_parser.read_string()
            self.positions['track_name'] = self.root_parser.pop_info()

            self.root_parser.read_byte()

            self.root_classes[cid] = game_class

            self.root_parser.pos = p + size
        elif cid == 0x03043005 or cid == 0x24003005:
            self.__community = self.root_parser.read_string()
        elif cid == 0x03093000 or cid == 0x2403F000:
            version = self.root_parser.read_uint32()
            self.__replay_header_info['version'] = version
            if version >= 2:
                for _ in range(3):
                    self.root_parser.read_string_lookback()
                self.root_parser.skip(4)
                self.__replay_header_info['nickname'] = self.root_parser.read_string()
                if version >= 6:
                    self.__replay_header_info['driver_login'] = self.root_parser.read_string()
                    self.root_parser.skip(1)
                    self.root_parser.read_string_lookback()
        elif cid == 0x03093002 or cid == 0x2403F002:
            self.root_parser.skip(8)
            for _ in range(4):
                self.root_parser.read_string()
        else:
            self.root_parser.skip(size)

    def _read_node(self, class_id, depth, bp, add=True):
        oldcid = 0
        cid = 0

        if class_id == GbxType.CHALLENGE or class_id == GbxType.CHALLENGE_OLD:
            game_class = headers.CGameChallenge(class_id)
            if hasattr(self, '__community'):
                game_class.community = self.__community
        elif class_id == GbxType.REPLAY_RECORD or class_id == GbxType.REPLAY_RECORD_OLD:
            game_class = headers.CGameReplayRecord(class_id)
            if 'nickname' in self.__replay_header_info:
                game_class.nickname = self.__replay_header_info['nickname']
            if 'driver_login' in self.__replay_header_info:
                game_class.driver_login = self.__replay_header_info['driver_login']

        elif class_id == GbxType.WAYPOINT_SPECIAL_PROP or class_id == 0x2E009000:
            game_class = headers.CGameWaypointSpecialProperty(class_id)
            self.__current_waypoint = game_class
            add = False
        elif class_id == GbxType.CTN_GHOST or class_id == GbxType.CTN_GHOST_OLD:
            game_class = headers.CGameCtnGhost(class_id)
        elif class_id == GbxType.GAME_GHOST:
            game_class = headers.CGameGhost(class_id)
        elif class_id == GbxType.COLLECTOR_LIST:
            game_class = headers.CGameCtnCollectorList(class_id)
        else:
            game_class = headers.CGameHeader(class_id)

        self.__current_class = game_class

        if add:
            self.classes[depth] = game_class

        while True:
            oldcid = cid
            cid = bp.read_uint32()
            logging.debug(f'Reading chunk {hex(cid)}')

            if cid == 0xFACADE01:
                logging.debug('Encountered chunk 0xFACADE01, stopping')
                break

            skipsize = -1
            skip = bp.read_int32()
            if skip == 0x534B4950:
                skipsize = bp.read_uint32()
            else:
                bp.pos -= 4

            if cid == 0x0304300D or cid == 0x2400300D:
                bp.read_string_lookback()
                bp.read_string_lookback()
                bp.read_string_lookback()
            elif cid == 0x03043011 or cid == 0x24003011:
                for _ in range(2):
                    idx = bp.read_int32()
                    if idx >= 0 and idx not in self.classes:
                        _class_id = bp.read_int32()
                        self._read_node(_class_id, idx, bp)
                bp.read_uint32()
            elif cid == 0x301B000 or cid == 0x2403C000:
                itemsct = bp.read_uint32()
                for _ in range(itemsct):
                    bp.read_string_lookback()
                    bp.read_string_lookback()
                    bp.read_string_lookback()
                    bp.read_uint32()
            elif cid == 0x0305B000 or cid == 0x2400C000:
                bp.skip(8 * 4)
            elif cid == 0x0305B001 or cid == 0x2400C001:
                bp.read_string()
                bp.read_string()
                bp.read_string()
                bp.read_string()
            elif cid == 0x0305B004 or cid == 0x2400C004:
                game_class.times = {
                    'bronze': bp.read_int32(),
                    'silver': bp.read_int32(),
                    'gold': bp.read_int32(),
                    'author': bp.read_int32()
                }

                bp.read_uint32()
            elif cid == 0x0305B005 or cid == 0x2400C005:
                bp.skip(4 * 3)
            elif cid == 0x0305B006 or cid == 0x2400C006:
                count = bp.read_uint32()
                bp.skip(count * 4)
            elif cid == 0x0305B008 or cid == 0x2400C008:
                bp.skip(2 * 4)
            elif cid == 0x0305B00A:
                bp.skip(9 * 4)                
            elif cid == 0x0305B00D:
                bp.skip(1 * 4)
            elif cid == 0x03043014 or cid == 0x03043029:
                bp.read(16 + 4)
                # m = hashlib.md5()
                # m.update(bp.read(16))
                # if isinstance(self.__current_class, headers.CGameChallenge):
                    # self.__current_class.password_hash = m.hexdigest()
                    # self.__current_class.password_crc = bp.read_uint32()
            elif cid == 0x03043017:
                num_cps = bp.read_uint32()
                for _ in range(num_cps):
                    bp.read_uint32()
                    bp.read_uint32()
                    bp.read_uint32()

            elif cid == 0x0304301F or cid == 0x2400301F:
                game_class.map_uid = bp.read_string_lookback()
                game_class.environment = bp.read_string_lookback()
                game_class.map_author = bp.read_string_lookback()

                bp.push_info()
                game_class.map_name = bp.read_string()
                self.positions['map_name'] = bp.pop_info()

                bp.push_info()
                game_class.mood = bp.read_string_lookback()
                self.positions['mood'] = bp.pop_info()
                game_class.env_bg = bp.read_string_lookback()
                game_class.env_author = bp.read_string_lookback()

                game_class.map_size = (
                    bp.read_int32(),
                    bp.read_int32(),
                    bp.read_int32()
                )

                game_class.req_unlock = bp.read_int32()
                game_class.flags = bp.read_int32()

                bp.push_info()
                num_blocks = bp.read_uint32()
                i = 0
                while i < num_blocks:
                    block = headers.MapBlock()
                    block.name = bp.read_string_lookback()
                    if block.name != 'Unassigned1':
                        game_class.blocks.append(block)
                    block.rotation = bp.read_byte()
                    block.position = headers.Vector3(
                        bp.read_byte(),
                        bp.read_byte(),
                        bp.read_byte()
                    )

                    if game_class.flags > 0:
                        block.flags = bp.read_uint32()
                    else:
                        block.flags = bp.read_uint16()

                    if block.flags == 0xFFFFFFFF:
                        continue

                    if (block.flags & 0x8000) != 0:
                        block.skin_author = bp.read_string_lookback()
                        if game_class.flags >= 6:
                            # TM2 flags
                            bp.read_string() # Block waypoint type {Spawn, Goal}
                            bp.read_int32()
                            self._read_node(0x2E009000, 0, bp, False)
                        else:
                            block.skin = bp.read_int32()
                            if block.skin >= 0 and block.skin not in self.classes:
                                _class_id = bp.read_int32()
                                self._read_node(_class_id, block.skin, bp)

                        if (block.flags & 0x100000) != 0:
                            block.params = bp.read_int32()
                            if block.params >= 0 and block.params not in self.classes:
                                _class_id = bp.read_int32()
                                self._read_node(_class_id, block.params, bp)

                    i += 1

                self.positions['block_data'] = bp.pop_info()              
            elif cid == 0x03043022:
                bp.skip(4)
            elif cid == 0x03043024:
                version = bp.read_byte()
                if version >= 3:
                    bp.skip(32)

                file_path = bp.read_string()
                if len(file_path) > 0 or version >= 3:
                    bp.read_string()
            elif cid == 0x03043025:
                bp.skip(4 * 4)
            elif cid == 0x03043026:
                idx = bp.read_int32()
                if idx >= 0 and idx not in self.classes:
                    _class_id = bp.read_int32()
                    self._read_node(_class_id, idx, bp)
            # elif cid == 0x03043028:
            #     archive_gm_cam_val = bp.read_int32()
            #     if archive_gm_cam_val == 1:
            #         bp.skip(1 + 4 * 7)

            #     bp.read_string()
            elif cid == 0x0304302A:
                bp.read_int32()
            elif cid == 0x3043040:
                bp.pos -= 4
                bp.push_info()
                bp.pos += 4

                item_bp = ByteReader(bp.data)
                item_bp.pos = bp.pos

                item_bp.skip(2 * 4)

                item_bp.push_info()
                item_bp.skip(2 * 4)

                num_items = item_bp.read_uint32()
                for i in range(num_items):
                    item_bp.skip(4 * 3)
                    item = headers.CGameBlockItem()
                    item.path = item_bp.read_string_lookback()
                    item.collection = item_bp.read_string_lookback()
                    item.author = item_bp.read_string_lookback()
                    item.rotation = item_bp.read_float()
                    item_bp.skip(15)

                    item.position = item_bp.read_vec3()

                    idx = item_bp.read_int32()
                    if idx >= 0:
                        self._read_node(0x2E009000, idx, item_bp)

                    item.waypoint = self.__current_waypoint
                    self.__current_waypoint = None

                    item_bp.skip(4 * 4 + 2)

                    self._read_node(0x3101004, 0, item_bp, add=False)

                    game_class.items.append(item)

                item_bp.skip(4)
                bp.pos = item_bp.pos
            elif cid == 0x03059002 or cid == 0x2403A002:
                bp.read_string()
                for i in range(2):
                    version = bp.read_byte()
                    if version >= 3:
                        bp.skip(32)

                    file_path = bp.read_string()
                    # (?) according to https://wiki.xaseco.org/wiki/GBX
                    # we need to check if the file path is not empty
                    # here but it crashes reading the file for TM2 challenges
                    if len(file_path) > 0 and version >= 1:
                        bp.read_string()
            elif cid == 0x03043022:
                bp.read_int32()
            elif cid == 0x03043024:
                bp.read_byte()
                bp.skip(32)
                bp.read_string()
                bp.read_string()
            elif cid == 0x03043025:
                bp.skip(16)
            elif cid == 0x03043026:
                idx = bp.read_int32()
                if idx >= 0 and idx not in self.classes:
                    _class_id = bp.read_int32()
                    self._read_node(_class_id, idx, bp)
            elif cid == 0x03043028:
                p = bp.read_int32()
                if p != 0:
                    bp.skip(1 + 4 * 3 * 3 + 4 * 3 + 4 + 4 + 4)

                bp.read_string()
            elif cid == 0x0304302A:
                bp.read_int32()
            elif cid == GbxType.WAYPOINT_SPECIAL_PROP or cid == 0x2E009000:
                version = bp.read_uint32()
                if version == 1:
                    game_class.spawn = bp.read_uint32()
                    game_class.order = bp.read_uint32()
                elif version == 2:
                    game_class.tag = bp.read_string()
                    game_class.order = bp.read_uint32()
            elif cid == 0x03059000:
                bp.read_string()
                bp.read_string()
            elif cid == 0x0303F005:
                Gbx.read_ghost(game_class, bp)
            elif cid == 0x0303F006:
                bp.skip(4)
                Gbx.read_ghost(game_class, bp)
            elif cid == 0x03093002 or cid == 0x2403F002:
                map_gbx_size = bp.read_uint32()
                data = bytes(bp.read(map_gbx_size))
                try:
                    game_class.track = Gbx(data)
                except Exception as e:
                    logging.error(f'Failed to parse map data: {e}')

            elif cid == 0x03093007:
                bp.skip(4)
            elif cid == 0x03093014 or cid == 0x2403F014:
                bp.skip(4)
                num_ghosts = bp.read_uint32()
                for _ in range(num_ghosts):
                    idx = bp.read_int32()
                    if idx >= 0 and idx not in self.classes:
                        _class_id = bp.read_uint32()
                        self._read_node(_class_id, idx, bp)
                
                bp.skip(4)
                # num_extras = bp.read_uint32()
                # bp.skip(num_extras * 8)
            elif cid == 0x3093015:
                idx = bp.read_int32()
                if idx >= 0 and idx not in self.classes:
                    _class_id = bp.read_uint32()
                    self._read_node(_class_id, idx, bp)

            elif cid == 0x03043021 or cid == 0x24003021:
                for _ in range(3):
                    idx = bp.read_int32()
                    if idx >= 0 and idx not in self.classes:
                        _class_id = bp.read_int32()
                        self._read_node(_class_id, idx, bp)
            elif cid == 0x03043022 or cid == 0x24003022:
                bp.skip(4)
            elif cid == 0x03043024 or cid == 0x24003024:
                version = bp.read_byte()
                if version >= 3:
                    bp.skip(32)
                
                path = bp.read_string()
                if len(path) > 0 and version >= 1:
                    bp.read_string()
            elif cid == 0x03043025 or cid == 0x24003025:
                bp.skip(4 * 4)
            elif cid == 0x03043026 or cid == 0x24003026:
                idx = bp.read_int32()
                if idx >= 0 and idx not in self.classes:
                    _class_id = bp.read_int32()
                    self._read_node(_class_id, idx, bp)
            elif cid == 0x03092005 or cid == 0x2401B005:
                game_class.race_time = bp.read_uint32()
            elif cid == 0x03092008 or cid == 0x2401B008:
                game_class.num_respawns = bp.read_uint32()
            elif cid == 0x03092009 or cid == 0x2401B009:
                game_class.light_trail_color = bp.read_vec3()
            elif cid == 0x0309200A or cid == 0x2401B00A:
                game_class.stunts_score = bp.read_uint32()
            # The GBX spec is wrong here.
            # 0x0309200B contains how many CP times there are
            # after that, there is a list of (uint32, uint32)
            # tuples, the first element is the time, the second
            # is unknown
            elif cid == 0x0309200B or cid == 0x2401B00B:
                num = bp.read_uint32()
                cp_times = []
                for i in range(num):
                    cp_times.append(bp.read_uint32())
                    bp.skip(4)
                
                game_class.cp_times = cp_times
            elif cid == 0x309200C or cid == 0x2401B00C:
                bp.skip(4)
            elif cid == 0x309200E or cid == 0x2401B00E:
                game_class.uid = bp.read_string_lookback()

                # For TM2
                if ('version' in self.__replay_header_info
                    and self.__replay_header_info['version'] >= 8):
                    pos = bp.pos
                    try:
                        game_class.login = bp.read_string()
                    except:
                        bp.pos = pos

            elif cid == 0x309200F or cid == 0x2401B00F:
                game_class.login = bp.read_string()
            elif cid == 0x3092010 or cid == 0x2401B010:
                bp.read_string_lookback()
            elif cid == 0x3092012 or cid == 0x2401B012:
                bp.skip(4 + 16)
                # import binascii
                # # bp.read(4)
                # print(bp.read_uint32())
                # print(f'{binascii.hexlify(bp.read(16))}')
                # print()
            elif cid == 0x3092013 or cid == 0x2401B013:
                bp.skip(4 + 4)
            elif cid == 0x3092014 or cid == 0x2401B014:
                bp.skip(4)
            elif cid == 0x3092015 or cid == 0x2401B015:
                bp.read_string_lookback()
            elif cid == 0x3092018 or cid == 0x2401B018:
                bp.read_string_lookback()
                bp.read_string_lookback()
                bp.read_string_lookback()
            elif cid == 0x3092019 or cid == 0x03092025 or cid == 0x2401B019 or cid == 0x2401B011:
                Gbx.read_ghost_events(game_class, bp, cid)
            elif cid == 0x309201c:
                bp.skip(32)
            elif cid == 0x03093004 or cid == 0x2403f004:
                bp.skip(4 * 4)
            elif skipsize != -1:
                bp.skip(skipsize)
                cid = oldcid
            else:
                return

    @staticmethod
    def read_ghost_events(game_class, bp, cid):
        if cid == 0x03092025:
            game_class.is_maniaplanet = True
            bp.skip(4)

        game_class.events_duration = bp.read_uint32()
        if game_class.events_duration != 0:
            bp.skip(4)

            num_control_names = bp.read_uint32()
            game_class.control_names = []
            for _ in range(num_control_names):
                name = bp.read_string_lookback()
                if name != '':
                    game_class.control_names.append(name)
                
            if len(game_class.control_names) == 0:
                return

            num_control_entries = bp.read_uint32()
            bp.skip(4)
            for _ in range(num_control_entries):
                time = bp.read_uint32() - 100000
                name = game_class.control_names[bp.read_byte()]
                entry = headers.ControlEntry(time, name, bp.read_uint16(), bp.read_uint16()) 
                game_class.control_entries.append(entry)
            
            game_class.game_version = bp.read_string()
            bp.skip(3 * 4)
            bp.read_string()
            bp.skip(4)

    @staticmethod
    def read_ghost(game_class, bp):
        uncomp_sz = bp.read_uint32()
        comp_sz = bp.read_uint32()
        comp_data = bp.read(comp_sz)
        data = zlib.decompress(comp_data, 0, uncomp_sz)

        gr = ByteReader(data)
        gr.skip(3 * 4)
        game_class.sample_period = gr.read_uint32()
        gr.skip(1 * 4)

        sample_data_sz = gr.read_uint32()
        sample_data_pos = gr.pos
        gr.skip(sample_data_sz)

        sample_sizes = []
        num_samples = gr.read_uint32()
        fso = 0
        if num_samples > 0:
            fso = gr.read_uint32()
            if num_samples > 1:
                sps = gr.read_int32()
                if sps == -1:
                    sample_sizes = []
                    for _ in range(num_samples - 1):
                        sample_sizes.append(gr.read_uint32())
                else:
                    sample_sizes.append(sps)

        gr.pos = sample_data_pos
        gr.skip(fso)
        for i in range(num_samples):
            sample_pos = gr.pos

            record = headers.GhostSampleRecord(
                gr.read_vec3(), gr.read_uint16(), gr.read_int16(),
                gr.read_int16(), gr.read_int16(),
                gr.read_int8(), gr.read_int8())

            len_sizes = len(sample_sizes)
            if i >= len_sizes:
                if len_sizes >= 1:
                    sample_sz = sample_sizes[0]
                else:
                    sample_sz = 0
            else:
                sample_sz = sample_sizes[i]

            record.raw_data = gr.read(sample_sz - (gr.pos - sample_pos))
            # import binascii
            # print(f'{i} {binascii.hexlify(record.raw_data)}')
            game_class.records.append(record)
