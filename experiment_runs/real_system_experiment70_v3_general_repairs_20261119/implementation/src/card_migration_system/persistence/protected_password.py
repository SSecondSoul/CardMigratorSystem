"""Optional Windows CurrentUser DPAPI storage for a database APPLICATION secret.

Root passwords are never stored. This is not a password-manager integration and
does not read other credentials. Linux/service deployments can keep using the
existing environment-variable path instead. A compromised logged-in Windows
account is outside DPAPI's protection; the password exists in process memory
while connecting to the database.
"""
import base64
import json
import os

MAGIC = b'CARDMIG-WINDOWS-DPAPI-v1\n'
ENTROPY = b'CardMigrator/MySQL/ApplicationPassword/v1'


class SecretError(ValueError):
    def __init__(self, code, *, win32_error=None):
        self.code = code
        self.win32_error = win32_error
        super().__init__(code)


def _dpapi(data, *, protect):
    if os.name != 'nt':raise SecretError('mysql_protected_password_requires_windows_user')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(data)
    entropy_buffer = ctypes.create_string_buffer(ENTROPY)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    entropy = Blob(len(ENTROPY), ctypes.cast(entropy_buffer, ctypes.c_void_p))
    result = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p];kernel.LocalFree.restype = ctypes.c_void_p
    try:
        # UI_FORBIDDEN only: NEVER set CRYPTPROTECT_LOCAL_MACHINE (all users).
        if not function(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(result)):
            raise SecretError('mysql_protected_password_encrypt_failed' if protect else 'mysql_protected_password_decrypt_failed',
                              win32_error=ctypes.get_last_error())
        return ctypes.string_at(result.data, result.length)
    finally:
        ctypes.memset(ctypes.addressof(buffer), 0, len(buffer))
        if result.data:
            if not protect:ctypes.memset(result.data, 0, result.length)
            kernel.LocalFree(result.data)


def save_password(path, password, binding):
    if binding.get('username', '').lower() == 'root':
        raise SecretError('mysql_root_password_must_not_be_saved')
    if type(password) is not str or not 1 <= len(password) <= 512:
        raise SecretError('mysql_application_password_invalid')
    raw = json.dumps({'version': 1, 'binding': binding, 'password': password},
                     sort_keys=True, separators=(',', ':')).encode('utf-8')
    encrypted = MAGIC + base64.b64encode(_dpapi(raw, protect=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:  # Do not rotate/overwrite an existing secret.
        stream.write(encrypted)


def load_password(path, binding):
    try:
        with path.open('rb') as stream:encoded = stream.read(16385)
        if len(encoded) > 16384 or not encoded.startswith(MAGIC):
            raise SecretError('mysql_protected_password_file_invalid')
        ciphertext = base64.b64decode(encoded[len(MAGIC):], validate=True)
        data = json.loads(_dpapi(ciphertext, protect=False).decode('utf-8'))
        if (type(data) is not dict or set(data) != {'version', 'binding', 'password'}
                or type(data['version']) is not int or data['version'] != 1
                or data['binding'] != binding or binding.get('username', '').lower() == 'root'
                or type(data['password']) is not str or not 1 <= len(data['password']) <= 512):
            raise SecretError('mysql_protected_password_binding_mismatch')
        return data['password']
    except SecretError:
        raise
    except (OSError, ValueError, UnicodeError, KeyError):
        raise SecretError('mysql_protected_password_file_invalid') from None
