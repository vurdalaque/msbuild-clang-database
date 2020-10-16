# vi: fenc=utf8
import os, sys, re, subprocess, json, msvcrt, shutil
from pathlib import Path

makefile_exists = Path("./Makefile").exists()

D = []  # ['CINTERFACE']
SYSINCLUDE = ['c:/.config/include']
I = []
F = []
build_opts = []

config = {
        'ignore_cc': True,
        'ignore_bb': True,
        'mixed_decoder': 'cp1251',
        'log' : False,
        'file_name' : 'cc.log',
        'fd' : None
        }

replaceable_path = {
        # those path will be excluded (already in SYSINCLUDE)
        'D:/projects/extsdk/trunk/gtest-1.8.1/googlemock/include': '',  # 'd:/site/googletest/googlemock/include',
        'D:/projects/extsdk/trunk/gtest-1.8.1/googletest/include': '',  # 'd:/site/googletest/googletest/include',
        'D:/projects/extsdk/trunk/log4cxx-0.10.0/include': '',
        'D:/projects/extsdk/trunk/nlohmann_json/include': '',
        'D:/projects/extsdk/trunk/boost_1_69_0': '',
        'D:/projects/extsdk/trunk/xerces-c-3.1.1/include': '',
        'D:/projects/extsdk/trunk/protobuf/install/include': '',
        'D:/projects/extsdk/trunk/CryptoPP-4.2/include': '',
        'D:/projects/extsdk/trunk/openssl/include': '',
        }

ycm_extra_conf_pattern = "def Settings( **kwargs ):\n    return {'flags': [\n$FLAGS$ ],\n}"

if Path('cc_args').exists():
    exec(open('./cc_args').read(), globals(), locals())

def log(*args):
    if config['log'] == False:
        return
    if config['fd'] is None:
        config['fd'] = open(config['file_name'], 'w')

    for line in args:
        config['fd'].write(line)

def lprint(*args):
    print(*args)
    log(*args)


def cleanup(silent = False, cdatabase = False, path = '.'):
    if silent is False:
        print('press [y] to remove studio projects... ')
        if msvcrt.getch() != b'y':
            return
    masks = [
            '^.*\.sln$',
            '^.*\.pdb$',
            '^cc\.log$',
            '^build\.log$',
            '^.*\.vcxproj$',
            '^.*\.vcxproj.filters$',
            '^\.vs$',
            ]
    if cdatabase is True:
        masks.append('^compile_commands.json$')
        masks.append('^Makefile$')
        masks.append('^Makefile.Release$')
        masks.append('^Makefile.Debug$')

    masks = [re.compile(r) for r in masks]
    for f in os.listdir('./'):
        for m in masks:
            if m.match(f) is not None:
                print(str(Path(f).absolute()).replace('\\', '/') + ' deleted')
                if os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors = True)
                else:
                    os.remove(f)

        if os.path.isdir(f):
            os.chdir(f)
            cleanup(True, cdatabase, f)
            os.chdir('..')


class source_file:
    def __init__(self, f, d, _F, _D, _I, _isystem, finc, pch):
        self.file = os.path.abspath('{d}/{f}'.format(d = d, f = f)).replace('\\', '/')
        self.directory = d
        self.flags = _F
        self.defs = _D
        self.inc = _I
        self.sys_inc = _isystem
        self.finc = finc
        self.pch = pch
        self.command = '"C:/Program Files/LLVM/bin/clang++" "{source}" {flags} {defs} {inc} {sys} {cdev}'.format(
                flags = ' '.join(_F),
                defs = ' '.join(['-D {f}'.format(f = f) for f in _D]),
                inc = ' '.join(['-I "{f}"'.format(f = f) for f in _I]),
                sys = ' '.join(['-isystem "{f}"'.format(f = f) for f in _isystem]),
                cdev = '-include "c:/.config/cc_dev.h"',
                source = f
                )

        if finc is not None:
            self.command = self.command + ' -include "{pch}"'.format(pch = finc)

        #  if pch is not None: # not supported :(
            #  self.command = self.command + ' -include-pch {pch}'.format(pch = pch)

    def collect(self):
        command = self.flags
        for d in self.defs:
            command.extend(['-D', '"{inc}"'.format(inc = d) if (' ' in d) == True else d])
        for inc in self.inc:
            command.extend(['-I', '"{inc}"'.format(inc = inc) if (' ' in inc) == True else inc])
        for inc in self.sys_inc:
            command.extend(['-isystem', '"{inc}"'.format(inc = inc) if (' ' in inc) == True else inc])
        if self.finc is not None:
            command.extend(['-include', self.finc])
        return command

    def optlen(self):
        return len(self.command)

    def toJSON(self):
        class json_src:
            def __init__(self, source_file):
                self.file = source_file.file
                self.directory = source_file.directory
                self.command = source_file.command
        return json.dumps(json_src(self), default=lambda o: o.__dict__,
                sort_keys=True, indent=4)

