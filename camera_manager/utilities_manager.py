import hashlib


def generate_md5(s: str) -> str:
    # Create an MD5 hash object
    md5_hash = hashlib.md5()

    # Update the hash object with the bytes of the string, encoding needed to convert string to bytes
    md5_hash.update(s.encode('utf-8'))

    # Return the hexadecimal digest of the hash
    return md5_hash.hexdigest()


def get_error_description(error_code):
    """
    Retrieves the description of an error based on its error code.

    Parameters:
    - error_code (int): The error code for which to retrieve the description.

    Returns:
    - str: A string describing the error associated with the given error code.

    Error codes and descriptions are based on a predefined set of values, including
    standard, libcurl-specific errors, and custom application-specific errors.
    """

    # Mapping of error codes to their descriptions
    error_descriptions = {
        0: "normal",
        # libcurl error codes (1-100) reference omitted for brevity
        -101: "The file name ID is the same",
        -102: "Libraries full",
        -103: "Adding a timeout",
        -104: "Parameter error",
        -105: "File is too large",
        -106: "Insufficient storage space",
        -107: "File open failed",
        -108: "No database",
        -109: "Image reading failed",
        -110: "Database file is damaged",
        -111: "Picture quality is poor",
        -112: "Image size is wrong, width and height cannot be odd numbers",
        -113: "Face detection failed (no face detected or multiple faces detected)",
        -114: "Picture format error",
        -115: "Face area error",
        -116: "Algorithm creates a handle error",
        -117: "Device is busy",
        -118: "File writing failed",
        -119: "Deletion failed (the corresponding ID was not found to delete)",
        -120: "Failed to allocate memory",
        -121: "The number of people in the list is NULL",
        -122: "Valid time error",
        -123: "Failed to write characteristic value",
        201: "Parameter does not exist",
        202: "User id already exists",
        203: "User id does not exist",
        204: "Device is busy (Duplicate)",
        205: "The parameter is invalid",
        206: "Administrator password error",
        207: "Picture name does not meet the rules",
        208: "No new information",
        209: "Device not supported",
        210: "The file format is not supported",
        299: "No reaction",
    }

    # Return the corresponding error description or a default message if not found
    if error_code in error_descriptions:
        return error_descriptions[error_code]
    elif 1 <= error_code <= 100:
        return "libcurl error"
    else:
        return "Unknown error"
