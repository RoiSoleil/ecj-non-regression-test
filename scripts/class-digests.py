#!/usr/bin/env python3
"""Lists the class files that a Java compiler wrote under the build output directories of a project, with a digest.

usage: class-digests.py <build directory>

One line per class file, sorted: "<path relative to the build directory> <the first 16 hex digits of its SHA-256>"
(scripts/bytecode.py compares these lists). Only the class files compiled from Java sources: their SourceFile attribute
names a .java file, or they have none. The others come from another compiler (Clojure, Kotlin, Groovy, Scala...), whose
output can change with the state of the JVM that runs it, and say nothing of the Java compiler.
"""
import hashlib
import os
import re
import struct
import sys

# the output directories of CLASS_FILES in run-project.sh
OUTPUT = re.compile(rb'(^|/)(target/classes|target/test-classes|build/classes)/|^out-java\.')


def source_file(data):
    """the SourceFile attribute of a class file, None when it has none or cannot be read"""
    try:
        if data[:4] != b'\xca\xfe\xba\xbe':
            return None
        count = struct.unpack_from('>H', data, 8)[0]
        utf8 = {}
        offset, index = 10, 1
        while index < count:
            tag = data[offset]
            if tag == 1:
                length = struct.unpack_from('>H', data, offset + 1)[0]
                utf8[index] = data[offset + 3:offset + 3 + length].decode('utf-8', 'replace')
                offset += 3 + length
            elif tag in (5, 6):  # long, double: two entries
                offset += 9
                index += 1
            elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
                offset += 5
            elif tag == 15:
                offset += 4
            elif tag in (7, 8, 16, 19, 20):
                offset += 3
            else:
                return None
            index += 1
        offset += 6  # access flags, this class, super class
        interfaces = struct.unpack_from('>H', data, offset)[0]
        offset += 2 + 2 * interfaces
        for _ in range(2):  # fields, then methods
            members = struct.unpack_from('>H', data, offset)[0]
            offset += 2
            for _ in range(members):
                attributes = struct.unpack_from('>H', data, offset + 6)[0]
                offset += 8
                for _ in range(attributes):
                    offset += 6 + struct.unpack_from('>I', data, offset + 2)[0]
        attributes = struct.unpack_from('>H', data, offset)[0]
        offset += 2
        for _ in range(attributes):
            name, length = struct.unpack_from('>HI', data, offset)
            if utf8.get(name) == 'SourceFile':
                return utf8.get(struct.unpack_from('>H', data, offset + 6)[0])
            offset += 6 + length
    except (IndexError, struct.error):
        pass
    return None


def main():
    # bytes, as find and sha256sum did: a file name need not be UTF-8
    root = os.fsencode(sys.argv[1])
    lines = []
    for directory, _, files in os.walk(root):
        for name in files:
            if not name.endswith(b'.class'):
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, root).replace(os.fsencode(os.sep), b'/')
            # regular files only (find -type f), and a name that fits on one line
            if not OUTPUT.search(relative) or b'\n' in relative or os.path.islink(path) or not os.path.isfile(path):
                continue
            with open(path, 'rb') as f:
                data = f.read()
            source = source_file(data)
            if source is not None and not source.endswith('.java'):
                continue
            lines.append(relative + b' ' + hashlib.sha256(data).hexdigest()[:16].encode())
    sys.stdout.buffer.write(b''.join(line + b'\n' for line in sorted(lines)))


if __name__ == '__main__':
    main()