class command_parser:
    def __init__(self):
        self.rel_path = ''
        self.files = []
        self.header_inc = None
        self.pch = None
        self.init_tags()
        self.sys_inc = SYSINCLUDE + [x.replace('\\', '/') for x in os.environ['INCLUDE'].split(';')]

    def qmake(self):
        projects = [f for f in os.listdir('./') if re.match('^.*\.pro$', f) is not None]
        if len(projects) == 0:
            lprint('no qt projects found')
            return []

        for pro in projects:
            opts = ['qmake.exe', '-tp', 'vc', '-r', pro]
            build = subprocess.Popen(opts,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    stdin = subprocess.PIPE)
            output, _  = build.communicate()
            if build.returncode != 0:
                lprint('qmake run with error ', output)

        projects = [f for f in os.listdir('./') if re.match('^.*\.vcxproj$', f) is not None]

        if len(projects) == 0:
            projects = [f for f in os.listdir('./') if re.match('^.*\.sln$', f) is not None]
            if len(projects) > 0:
                # this was pro with SUBDIRS, additional build option required
                global build_opts
                build_opts = ['/p:platform="Win32"']

        if len(projects) > 0:
            lprint('generated projects: ' + ', '.join(projects))

        return projects

    def msbuild(self, proj):
        output = None
        compile_command = ''
        if Path('build.log').exists() and config['ignore_bb'] is False:
            lprint('using build.log')
            #  output = open('build.log', 'rb').read()
            output = open('build.log').read().split('\n')
        else:
            opts = ["msbuild.exe", "/t:Rebuild"]
            if len(build_opts) > 0:
                opts.extend(build_opts)
            if len(proj) > 0:
                opts.append(proj)
            compile_command = ' '.join(opts)
            lprint('{' + compile_command + '}')

            build = subprocess.Popen(compile_command,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    stdin = subprocess.PIPE, shell = True)
            output, _  = build.communicate()
            if build.returncode != 0:
                lprint('msbuild run with error. compilation_database may be incomplete')
                #  os._exit(1)

            open('build.log', 'wb').write((compile_command + '\n').encode('utf-8')  + output)

            output = output.decode('cp866')
            output = output.split('\r\n')

        self.init_tags()
        self.parse_buffer(output)

    def parse_buffer(self, bld):
        log('\n\n\n>>> parse buffer\n')
        cl_match = re.compile('^.*[Cc][Ll]\.[Ee][Xx][Ee](.*)$')  # may broke everything!
        chdir_match = re.compile('^.*\".*\.sln\".*\"(.*)\\\\(.*\.vcxproj)\"');
        for line in bld:
            # find compilation lines
            compile_line = cl_match.match(line)
            if compile_line is not None:
                cl = compile_line.group(1).replace('\r\n', ' ').strip(' ')
                log('parse line: [' + cl + ']\n')

                self.dir = os.getcwd().replace("\\", "/")
                self.inc = I
                self.defs = D
                self.opts = []
                self.flags = [
                        '-std=c++17', '-x', 'c++',
                        '-fms-compatibility-version=19.00',
                        '-fms-extensions',
                        '-fms-compatibility',
                        ]
                while len(cl) > 0:
                    for tag_name in self.tags:
                        tag_regexp, foo = self.tags[tag_name]
                        match = re.match(tag_regexp, cl)
                        if match is None:
                            continue

                        foo(match.groups())
                        cl = re.sub('({re})'.format(re = tag_regexp), ' ', cl).strip(' ')
                        break
                    else:
                        lprint("unknown tag [" + cl.split(' ')[0] + "]. Bailout...")
                        os._exit(1)

                continue

            #  print(line)
            chdir = chdir_match.match(line)
            if chdir is not None:
                self.path = chdir.groups()[0].replace('\\', '/')
                run_path = str(Path('.').absolute()).replace('\\', '/')
                self.rel_path = os.path.relpath(self.path, run_path).replace('\\', '/') + '/'
                print('chdir ' + self.rel_path)

    def definition(self, groups):
        definition = groups[0]
        if definition in self.defs:
            return
        if definition.startswith('"'):
            return;
        log('definition: [' + definition + ']\n')
        self.defs.append(definition)

    def include(self, groups):
        path = groups[0].replace('\\', '/')
        if path in replaceable_path:
            path = replaceable_path[path]
        if len(path) == 0 or path in self.inc or path in self.sys_inc:
            return
        if not os.path.isabs(path):
            log('-I: [' + path + ']\n')
            path = self.rel_path + path
            self.inc.append(path)
        else:
            self.sys_inc.append(path)

    def skip(self, groups):
        log('skip tag: [' + groups[0] + ']\n')
        pass

    def source(self, groups, match_header = True):
        path = groups[0].replace('\\', '/')
        if match_header is True:
            hdr_match = re.match("^(.*)\.(?:c|cpp|cxx)$", path)
            if hdr_match.groups() is not None:
                header = '{f}.h'.format(f = hdr_match.groups()[0])
                if Path(self.rel_path + header).exists():
                    self.source([header], False)

        if not Path(self.rel_path + path).exists():
            lprint('file ' + self.rel_path + path + ' is unreachable ***WARNING***')

        src = source_file(
                self.rel_path + path,
                self.dir,
                self.flags,
                self.defs,
                self.inc,
                self.sys_inc,
                self.header_inc,
                self.pch)
        for source in self.files:
            if source.file == src.file:
                lprint(path + ' dup ***WARNING***')
                if source.optlen() < src.optlen():
                    source.flags = src.flags
                    source.defs = src.defs
                    source.inc = src.inc
                    source.sys_inc = src.sys_inc
                    source.finc = src.finc
                    source.pch = src.pch
                    source.command = src.command
                break
        else:
            lprint(path)
            self.files.append(src)

    def include_file(self, groups):
        log('file include: ' + groups[0] + '\n')
        inc = self.rel_path + groups[0].replace("\\", "/")
        if not Path(inc).exists():
            lprint('file ' + inc + ' is unreachable ***WARNING***')

        if self.header_inc is not None and len(self.header_inc) > 0 and self.header_inc != inc:
            lprint('global include file "' + self.header_inc + '" was overriden by "' + inc + '" ***WARNING***')
        self.header_inc = inc

    def emit_pch(self, groups):
        lprint('DISABLED: emit pch: {pch}.pch'.format(pch = groups[0]))
        return
        command = 'clang -cc1 {hdr} -emit-pch -o {pch}.pch'.format(
            hdr = self.header_inc,
            pch = groups[0]).split(' ')
        command.extend(self.flags)
        for d in self.defs:
            command.extend(['-D', d])
        for inc in self.inc:
            command.extend(['-I', inc])
        for inc in self.sys_inc:
            command.extend(['-isystem', inc])
        command.extend(['-include', self.header_inc])
        clang = subprocess.Popen(command,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                stdin = subprocess.PIPE
                )
        clang.communicate()
        if clang.returncode != 0:
            log('failed to create pch: ' + groups[0] + '\n')
            return
        log('emit pch: ' + groups[0] + '\n')
        self.pch = "{pch}.pch".format(pch = groups[0])

    def init_tags(self):
        self.tags = {
                'definition': ['^[/-]D\s*([^ ]*)', self.definition],
                'include_0': ['^[/-]I\s*"([^"]+)"', self.include],
                'include_1': ['^[/-]I\s*([^ ]*)', self.include],
                'emit_pch': ['^/Y[cu]"([^"]+\.(h|hpp|hxx))"', self.include_file],
                '/skip_flags': ['^([/-][a-zA-Z]([^ ]*))', self.skip],
                'source': ['^"?([^ $]+\.(cpp|cxx|cs|cc|c))"?', self.source],
                }

    def compilation_database(self):
        if len(self.files) == 0:
            lprint('no files to generate compilation_database')
            return
        lprint('generating compile_commands.json');
        with open('compile_commands.json', 'w') as js:
            js.write('[')
            js.write(',\n'.join([f.toJSON() for f in self.files]))
            js.write(']')

        cleanup()

    def extra_conf(self):
        if len(self.files) == 0:
            lprint('no files to generate compilation_database')
            return
        lprint('generating .ycm_extra_conf.py (warn: experimental)');
        flags = []
        flags_writeable = '        \'-include\', \'c:/.config/cc_dev.h\',\n'

        for source in self.files:
            if source.finc is not None:
                value = '-include "{f}"'.format(f = source.finc)
                if value not in flags:
                    flags.append(value)
                    flags_writeable = flags_writeable + '        \'-include\', \'' + source.finc + '\',\n'

            for F in source.flags:
                if F not in flags:
                    flags.append(F)
                    flags_writeable = flags_writeable + '        \'' + F + '\',\n'

            for D in source.defs:
                value = '-D {f}'.format(f = D)
                if value not in flags:
                    flags.append(value)
                    flags_writeable = flags_writeable + '        \'-D\', \'' + D + '\',\n'
            for inc in source.sys_inc:
                value = '-isystem "{f}"'.format(f = inc)
                if value not in flags:
                    flags.append(value)
                    flags_writeable = flags_writeable + '        \'-isystem\', \'' + inc + '\',\n'
            for inc in source.inc:
                value = '-I "{f}"'.format(f = inc)
                if value not in flags:
                    flags.append(value)
                    flags_writeable = flags_writeable + '        \'-I\', \'' + inc + '\',\n'

        with open('.ycm_extra_conf.py', 'w') as f:
            f.write(ycm_extra_conf_pattern.replace('$FLAGS$', flags_writeable))

