import logging
import struct
from io import IOBase
from pygbx.headers import Vector3
from os import SEEK_END

class PositionInfo(object):
    """
    This classes holds information that is mainly private to
    the Gbx class but can still be retrieved through the positions member.

    The PositionInfo marks a specific section in the file through it's position and size.
    """

    def __init__(self, pos, size):
        """Constructs a new PositionInfo"""

        self.pos = pos
        self.size = size

    @property
    def valid(self):
        """Checks if the instance of the section is valid
        
        Returns:
            True if the instance points to a valid section in the file, False otherwise
        """
        return self.pos > -1 and self.size > 0


class ByteReader(object):
    """The ByteReader class is used by the Gbx class to read specific data types supported by the GBX file format.

    The class provides convinience methods for reading raw types such as integers, strings and vectors, which
    are the main data types of the GBX file format. While reading the file, the Gbx class may instantiate multiple
    instances of ByteReader to read different parts of the file. This is because some chunks depend on the state
    of the reader, this state can be e.g: lookback strings.

    ByteReader accepts reading from raw bytes as well as from a file handle.
    """
    def __init__(self, obj):
        """Constructs a new ByteReader with the provided object.

        Args:
            obj (file/bytes): a file handle opened through open() or a bytes object
        """
        self.data = obj
        if isinstance(obj, IOBase):
            self.get_bytes = self.__get_bytes_file
            self.data.seek(0, SEEK_END)
            self.size = self.data.tell()
            self.data.seek(0)
        else:
            self.get_bytes = self.__get_bytes_generic
            self.size = len(self.data)

        self.pos = 0
        self.seen_loopback = False
        self.stored_strings = []
        self.current_info = PositionInfo(-1, 0)

    def push_info(self):
        """Begins a section that can be then retrieved with pop_info."""
        self.current_info = PositionInfo(self.pos, 0)


    def pop_info(self):
        """Ends the section began with push_info.
    
        Returns:
            a PositionInfo marking the section
        """
        self.current_info.size = self.pos - self.current_info.pos
        info = self.current_info
        self.current_info = PositionInfo(-1, 0)
        return info

    def read(self, num_bytes, typestr=None):
        """Reads an arbitrary amount of bytes from the buffer.

        Reads the buffer of length num_bytes and optionally
        takes a type string that is passed to struct.unpack if not None.

        Args:
            num_bytes (int): the number of bytes to read from the buffer
            typestr (str): the format character used by the struct module, passing None does not unpack the bytes
        
        Returns:
            the bytes object, if no type string was provided, type returned by struct.unpack otherwise
        """
        val = self.get_bytes(num_bytes)
        self.pos += num_bytes
        if typestr == None:
            return val
        try:
            return struct.unpack(typestr, val)[0]
        except Exception as e:
            logging.error(e)
            return 0

    def size(self):
        if isinstance(self.data, IOBase):
            return self.data.tell()
        else:
            return len(self.data)

    def __get_bytes_file(self, num_bytes):
        self.data.seek(self.pos)
        return self.data.read(num_bytes)

    def __get_bytes_generic(self, num_bytes):
        return self.data[self.pos:self.pos + num_bytes]

    def read_int32(self):
        """Reads a signed int32.
        
        Returns:
            the integer read from the buffer
        """
        return self.read(4, 'i')

    def read_uint32(self):
        """Reads an unsigned int32.
        
        Returns:
            the integer read from the buffer
        """
        return self.read(4, 'I')

    def read_int16(self):
        """Reads a signed int16.
        
        Returns:
            the integer read from the buffer
        """
        return self.read(2, 'h')

    def read_uint16(self):
        """Reads an unsigned int16.
        
        Returns:
            the integer read from the buffer
        """
        return self.read(2, 'H')

    def read_int8(self):
        """Reads a signed int8.
        
        Returns:
            the integer read from the buffer
        """
        return self.read(1, 'b')

    def read_float(self):
        """Reads a 32 bit float.
        
        Returns:
            the float read from the buffer
        """
        return self.read(4, 'f')

    def read_vec3(self):
        """Reads 12 bytes as 3 floats from the buffer and packs them into a Vector3.
        
        Returns:
            the vector read from the buffer
        """
        return Vector3(self.read_float(), self.read_float(), self.read_float())

    def read_string(self):
        """Reads a string from the buffer, first reading the length, then it's data.

        Returns:
            the string read from the buffer, None if there was an error
        """
        strlen = self.read_uint32()
        try:
            return self.read(strlen, str(strlen) + 's').decode('utf-8')
        except UnicodeDecodeError as e:
            logging.error(f'Failed to read string: {e}')
            return None

    def read_byte(self):
        """Reads a single byte from the buffer.

        Returns:
            the single byte read from the buffer
        """
        val = self.get_bytes(1)[0]
        self.pos += 1
        return val

    def skip(self, num_bytes):
        """Skips provided amount of bytes in the buffer

        Args:
            num_bytes (int): the number of bytes to skip
        """
        self.pos += num_bytes

    def read_string_lookback(self):
        """Reads a special string type in the GBX file format called the lookbackstring.
        
        Such type is used to reference already read strings, or introduce them if they were not 
        read yet. A ByteReader instance keeps track of lookback strings previously read and
        returns an already existing string, if the data references it. For more information,
        see the lookbackstring type in the GBX file format: https://wiki.xaseco.org/wiki/GBX.

        Returns:
            the lookback string read from the buffer
        """
        if not self.seen_loopback:
            self.read_uint32()

        self.seen_loopback = True
        inp = self.read_uint32()
        if (inp & 0xc0000000) != 0 and (inp & 0x3fffffff) == 0:
            s = self.read_string()
            self.stored_strings.append(s)
            return s

        if inp == 0:
            s = self.read_string()
            self.stored_strings.append(s)
            return s

        if inp == -1:
            return ''

        if (inp & 0x3fffffff) == inp:
            if inp == 11:
                return 'Valley'
            elif inp == 12:
                return 'Canyon'
            elif inp == 13:
                return 'Lagoon'
            elif inp == 17:
                return 'TMCommon'
            elif inp == 202:
                return 'Storm'
            elif inp == 299:
                return 'SMCommon'
            elif inp == 10003:
                return 'Common'

        inp &= 0x3fffffff
        if inp - 1 >= len(self.stored_strings):
            return ''
        return self.stored_strings[inp - 1]
