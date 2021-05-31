import ctypes
from os import path, name as osname
from ctypes import CDLL, c_uint32, byref
from logging import error


class LZO(object):
    """This class contains stand alone methods of the LZO library. It calls an external library file.

    Available methods:
        lzo1x_1_compress
        lzo1x_999_compress (best compression)
        lzo1x_decompress_safe (use this for decompression)

    More functions build into the library that haven't been implemented yet:
        lzo1x_1_11_compress
        lzo1x_1_12_compress
        lzo1x_1_15_compress
        lzo1x_999_compress_dict
        lzo1x_999_compress_internal
        lzo1x_999_compress_level
        lzo1x_decompress
        lzo1x_decompress_dict_safe
        lzo1x_optimize
    """
    def __init__(self):
        # Load libs here once in case someone wants to execute the compression methods in batch mode
        if osname == 'nt':
            self.__lib_ext = '.dll'
        elif osname == 'posix':
            self.__lib_ext = '.so'
        else:
            raise Exception(f'your system cannot load the lzo libs. required: windows/posix, given: {osname}')

        self.__lzo1x_lib_path = path.join(path.dirname(path.abspath(__file__)), 'lzo', 'libs',
                                          f'lzo1x{self.__lib_ext}')

        try:
            self.__lzo1x_lib = CDLL(self.__lzo1x_lib_path)
        except Exception as e:
            raise Exception(f'lzo decompression library could not be successfully loaded: {e}')

    def lzo1x_decompress_safe(self, data, uncompressed_size):
        return self.__lzo1x_decompress_safe(data, uncompressed_size)

    def lzo1x_1_compress(self, data, uncompressed_size):
        return self.__lzo1x_1_compress(data, uncompressed_size)

    def lzo1x_999_compress(self, data, uncompressed_size):
        return self.__lzo1x_999_compress(data, uncompressed_size)

    def __lzo1x_decompress_safe(self, data, uncompressed_size):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into bytes data type: {e}')
                return False
        if not isinstance(uncompressed_size, int):
            error(f'uncompressed_size must be of data type int. {type(uncompressed_size)} was given')
            return False

        # compressed data is here
        in_buffer = data
        # decompressed data goes here
        out_buffer = bytes(uncompressed_size)

        # C unsigned int compressed_size
        compressed_size = c_uint32(len(in_buffer))

        # C unsigned int uncompressed_size
        uncompressed_size = c_uint32(uncompressed_size)

        # This is is necessary because uncompressed_size will be overwritten by the decompress function
        uncompressed_size_original = uncompressed_size.value

        # ! bytes_written is a pointer (C unsigned int* bytes_written) that points to uncompressed_size, which holds
        # (currently) the output length that we should see if decompression is successful. however the C function
        # sets the value in uncompressed_size to 0 at the start of the functions. before it sets it 0, it saves the
        # value into another internal value. the uncompressed_size value will then be used as a variable to store how
        # many bytes were written during decompression, which is why this pointer below that points to uncompressed_size
        # is called bytes_written.
        bytes_written = byref(uncompressed_size)

        try:
            self.__lzo1x_lib.lzo1x_decompress_safe(in_buffer, compressed_size,
                                                   out_buffer, bytes_written)
            # we can now compare uncompressed_size (how many bytes were written during decompression) with
            # the uncompressed_size_original variable
            if uncompressed_size.value != uncompressed_size_original:
                return False
            else:
                return out_buffer
        except Exception as e:
            error(e)
            return False

    def __lzo1x_1_compress(self, data, uncompressed_size):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into bytes data type: {e}')
                return False
        if not isinstance(uncompressed_size, int):
            error(f'uncompressed_size must be of data type int. {type(uncompressed_size)} was given')
            return False

        in_buffer = data
        # How big should these even be?
        out_buffer = bytes(len(in_buffer)*2)

        workmem = bytes(65535)

        uncompressed_size = ctypes.c_uint32(uncompressed_size)
        compressed_size = ctypes.c_uint32(0)

        bytes_written = ctypes.byref(compressed_size)

        try:
            self.__lzo1x_lib.lzo1x_1_compress(in_buffer, uncompressed_size, out_buffer,
                                              bytes_written, workmem)
            return out_buffer[0:compressed_size.value]
        except Exception as e:
            error(e)
        return False

    def __lzo1x_999_compress(self, data, uncompressed_size):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into bytes data type: {e}')
                return False
        if not isinstance(uncompressed_size, int):
            error(f'uncompressed_size must be of data type int. {type(uncompressed_size)} was given')
            return False

        in_buffer = data
        # How big should these even be?
        out_buffer = bytes(len(in_buffer)*2)

        workmem = bytes(524288)

        uncompressed_size = ctypes.c_uint32(uncompressed_size)
        compressed_size = ctypes.c_uint32(0)

        bytes_written = ctypes.byref(compressed_size)

        try:
            self.__lzo1x_lib.lzo1x_999_compress(in_buffer, uncompressed_size, out_buffer,
                                                bytes_written, workmem)
            return out_buffer[0:compressed_size.value]
        except Exception as e:
            error(e)
        return False