if __name__ == '__main__':
    exit_reason = []
    if len(sys.argv) > 1 and sys.argv[1] == 'clean':
        cleanup(True)
        os._exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == 'clean_all':
        cleanup(True, True)
        os._exit(1)
    if 'INCLUDE' not in os.environ:
        exit_reason.append('no development environment or build.log')

    if Path('./compile_commands.json').exists() and config['ignore_cc'] is False:
        exit_reason.append('compile_commands.json already exists');

    if len(exit_reason) > 0:
        [lprint('error: ' + line) for line in exit_reason]
        os._exit(1)
    p = command_parser()

    projects = []
    for idx in range(1, len(sys.argv)):
        if sys.argv[idx].startswith("/"): # exclude parameters
            build_opts.append(sys.argv[idx])
        else:
            projects.append(sys.argv[idx])

    if not Path('./build.log').exists() or config['ignore_bb'] is True:
        projects = p.qmake()
        if len(projects) == 0:
            projects = [f for f in os.listdir('./') if re.match('^.*\.vcxproj$', f) is not None]

        if len(projects) == 0:
            lprint('*.vcxproj name required. Nothing to build...')
            os._exit(0)

    if Path("./build.log").exists() and config['ignore_bb'] is False:
        p.msbuild(None)
    else:
        for proj in projects:
            p.msbuild(proj)

    p.compilation_database()
    p.extra_conf()

