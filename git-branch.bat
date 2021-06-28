0<0# : ^
'''
@echo off
python "%~f0" %*
exit /b 0
'''
import sys, os, subprocess, msvcrt, re as regex

class config:
    enc = 'utf8'
    #  no_description = '{sc}{mark} {branch:<{width}}{ec} {last_commit}'
    #  has_description ='{sc}{mark} {branch:<{width}}{ec} {ds}{description}{ec}\n   {spaces:<{width}}{last_commit}'
    no_description = '{sc}{mark} {branch:<{width}}{ec}'
    has_description ='{sc}{mark} {branch:<{width}}{ec}{br} {ds}{description}{ec}'


re = [ r'^(.)\s+([^\s]+)\s+([^\s]+)\s+(.*)$', '^(.*)\n\n$' ]
re = [regex.compile(r) for r in re]
from colorama import init, AnsiToWin32, Fore, Back, Cursor
init(wrap=False)
stream = AnsiToWin32(sys.stdout).stream

def git_execute(command):
    print('{sc}{msg}{ec}'.format(sc=Fore.LIGHTGREEN_EX, ec=Fore.RESET, msg=command), file=stream)
    cmd = subprocess.Popen(command,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            stdin = subprocess.PIPE)
    stdout, stderr = cmd.communicate()
    if cmd.returncode != 0:
        print('{sc}{msg}{ec}'.format(sc=Fore.RED, ec=Fore.RESET, msg=stderr.decode(config.enc)), file=stream)
    print(stdout.decode(config.enc), file=stream)
    print(stderr.decode(config.enc), file=stream)

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

menu = []

for branch in branches:
    color = Fore.WHITE
    if branch.mark == '*':
        color = Fore.GREEN
    if branch.mark == '+':
        color = Fore.CYAN
    fmt = config.has_description if len(branch.description) > 0 else config.no_description
    line = fmt.format(
            sc=color,
            ec=Fore.RESET,
            br=Back.RESET,
            ds=Fore.LIGHTWHITE_EX,
            width=max_len,
            spaces=' ',
            mark=branch.mark,
            branch=branch.name,
            description=branch.description,
            last_commit=branch.last_commit)

    menu.append((line, branch.name))


class Menu:

    def __init__(self, items):
        self.current_item = 0
        self.previous_item = -1
        self.items = items
        self.items_count = len(items)
        for item in items:
            print(item[0], file=stream)
        print(Cursor.UP(self.items_count + 1), file=stream)
        self.display()

    def display(self):
        if self.previous_item == self.current_item:
            return
        if self.previous_item >= 0:
            print(Back.RESET + self.items[self.previous_item][0] + Cursor.UP(), file=stream)
            print(Cursor.UP() if self.previous_item > self.current_item else Cursor.DOWN(), file=stream, end='')

        if self.current_item < 0:
            return
        print(Back.LIGHTBLUE_EX + self.items[self.current_item][0] + Cursor.UP(), file = stream)
        self.previous_item = self.current_item

    def reset_selection(self):
        self.previous_item = self.current_item
        self.current_item = -1
        self.display()
        self.current_item = self.previous_item

    def loop(self):
        ctrl_spec = False
        while True:
            ch = ord(msvcrt.getch())
            if ch == 0:
                ctrl_spec = True
                continue
            if ch == 27 or ch == ord('q'):
                self.reset_selection()
                break
            if ch == 80 or ch == 9 or ch == ord('j'):
                self.previous_item = self.current_item
                self.current_item += 1

            if ch == 72 or ch == ord('k') or (ctrl_spec and ch == 148):
                self.previous_item = self.current_item
                self.current_item -= 1

            if ch == 13 or ch == 32:
                self.reset_selection()
                print(Cursor.DOWN(self.items_count - self.previous_item), file=stream, end='\n\n')
                git_execute("git checkout {branch_name}".format(branch_name = self.items[self.previous_item][1]))
                break

            if ch == ord('e'):
                self.reset_selection()
                print(Cursor.DOWN(self.items_count - self.previous_item), file=stream, end='\n\n')
                git_execute("git branch --edit-description")
                break

            if ch == ord('d'):
                self.reset_selection()
                print(Cursor.DOWN(self.items_count - self.previous_item), file=stream, end='\n\n')
                git_execute("git branch -d {branch_name}".format(branch_name = self.items[self.previous_item][1]))
                break

            if ch == ord('D'):
                self.reset_selection()
                print(Cursor.DOWN(self.items_count - self.previous_item), file=stream, end='\n\n')
                git_execute("git branch -D {branch_name}".format(branch_name = self.items[self.previous_item][1]))
                break

            if self.current_item < 0:
                self.current_item = -1
                self.display()
                print(Cursor.DOWN(self.items_count - 1), file=stream)
                self.previous_item = -1
                self.current_item = self.items_count - 1

            if self.current_item >= self.items_count:
                self.current_item = -1
                self.display()
                print(Cursor.UP(self.items_count - 1), file=stream)
                self.previous_item = -1
                self.current_item = 0

            ctrl_spec = False
            self.display()



if __name__ == '__main__':
    if len(menu) == 0:
        exit()

    m = Menu(menu)
    m.loop()

