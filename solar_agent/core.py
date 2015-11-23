#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License attached#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See then
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import random
import string
from contextlib import nested
from fabric import api as fabric_api
from subprocess import check_output
import shlex
from itertools import takewhile


from solar_agent.logger import logger


# XXX: not used for now vvv

# def common_path(paths, sep=os.path.sep):
#     paths = [x.split(sep) for x in paths]
#     dirs = zip(*(p for p in paths))
#     return [x[0] for x in takewhile(lambda x: all(n == x[0] for n in x[1:]), dirs)]


# class SolarAgentContext(object):

#     def __init__(self):
#         self._dirs = {}
#         self._files = {}

#     def file(self, path):
#         try:
#             return self._files[path]
#         except KeyError:
#             if self.is_safe_file(path):
#                 cls = SolarAgentSafeFile
#             else:
#                 cls = SolarAgentFile
#             self._files[path] = f = cls(self, path)
#         return f

#     def dir(self, path):
#         try:
#             return self._dirs[path]
#         except KeyError:
#             self._dirs[path] = solar_agent_dir = SolarAgentDir(self, path)
#         return solar_agent_dir

#     def is_safe_file(self, path):
#         dirname = os.path.dirname(path)
#         common = SolarAgentContext.common_path(dirname, self._dirs.keys())
#         if common not in ((), ('/', )):
#             return False
#         return True

#     def is_safe_dir(self, path):
#         common = SolarAgentContext.common_path(path, self._dirs.keys())
#         if common not in ((), ('/', )):
#             return False
#         return True

#     @staticmethod
#     def common_path(path, paths, sep=os.path.sep):
#         all_paths = paths + [path]
#         paths = [x.split(sep) for x in all_paths]
#         dirs = zip(*(p for p in all_paths))
#         return tuple(x[0] for x in takewhile(lambda x: all(n == x[0] for n in x[1:]), dirs))


# class SolarAgentSafeFile(object):

#     def __init__(self, context, target):
#         self._f = None
#         self._rnd = 'solar' + ''.join((random.choice(string.ascii_lowercase) for _ in xrange(6)))
#         self._path = target
#         self._safe_path = self._path + '_' + self._rnd

#     def open(self):
#         self._f = open(self._safe_path, 'wb')

#     def write(self, data):
#         return self._f.write(data)

#     def close(self):
#         self._f.close()

#     def finish(self):
#         self.close()
#         os.rename(self._safe_path, self._path)


# class SolarAgentFile(object):

#     def __init__(self, context, target):
#         self._f = None
#         self._path = target

#     def open(self):
#         self._f = open(self._path, 'wb')

#     def write(self, data):
#         self._f.write(data)

#     def close(self):
#         self._f.close()

#     def finish(self):
#         self.close()


# class SolarAgentSafeDir(object):

#     def __init__(self, context, target):
#         self._rnd = 'solar' + ''.join((random.choice(string.ascii_lowercase) for _ in xrange(6)))
#         self._path = target
#         self._safe_path = self._path + '_' + self._rnd

#     def start(self):
#         os.makedirs(self._safe_path)

#     def finish(self):
#         os.rename(self._safe_path, self._path)


# class SolarAgentDir(object):

#     def __init__(self, context, target):
#         self._path = target

#     def start(self):
#         os.makedirs(self._path)

#     def finish(self):
#         pass

# XXX: not used for now ^^^

class SolarAgentContext(object):

    def __init__(self):
        self.files = {}

    def file(self, path):
        try:
            return self.files[path]
        except KeyError:
            self.files[path] = r = SolarAgentFile(self, path)
        return r


class SolarAgentFile(object):

    def __init__(self, context, target):
        self.ctx = context
        self._rnd = 'solar' + ''.join((random.choice(string.ascii_lowercase) for _ in xrange(6)))
        self._path = target
        self._f = None
        self._safe_path = self._path + '_' + self._rnd

    def open(self):
        dirname = os.path.dirname(self._safe_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if self._f is None:
            self._f = open(self._safe_path, 'wb')

    def write(self, data):
        self._f.write(data)

    def finish(self):
        self._f.close()
        self._f = None
        os.rename(self._safe_path, self._path)


class SolarAgentIface(object):

    @staticmethod
    def run(solar_agent_context, cmd, **kwargs):
        # return check_output(shlex.split(cmd))
        executor = fabric_api.local
        # if kwargs.get('use_sudo', False):
        #     cmd = 'sudo ' + cmd

        managers = []

        cwd = kwargs.get('cwd')
        if cwd:
            managers.append(fabric_api.cd(kwargs['cwd']))

        env = kwargs.get('env')
        if env:
            managers.append(fabric_api.shell_env(**kwargs['env']))

        # we just warn, don't exit on solar_agent
        # correct data is returned
        managers.append(fabric_api.warn_only())

        with nested(*managers):
            out = executor(cmd, capture=True)
            result = {}
            for name in ('failed', 'return_code', 'stdout', 'stderr',
                         'succeeded', 'command', 'real_command'):
                result[name] = getattr(out, name)
            return result

    @staticmethod
    def copy_file(solar_agent_context, stream_reader, path, size=None):
        f = SolarAgentIface.file_start(solar_agent_context, path)
        rdr = stream_reader(size)
        for data in rdr:
            f.write(data)
        SolarAgentIface.file_end(solar_agent_context, path)
        return True

    @staticmethod
    def copy_files(solar_agent_context, stream_reader, paths, total_size):
        # total_size not used for now
        for _to, _size in paths:
            logger.debug("Starting %s size=%d", _to, _size)
            f = SolarAgentIface.file_start(solar_agent_context, _to)
            if _size > 0:
                rdr = stream_reader(_size)
                for data in rdr:
                    f.write(data)
            SolarAgentIface.file_end(solar_agent_context, _to)
            logger.debug("Done %s size=%d", _to, _size)
        return True


    # # TODO: not used YET fully
    # @staticmethod
    # def dir_start(solar_agent_context, path):
    #     solar_agent_dir = solar_agent_context.dir(path)
    #     solar_agent_dir.start()
    #     return solar_agent_dir

    # @staticmethod
    # def dir_finish(solar_agent_context, path):
    #     solar_agent_dir = solar_agent_context.dir(path)
    #     solar_agent_dir.finish()
    #     return True

    @staticmethod
    def file_start(solar_agent_context, path):
        solar_agent_file = solar_agent_context.file(path)
        solar_agent_file.open()
        return solar_agent_file

    @staticmethod
    def file_put_data(solar_agent_context, path, data):
        solar_agent_file = solar_agent_context.file(path)
        return solar_agent_file.write(data)

    @staticmethod
    def file_end(solar_agent_context, path):
        solar_agent_file = solar_agent_context.file(path)
        solar_agent_file.finish()
        return True

