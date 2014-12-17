import os,sys
import yaml
from subprocess import Popen, PIPE
import logging

class dotdictify(dict):
    """
        http://stackoverflow.com/questions/3031219
        Creates dictionary accessible via attributes or keys.
    """
    marker = object()
    def __init__(self, value=None):
        if value is None:
            pass
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            raise TypeError, 'expected dict'

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, dotdictify):
            value = dotdictify(value)
        dict.__setitem__(self, key, value)

    def __getitem__(self, key):
        found = self.get(key, dotdictify.marker)
        if found is dotdictify.marker:
            found = dotdictify()
            dict.__setitem__(self, key, found)
        return found

    __setattr__ = __setitem__
    __getattr__ = __getitem__


def setup_logger(config):
    # Set up Logger
    log = logging.getLogger("pyPipeline")
    analysis_dir = config.OPTIONS.analysis_dir
    fh = logging.FileHandler(analysis_dir + "/" + analysis_dir + ".log")
    # Setup Formatting
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # Set formats
    fh.setFormatter(formatter)
    log.addHandler(fh)
    if config.DEBUG == True:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    return log

class command_log:
    def __init__(self, config):
        analysis_dir = config.OPTIONS.analysis_dir
        self.log = open(analysis_dir + "/commands.log",'a')
    def add(self, command):
        self.log.write(command)

def load_config_and_log(config, job_type):
    """ 
        Loads the configuration file
            - Inherits default options not specified
            - Inherits options only for the job type specified.
    """
    default = dotdictify(ya=ml.load(open("default.config.yaml","r")))
    config = dotdictify(yaml.load(open(config, 'r')))
    # Create analysis directory.
    makedir(config.OPTIONS.analysis_dir)
    # Override Options
    for opt,val in default["OPTIONS"].items():
        if opt not in config["OPTIONS"].keys():
            config["OPTIONS"][opt] = val
    # Override command options for those specified
    for comm in config["COMMANDS"][job_type].keys():
        for opt,val in default["COMMANDS"][job_type][comm].items():
            if config["COMMANDS"][job_type][comm] is not None:
                print config
                if opt not in config["COMMANDS"][job_type][comm].keys():
                    config["COMMANDS"][job_type][comm][opt] = val
            else:
                # If no options are set in the analysis configuration
                # set it up now.
                config["COMMANDS"][job_type][comm] = {}
                config["COMMANDS"][job_type][comm][opt] = val
    general_log = setup_logger(config)
    c_log = command_log(config)
    return config, general_log, c_log

def format_command(command_config):
    """
        Performs standard formatting of commands being run.
    """
    if "__command__" in command_config:
        first_arg = command_config["__command__"]
    opts = ""
    for k,v in command_config.items():
        if k != "__command__":
            opts += "%s %s " % (k,v)
    return first_arg, opts

def file_greater_than_0(filename):
    if os.path.isfile(filename) and os.path.getsize(filename) > 0:
        return True
    else:
        return False

def makedir(dirname):
  if not os.path.exists(dirname):
    os.mkdir(dirname)


def command(command, log):
    """ Run a command on system and log """
    log.add(command.strip() + "\n")
    command = Popen(command, shell=True, stdout=PIPE)
    for line in command.stdout:
        print(line)
    if command.stderr is not None:
        raise Exception(command.stderr)

def which(program):
    """ returns the path to an executable or None if it can't be found
     http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
     """
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

def version(program):
    """ Attempts to return the version of an executable or None if it can't be found. """
    prog = which(program)
    if program not in ["tabix"]:
        try:
            version = Popen([prog,"--version"], stdout=PIPE).communicate()[0]
            version = version.strip().split("\n")[0]
            return "%-50s\t%s" % (prog, version)
        except:
            return None
    else:
        # Hand special cases
        pass

def common_prefix(strings):
    """ Find the longest string that is a prefix of all the strings.
     http://bitbucket.org/ned/cog/src/tip/cogapp/whiteutils.py
    """
    if not strings:
        return ''
    prefix = strings[0]
    for s in strings:
        if len(s) < len(prefix):
            prefix = prefix[:len(s)]
        if not prefix:
            return ''
        for i in range(len(prefix)):
            if prefix[i] != s[i]:
                prefix = prefix[:i]
                break
    return prefix

def get_script_dir():
    return os.path.dirname(os.path.realpath(__file__)).replace("/utils", "")


# Define Constants

script_dir = get_script_dir()


