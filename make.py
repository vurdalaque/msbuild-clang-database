from pathlib import Path
import os, sys, re

os.environ['PYTHONDONTWRITEBYTECODE']='1'  # must be set outside of the script
os.environ['VSLANG'] = '1033'
os.environ['NO_UPDATE_NNLAB_EXTERNAL'] = '1'
os.environ['VSCMD_ARG_no_logo'] = '1'

archs = ['8.1', 'x86', 'x64']
vcvars32 = r'C:\Program Files (x86)\Microsoft Visual Studio\2017\Professional\VC\Auxiliary\Build\vcvars32.bat'
arch = '8.1'

args = sys.argv[1:]
arches = [arg for arg in args if arg in archs]
if len(arches) != 0:
    arch = arches[0]
    [args.remove(a) for a in arches]

init_environment = ''
if 'INCLUDE' not in os.environ:
    init_environment = '"{vcvars32}" {a} & '.format(vcvars32 = vcvars32, a = arch)

def search_in_args(in_arg):
    global args
    arg = [in_arg] if type(in_arg) != type([]) else in_arg
    _args = [a for a in arg if a in args]
    [args.remove(a) for a in _args]
    return _args

def run_msbuild(project):
    global args
    keys = search_in_args(['release', 'debug', 'dllrelease', 'clean', 'mt', 'only'])
    build_params = []
    for key in keys:
        if key == 'release':
            build_params.append('/p:configuration=release')
        elif key == 'debug':
            build_params.append('/p:configuration=release')
        elif key == 'dllrelease':
            build_params.append('/p:configuration=DllRelease')
        elif key == 'clean':
            build_params.append('/t:clean')
        elif key == 'mt':
            build_params.append('/m /p:BuildInParallel=true')
        elif key == 'only':
            build_params.append('/p:BuildProjectReferences=false')
        else:
            print('unused key:', key)
            os._exit(0)

    args = ' '.join(args)
    os.system('@start /max cmd.exe @cmd /k "{init_environment} msbuild /nologo {keys} {args} {project} & pause & exit" '.format(
        keys = ' '.join(build_params),
        args = args,
        project = project,
        init_environment = init_environment))



def run_make_from_ycm_extra_conf():
    import importlib.machinery as m
    module = m.SourceFileLoader('conf', './.ycm_extra_conf.py')
    conf = module.load_module()
    params = conf.build_parameters()
    project = f'{params["directory"]}/{params["project"]}'
    if not Path(project).exists():
        print('failed to run from .ycm_extra_conf: path {p} not exists'.format(p = project))
        return
    run_msbuild(project)

def run_make():
    global args
    args = ' '.join(args)
    os.system('@start /max cmd.exe @cmd /k "{init_environment} nmake /nologo {args} & pause & exit" '.format(
        args = args,
        init_environment = init_environment))

if __name__ == '__main__':
    if Path('./Makefile').exists() or Path('./makefile').exists():
        run_make()
        os._exit(0)

    vcxprojs = []
    for proj_file in os.listdir('./'):
        if re.match('^.*\.vcxproj$', proj_file): #  and proj_file not in ['ALL_BUILD.vcxproj', 'ZERO_CHECK.vcxproj', 'RUN_TESTS.vcxproj']:
            vcxprojs.append(proj_file)

    if len(sys.argv) >= 2:
        if sys.argv[1] in vcxprojs:
            vcxprojs = [sys.argv[1]]
            args = args[1:]
        if sys.argv[1] + '.vcxproj' in vcxprojs:
            vcxprojs = [sys.argv[1] + '.vcxproj']
            args = args[1:]

    if len(vcxprojs) == 1:
        project = vcxprojs[0]
        run_msbuild(project)
        os._exit(0)

    if Path('./.ycm_extra_conf.py').exists():
        run_make_from_ycm_extra_conf()
        os._exit(0)
    print('No makefile, .vcxproj or .ycm_extra_conf found. Nothing to do...')
