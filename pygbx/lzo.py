import ctypes
from os import path, name as osname
from ctypes import CDLL, c_uint32, byref, c_char_p, POINTER, sizeof, c_void_p
from logging import error


class LZO:
    """This class contains stand alone methods of the LZO library. It calls an external library file and will run in C.

    Usage
        Create an instance of this class and use it with obj.decompress(data, uncompressed_size) or obj.compress(data).
        It will always return data or False on failure. The instance is reusable.

    Availability
        This library should work on Windows and Linux both 32 and 64 bit. If you encounter issues
        please submit an issue

    Extra info
        When decompressing, the uncompressed_size argument is known before the data is uncompressed.
        It is written inside of GBX data and has to be retrieved from there.

        Internal LZO functions that are used
            lzo1x_999_compress
            lzo1x_decompress_safe

        Other internal functions that are called from the above
            lzo1x_999_compress_internal
            lzo1x_999_compress_level

        lzo1x_999_compress
            This is the best function for compressing data in terms of file size, but also one of the slowest. The LZO
            FAQ itself says however it should be used when generating pre-compressed data (meaning stuff like
            Replay/Challenge files). The decompression speed is not affected by whatever compression function was used.

        lzo1x_decompress_safe
            Extremely fast decompression algorithm. It was designed for run time applications, such as it was in the
            game Trackmania. Its name has the postfix _safe because it can never crash (from LZO FAQ). However there is
            no guarantee that the returned data has its integrity preserved. LZO offers crc32 (and adler32) to check the
            integrity, but since GBX data doesn't seem to have the checksum written anywhere, there was also no real
            point of integrating the lzo_crc32 into this library. If you know where the checksum might be hidden please
            write us back.

        Speed
            The lzo1x_decompress_safe function is extremely fast. Benchmarking 100,000 iterations of decompressing a
            TMNF replay file (36538 bytes in size) took approximately 1.08 seconds. The uncompressed size was 38595

            The lzo1x_999_compress function is slow. Benchmarking 1000 iterations of uncompressed data from above with
            a size of 38595 bytes took approximately 2.7 seconds (which still is only ~0.003 seconds for a GBX Replay)

        Comparison to compression of TMNF
            A random set of 14000 replays were analyzed in terms of their compressed to decompressed ratio for the
            internal function the game uses vs the lzo1x_999_compress function this library uses.
            On average, the compression factor of replay files in TMNF are at about 94.33%, where as compressing that
            data with lzo1x_999_compress resulted in a compression rate of about 93.60%.

            Tip: You can if you want uncompress the data in your GBX data and re-compress it with this
            lzo1x_999_compress method to save a little bit of space, it is recognized and acceptable by the game
    """

    def __init__(self):
        """Loads library upon object creation once"""

        # Check for architecture size
        self.is64 = sizeof(c_void_p) >> 3

        # Check for architecture (Windows/Linux supported)
        if osname == 'nt':
            self.__lib_ext = '.dll'
        elif osname == 'posix':
            self.__lib_ext = '.so'
        else:
            raise Exception(f'Your system cannot load the LZO libs. Required: Windows/Linux, given: {osname}')

        self.__lzo1x_lib_path = path.join(path.dirname(path.abspath(__file__)), 'lzo', 'libs',
                                          f'lzo1x_{"64" if self.is64 else "32"}{self.__lib_ext}')

        try:
            self.__lzo1x_lib = CDLL(self.__lzo1x_lib_path)
        except Exception as e:
            raise Exception(f'LZO library could not be loaded: {e}')

        # Specify arguments and response types
        self.__lzo1x_lib.lzo1x_decompress_safe.restype = c_uint32
        self.__lzo1x_lib.lzo1x_decompress_safe.argtypes = [c_char_p, c_uint32, c_char_p,
                                                           POINTER(c_uint32)]

        self.__lzo1x_lib.lzo1x_999_compress.restype = c_uint32
        self.__lzo1x_lib.lzo1x_999_compress.argtypes = [c_char_p, c_uint32, c_char_p,
                                                        POINTER(c_uint32), ctypes.c_void_p]

    def decompress(self, data, uncompressed_size):
        return self.__lzo1x_decompress_safe(data, uncompressed_size)

    def compress(self, data):
        return self.__lzo1x_999_compress(data)

    def __lzo1x_decompress_safe(self, data, uncompressed_size):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into type bytes: {e}')
                return False
        if not isinstance(uncompressed_size, int):
            error(f'uncompressed_size must be of data type int. {type(uncompressed_size)} was given')
            return False

        # decompressed data goes here
        out_buffer = bytes(uncompressed_size)

        # C unsigned int compressed_size
        compressed_size = c_uint32(len(data))

        # Pointer to uncompressed_size. The function takes in a pointer to uncompressed_size and uses it internally
        # to store some internal temporary value which then holds the uncompressed_size and is used for something else.
        # Afterwards the internal function sets our outside uncompressed_size to 0, and as the decompression process
        # progresses, it writes into it the number of bytes that were written (hence the name bytes_written for the
        # pointer). After the internal function returns, it will have set our outside uncompressed_size to the bytes
        # that were actually written, so uncompressed_size should become the same value again, if no error has occurred
        bytes_written = c_uint32(uncompressed_size)

        try:
            if self.__lzo1x_lib.lzo1x_decompress_safe(data, compressed_size, out_buffer, byref(bytes_written)):
                return False

            # check if the bytes that were written match out_buffer size we have originally allocated
            if bytes_written.value != len(out_buffer):
                return False
            else:
                return out_buffer
        except Exception as e:
            error(e)
            return False

    def __lzo1x_999_compress(self, data):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into bytes data type: {e}')
                return False

        # Compressed data ends up here. According to LZO FAQ, the size of this buffer is calculated with this formula:
        # out_size = in_size + (in_size / 16) + 64 + 3
        # These are worst case scenario expansions (~106% of in_size)
        out_buffer = bytes(len(data) + (int(len(data) / 16)) + 67)

        work_memory = bytes(524288)
        uncompressed_size = c_uint32(len(data))
        bytes_written = c_uint32(0)

        try:
            if self.__lzo1x_lib.lzo1x_999_compress(
                    data, uncompressed_size, out_buffer, byref(bytes_written), work_memory) != 0:
                return False

            return out_buffer[0:bytes_written.value]
        except Exception as e:
            error(e)
            return False
