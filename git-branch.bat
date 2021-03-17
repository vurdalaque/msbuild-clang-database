0<0# : ^
'''
@echo off
python "%~f0" %*
exit /b 0
'''
import sys, os, subprocess, re as regex

class config:
    enc = 'utf8'
    #  no_description = '{sc}{mark} {branch:<{width}}{ec} {last_commit}'
    #  has_description ='{sc}{mark} {branch:<{width}}{ec} {ds}{description}{ec}\n   {spaces:<{width}}{last_commit}'
    no_description = '{sc}{mark} {branch:<{width}}{ec}'
    has_description ='{sc}{mark} {branch:<{width}}{ec} {ds}{description}{ec}'


re = [ r'^(.)\s+([^\s]+)\s+([^\s]+)\s+(.*)$', '^(.*)\n\n$' ]
re = [regex.compile(r) for r in re]
from colorama import init, AnsiToWin32, Fore
init(wrap=False)
stream = AnsiToWin32(sys.stdout).stream

branch = subprocess.Popen("git branch -v --no-color",
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        stdin = subprocess.PIPE)

stdout, stderr = branch.communicate()
if branch.returncode != 0:
    print('{sc}{msg}{ec}'.format(sc=Fore.RED, ec=Fore.RESET, msg=stderr.decode(config.enc)), file=stream)
    os._exit(1)

class branch:
    def __init__(self, mark, branch_name, hsh, last_commit, description):
        self.mark = mark
        self.name = branch_name
        self.hsh = hsh
        self.last_commit = last_commit
        self.description = description

branches = []

for line in stdout.decode(config.enc).split('\n'):
    m = re[0].match(line);
    if len(line) == 0:
        continue
    if m is None or len(m.groups()) == 0:
        print('{sc}{msg}{ec}'.format(sc=Fore.RED, ec=Fore.RESET, msg=u'regex is fucked up'), file=stream)
        os._exit(1)

    description = subprocess.Popen(
            'git config branch.{branch}.description'.format(branch=m.group(2)),
            stdout = subprocess.PIPE);
    d, _ = description.communicate()
    d = re[1].match(d.decode(config.enc)).group(1) if len(d) != 0 else ''
    branches.append(branch(m.group(1), m.group(2), m.group(3), m.group(4), d))

max_len = 0
for branch in branches:
    max_len = max(max_len, len(branch.name))

for branch in branches:
    color = Fore.WHITE
    if branch.mark == '*':
        color = Fore.GREEN
    if branch.mark == '+':
        color = Fore.CYAN
    fmt = config.has_description if len(branch.description) > 0 else config.no_description

    print(fmt.format(
        sc=color, ec=Fore.RESET, ds=Fore.GREEN,
        width = max_len,
        spaces=' ',
        mark=branch.mark,
        branch=branch.name,
        description=branch.description,
        last_commit=branch.last_commit
        ) , file=stream)

