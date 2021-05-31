from os import path, name as osname, getcwd
from ctypes import CDLL, c_uint32, byref
from logging import error

class LZO(object):
    def __init__(self):
        # Load libs here once in case someone wants to execute the compression methods in batch mode
        if osname == 'nt':
            self._lib_ext = '.dll'
        elif osname == 'posix':
            self._lib_ext = '.so'
        else:
            raise Exception(f'your system cannot load the lzo libs. required: windows/posix, given: {osname}')

        self._decompress_lib_path = path.join(path.dirname(path.abspath(__file__)), 'lzo', 'libs',
                                              f'lzo1x_decompress_safe{self._lib_ext}')
        try:
            self._lzo_lib = CDLL(self._decompress_lib_path)
        except Exception as e:
            raise Exception(f'lzo decompression library was not successfully loaded: {e}')

    def lzo1x_decompress_safe(self, data, uncompressed_size):
        return self._lzo1x_decompress_safe(data, uncompressed_size)

    def _lzo1x_decompress_safe(self, data, uncompressed_size):
        if not isinstance(data, bytes):
            try:
                data = bytes(data)
            except Exception as e:
                error(f'Could not turn data into bytes data type: {e}')
                return False
        if not isinstance(uncompressed_size, int):
            error(f'uncompressed_size must be of data type int. {type(uncompressed_size)} was given')
            return False

        # the C lzo1x_decompress_safe function takes in following arguments:
        # ( const unsigned char* in_buffer, unsigned long compressed_size,
        # unsigned char* out_buffer, unsigned long* bytes_written )

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
            self._lzo_lib.lzo1x_decompress_safe(in_buffer, compressed_size, out_buffer, bytes_written)
            # we can now compare uncompressed_size (how many bytes were written during decompression) with
            # the uncompressed_size_original variable
            if uncompressed_size.value != uncompressed_size_original:
                return False
            else:
                return out_buffer
        except Exception as e:
            error(e)
            return False
