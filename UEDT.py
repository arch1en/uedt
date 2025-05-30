#region License
"""
    MIT License
    
    Copyright (c) 2024 Artur "Arch1eN" Ostrowski
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""
#endregion License

"""
    UEDT should be in the project directory, next to the 'uproject' file. 
"""

"""
    Config
"""

class Config:
    # Compilation
    CompilationConfiguration = "Shipping"
    # Build
    BuildStagingDir = "E:/_Builds" # / ProjectName / ConfigurationName
    BuildConfiguration = "Development" # Development | Test | Shipping | Release 
    
    # Whitelist maps that will be added to the build.
    # If, array is empty, map parameter during cooking process will be ignored.
    Maps =  [
    ]

"""
    Code
"""

import os
import re
import sys
import glob
import shutil
import logging
import argparse
import platform
import subprocess

from abc import ABC

from pathlib import Path
from enum import IntFlag, auto

c = Config


#region Classes
class PerforceHandler:

    def GetDefaultCharSet(self):
        return "latin-1"

    def SubmitChangelist(self, targetChangelist:int = -1):
        if targetChangelist == -1:
            return
        
        Args = f"{self.__GetPreliminaryCommandArgs()} submit -c {targetChangelist}"

        Response, OK = HandleCommand(Args.split())

        if OK and self.__GetResponseReturnCode(Response) == 0:              
            return OK

        raise ConnectionError

    # @ret - New changelist number.
    def CreateNewChangelist(self, description) -> int:
        Args = f"{self.__GetPreliminaryCommandArgs()} --field \"Description={description}\" --field \"Files=\" change -o"

        ps = subprocess.Popen(Args, stdout=subprocess.PIPE)
        output = subprocess.check_output(f"{self.__GetPreliminaryCommandArgs()} change -i", stdin=ps.stdout)
        ps.wait()

        Regex = re.compile(r"^Change (\d+)")
        
        found = re.search(Regex, output.decode(self.GetDefaultCharSet()))

        changelistNumber = -1

        if len(found.groups()) > 0:
            changelistNumber = int(found.group(1))
        else:
            raise ConnectionError

        return changelistNumber

    # Checkout files.
    def EditFiles(self, targetChangeList = -1, filePaths=[]):
        filePathsChecked = self.__RetrieveExistingFiles(filePaths)

        Args = self.__GetPreliminaryCommandArgs() + "edit" 

        if targetChangeList != -1:
            Args += f" -c {targetChangeList}"

        Args += f" " + ' '.join(str(x) for x in filePathsChecked)

        Response, OK = HandleCommand(Args.split())

        if OK and Response is not None:
            shouldUseReopen = Response.stdout.decode(self.GetDefaultCharSet()).find('reopen') != -1
            if shouldUseReopen:
                return self.ReopenFiles(targetChangeList, filePaths)

        return OK

    # Process files that are already checked out.
    def ReopenFiles(self, targetChangeList = -1, filePaths = []):
        filePathsChecked = self.__RetrieveExistingFiles(filePaths)

        Args = self.__GetPreliminaryCommandArgs() + "reopen" 

        if targetChangeList != -1:
            Args += f" -c {targetChangeList}"

        Args += f" " + ' '.join(str(x) for x in filePathsChecked)

        Response, OK = HandleCommand(Args.split())
        if OK and self.__GetResponseReturnCode(Response) == 0:
            return OK

        raise ConnectionError

    def RevertFiles(self, filePaths):
        filePathsChecked = self.__RetrieveExistingFiles(filePaths)

        Args = f"{self.__GetPreliminaryCommandArgs()} revert -a " + ' '.join(str(x) for x in filePathsChecked)

        Response, OK = HandleCommand(Args.split())
        if OK and self.__GetResponseReturnCode(Response) == 0:
            return OK
        raise ConnectionError

    def __GetPreliminaryCommandArgs(self):
        return f"p4 -p {c.P4ServerAddress}:{str(c.P4ServerPort)} -u {c.P4User} -P {c.P4Ticket} -c {c.P4Workspace} "

    def __RetrieveExistingFiles(self, filePaths):
        filePathsChecked = []
        for i in filePaths:
            if os.path.isfile(i) == True:
                filePathsChecked.append(i)
        
        return filePathsChecked

    def __GetResponseReturnCode(self, response):
            responseMsg = str(response)
            regex = re.compile(r"returncode=(\d+)")
            found = re.search(regex, responseMsg)
            if len(found.groups()) > 0:
                return int(found.group(1))
            return -1

class Command(ABC):
   
    def __init__(self, *args, **kwargs) -> None:
        self._Execute(args[0])
    
    def _Execute(self, args):
        pass
#endregion Classes

#region Objects
perforceHandler = PerforceHandler()
#endregion Objects

#region Functions 

def HandleCommand(Arguments, LiveLog=False):
    OK = True
    Response = None

    try:
        if LiveLog:
            OK = not subprocess.Popen(Arguments).wait()
        else:
            Response = subprocess.run(Arguments, capture_output=True, timeout=10)
            if Response.returncode != 0:
                logging.getLogger().error(Response.stderr)
                OK = False

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"command {e.cmd} return with error (code {e.returncode}): {e.output}")
    except subprocess.TimeoutExpired as e:
        logging.getLogger().error(f"Command {Arguments} timeout expired.")

    return Response, OK

# Returns full path to the project's 'uproject' file.
# Eg. C:/Project/Project.uproject
def GetUProjectPath():
    for root, dirs, files in os.walk(GetProjectDir()):
        for file in files:
            if file.endswith(".uproject"):
                return Path(os.path.join(root, file))

def GetProjectDir():
    return Path(os.path.dirname(os.path.realpath(__file__)))

def GetProjectFileName():
    return str(GetUProjectPath()).split(os.sep)[-1]

def GetProjectName():
    return GetProjectFileName().split(".")[0]

def GetUATPath():
    return Path(GetAssociatedEngineDir()) / 'Engine/Build/BatchFiles/RunUAT.bat'

def GetUProjectFileData():
    import json
    
    with open(GetUProjectPath(), 'r') as f:
        try:
            json_object = json.loads(f.read())
            return json_object
        except ValueError as e:
            logging.getLogger().error(f"Cannot parse {GetUProjectPath()} file. {e}")
            sys.exit(1)
    
# [TestRequired]
def GetAssociatedEngineDir():
    data = GetUProjectFileData()
    path = []
    
    # Distinguish source and launcher engine association.
    if data['EngineAssociation'].startswith('{'):
        path = GetRegistryData(f"HKCU:Software/Epic Games/Unreal Engine/Builds/{data['EngineAssociation']}")
    else:
        path = GetRegistryData(f"HKLM:SOFTWARE/EpicGames/Unreal Engine/{data['EngineAssociation']}/InstalledDirectory")
        
    #path = Path(GetRegistryData(f"HKLM:SOFTWARE/EpicGames/Unreal Engine/{data['EngineAssociation']}/InstalledDirectory")[0])
    
    return Path(path[0])

def GetAssociatedEngineBinariesDir():
    BinariesDir = GetAssociatedEngineDir() / "Engine" / "Binaries"
    if platform.uname().system == "Windows":
        BinariesDir /= "Win64"
    else:
        raise NotImplementedError
    
    return BinariesDir

def GetRegistryData(RegistryPath):
    if os.sys.platform == "win32":
        import winreg

        RegType, RegPath = RegistryPath.split(":")

        RegistryType = {
            'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKU': winreg.HKEY_USERS,
            'HKCC': winreg.HKEY_CURRENT_CONFIG
        }[RegType]

        try:
            AccessRegistry = winreg.ConnectRegistry(None, RegistryType)
        except OSError as e:
            logging.getLogger().info(f"Cannot connect to {RegistryType} : {e}")
            return None

        RegPath = RegPath.replace("/","\\")
        RegPath, RegKeyName = RegPath.rsplit("\\", 1)
        
        try: 
            RegKey = winreg.OpenKey(AccessRegistry, RegPath)
        except OSError as e:
            logging.getLogger().info(f"Cannot open {RegPath} registry.")
            return None

        Values = winreg.QueryValueEx(RegKey, RegKeyName)
        if len(Values) < 1:
            logging.getLogger().info(
                f"Cannot retrieve data from {RegKeyName} registry in {RegistryType}\\{RegPath}.")
            return None

        if Values[0].find(";"):
            Values = Values[0].split(';')

        Result = [v for v in Values if len(v) > 0]

        return Result
    else:
        raise NotImplemented

def RemoveDir(path):
    shutil.rmtree(path, ignore_errors=False, onerror=RmTreeHandleError)


def RemoveFile(path):
    os.remove(path)

def RmTreeHandleError(func, path, exc_info):
    print("Cannot remove files from path " + str(path))

def GetUnrealInsightsPath():
    return GetAssociatedEngineBinariesDir() / "UnrealInsights.exe"

def GetUnrealFrontEndPath():
    return GetAssociatedEngineBinariesDir() / "UnrealFrontend.exe"

def IsProcessRunning(process_name):
    try:
        import psutil
    except ImportError:
        logging.error("Required module \"psutil\" not found. Use \"pip install psutil\" or \"pip3 install psutil\"")
        sys.exit(1)
        
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            return True
    
    return False

def FireAndForgetProcess(Args):
    try:
        kwargs = {}
        if platform.uname().system == 'Windows':
            # from msdn [1]
            CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
            DETACHED_PROCESS = 0x00000008          # 0x8 | 0x200 == 0x208
            kwargs.update(creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)  
        elif sys.version_info < (3, 2):  # assume posix
            kwargs.update(preexec_fn=os.setsid)
        else:  # Python 3.2+ and Unix
            kwargs.update(start_new_session=True)

        p = subprocess.Popen(Args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        assert not p.poll()
        return p
    except Exception as e:
        logging.error(f"Cannot fire and forget process. {e} ({Args})")
        sys.exit(1)
        
def LaunchUnrealInsights():
    if not IsProcessRunning("UnrealInsights.exe"):
        FireAndForgetProcess([f"{GetUnrealInsightsPath()}"])
        logging.info("Launching UnrealInsights...")
        return True
    else:
        logging.info("UnrealInsights process detected. Skipping launching...")
        
    return False

#endregion Functions

#region Command Classes
"""
    Command Classes
"""

class Clean(Command):
    def _Execute(self, args):
        ProjectDir = GetProjectDir()
        
        DirsToRemove = [
            "Binaries",
            "Intermediate",
            "Saved/Autosaves",
            "Saved/Backup",
            "Saved/Diff"
        ]
        
        PathsToRemove = [ProjectDir / x for x in DirsToRemove]

        for path in PathsToRemove:
            path = Path(path)
            if os.path.exists(path):
                RemoveDir(path)

        for mainPath in glob.glob(str(ProjectDir) + "/Plugins/*"):
            for dirToRemove in DirsToRemove:
                finalPath = Path(mainPath) / dirToRemove
                if os.path.exists(finalPath):
                    RemoveDir(finalPath)
        

        for file in os.listdir(ProjectDir):
            if file.endswith(".sln"):
                FilePath = os.path.join(ProjectDir, file)
                if os.path.exists(FilePath):
                    RemoveFile(FilePath)

        print("Clean Up Ended.")

class Build(Command):
    def _Execute(self, args):
        
        BuildConfiguration = ""

        if args.get("configuration") is not None:
            BuildConfiguration = args.get("configuration")
        elif args.get("c") is not None:
            BuildConfiguration = args.get("c")
        else:
            BuildConfiguration = c.BuildConfiguration
        
        ActualBuildConfiguration = BuildConfiguration

        if ActualBuildConfiguration == "Release":
            ActualBuildConfiguration = "Shipping"

        logging.getLogger().info("--------------------------------")
        logging.getLogger().info(f"Build Configuration : {BuildConfiguration}")
        logging.getLogger().info("--------------------------------")

        Args = [
            f"{str(GetUATPath())}",
            "BuildCookRun",
            f"-ue4exe={str(Path(GetAssociatedEngineDir()) / 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe')}",
            f"-project={str(Path(GetUProjectPath()))}",
            f"-clientconfig={ActualBuildConfiguration}",
            f"-serverconfig={ActualBuildConfiguration}",
            "-targetplatform=Win64",
            "-platform=Win64",
            "-noP4",
            "-build",
            "-cook", # cook -
            "-stage",
            f"-stagingdirectory={str(Path(c.BuildStagingDir) / GetProjectName() / BuildConfiguration)}",
            # Due to problems with blueprint nativization, it is by default disabled in building process.
            "-ini:Game[/Script/UnrealEd.ProjectPackagingSettings]:BlueprintNativizationMethod=Disabled",
            #"-nocompileeditor",
            "-installed",
            "-unversionedcookedcontent",
            "-compressed",
            f"-map={'+'.join(c.Maps)}",
            ("-distribution" if BuildConfiguration == "Release" else ""), # 
            ("-encryptinifiles" if BuildConfiguration == "Release" else ""), # 
            ("-skipeditorcontent" if BuildConfiguration == "Release" else ""), # 
            ("-skipcookingeditorcontent" if BuildConfiguration == "Release" else ""), # 
            ("-pak" if BuildConfiguration == "Release" else ""), # 
            "-fullrebuild"
            #"-clean",
            #"-iterativecooking"
        ]

        try:
            BuildProcess = subprocess.Popen(Args).wait()
        except:
            pass

class FixBinaryPermissions(Command):
    def _Execute(self, args):
        import stat

        extensions = ['.dll', '.pdb', '.modules', '.target', '.uproject']
        files = [os.path.join(root, f) for root, dirs, filenames in os.walk(GetProjectDir()) for f in filenames if any(f.endswith(ext) for ext in extensions ) ]

        result = True

        for file in files:
            if not os.access(file, os.W_OK):
                os.chmod(file, stat.S_IWUSR)
                if not os.access(file, os.W_OK):
                    print(f"Cannot fix permissions for {file}")
                    result = False

        if result == True:
            print("Permissions fixed successfuly!")
        else:
            print("Unable to fix all permissions.\n Check if account that you are logged on is an owner of these files or if you need to launch the script as an administrator.")

class RebuildLighting(Command):
    def _Execute(self):
        logging.getLogger().info("--------------------------------")
        logging.getLogger().info(f"Rebuild Lighting Started")
        logging.getLogger().info("--------------------------------")

        Args = [
            f"{str(Path(GetAssociatedEngineDir()) / 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe')}",
            f"{str(Path(GetUProjectPath()))}",
            "-run=resavepackages",
            "-buildlighting",
            "-quality=Production",
            "-allowcommandletrendering",
            f"-map={'+'.join(c.Maps)}",
        ]

        try:
            process = subprocess.Popen(Args).wait()
        except:
            pass

class Compile(Command):
    def _Execute(self, args):
        MSBuildPath = GetRegistryData("HKLM:SOFTWARE/Microsoft/MSBuild/ToolsVersions/4.0/MSBuildToolsPath")
        if len(MSBuildPath) > 0:
            ProjectName = GetProjectName()

            BatchFilePath = Path(GetAssociatedEngineDir()) / 'Engine/Build/BatchFiles/Build.bat'
            if not os.path.exists(BatchFilePath):
                logging.error(f"File does not exist. {str(BatchFilePath)}")
                return

            Commands = [
                f"{str(BatchFilePath)}",
                ProjectName+'Editor',
                'Win64',
                c.CompilationConfiguration,
                GetUProjectPath(),
                '-WaitMutex'
            ]

            try:
                BuildProcess = subprocess.Popen(Commands).wait()
            except:
                pass
        else:
            logging.error("MSBuild not installed. Use 'python UEDT.py compile -help' to get information about MSBuild tool installation.")

class LaunchMode(IntFlag):
    Opti = auto()
    Trace = auto()
    Debug = auto()

class Launch(Command):
    def _Execute(self, args):
        Mode = None

        if args.get("mode") is not None:
            Mode = args.get("mode")
        elif args.get("m") is not None:
            Mode = args.get("m")
        
        Args = [
            f"{str(Path(GetAssociatedEngineDir()) / 'Engine/Binaries/Win64/UnrealEditor.exe')}",
            f"{str(Path(GetUProjectPath()))}",
            "-game",
            "-log",
        ]
        
        if Mode is not None:
            if Mode != "":
                Data = self.ParseLaunchMode(Mode)
                
                if Data & LaunchMode.Debug.value:
                    Args += [
                        "-debug"
                    ]

                if Data & LaunchMode.Opti.value:           
                    Args += [
                        "-noailogging",
                        "-nosound",
                        "-novsync",
                        "-nogpucrashdebugging",
                        "-nomcp", # No multiplayer.
                        "-noscreenmessages",
                        "-noverifygc",
                        "-nothreadtimeout",
                        "-unattended",
                    ]
                    
                if Data & LaunchMode.Trace.value:
                    if LaunchUnrealInsights():
                        import time
                        time.sleep(1) # Small delay to let UnrealInsights warmup, otherwise it might not notice that the game is launching.
                        
                    Args += [
                        "-trace=default,memory,metadata,assetmetadata"
                    ]
            
        logging.info(f"Launching {GetProjectName()}...")

        FireAndForgetProcess(Args)
        
    def ParseLaunchMode(self, Mode):
        PreparedString = "".join(Mode.split()).lower()
        Modes = PreparedString.split("|")
        
        Result = 0
        
        for e in LaunchMode:
            if e.name.lower() in Modes:
                Result |= e.value

        return Result


class CookProject(Command):
    def _Execute(self, args):
        Args = [
            f"{str(Path(GetAssociatedEngineDir()) / 'Engine/Binaries/Win64/UnrealEditor.exe')}",
            f"{str(Path(GetUProjectPath()))}",
            "-run=cook",
            "-targetplatform=Win64",
            "-cookonthefly",
            "-iterate",
            # Due to problems with blueprint nativization, it is by default disabled in building process.
            #"-ini:Game[/Script/UnrealEd.ProjectPackagingSettings]:BlueprintNativizationMethod=Disabled",
            #"-map=FirstMap+SecondMap",
            #"-clean",
        ]

        try:
            BuildProcess = subprocess.Popen(Args).wait()
        except:
            pass

class DataValidator(Command):
    def _Execute(self, args):
        args = f"{str(Path(GetAssociatedEngineDir()) / 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe')} {str(Path(GetUProjectPath()))} -run=DataValidation"

        try:
            process = subprocess.Popen(args.split()).wait()
        except:
            pass


class GauntletTest(Command):      
    def _Execute(self, args):
        
        if args.get("target") is None:
            print("Cannot perform GauntletTest. Target not provided.")
            return
        
        args = f"{GetUATPath()} BuildCookRun -project={GetUProjectPath()} -platform=Win64 -configuration=Development -build -cook -pak -stage"
        print(args)
        
        try:
            process = subprocess.Popen(args.split()).wait()
        except:
            pass
        
        print("\n################\n# START GAUNTLET TEST\n################")
        
        args = f"{GetUATPath()} RunUnreal -project={GetUProjectPath()} -platform=Win64 -configuration=Development -build=local -test={args.target}"

        try:
            process = subprocess.Popen(args.split()).wait()
        except:
            pass

class Test(Command):
    def _Execute(self, args):

        testFiles = [GetUProjectPath()]

        changelist = perforceHandler.CreateNewChangelist("Test")
        perforceHandler.EditFiles(changelist, testFiles)
        perforceHandler.RevertFiles(testFiles)

        #perforceHandler.SubmitChangelist(changelist)

class ShowChangelist(Command):
    def _Execute(self, args):
        os.system('p4 changes -m 1 -s submitted //GiantsUprising/Master/...')

class LaunchUnrealInsightsTool(Command):
    def _Execute(self, args):
        LaunchUnrealInsights()

#endregion

#region Commands
"""
    Commands
"""

commands = [
    ["build", Build, "Build project.",   
        [
            ["--configuration", "Override default configuration"],
            ["--c", "Override default configuration"],
        ]
    ],
    ["clean", Clean, "Clean project by removing Binaries folder, Intermediate folder and some Saved folders.", []],
    ["compile", Compile, "Compile project using MSBuild tool.", 
        [
            ["--configuration", "Override default configuration (available: Development, Shipping)"],
            ["--c", "Override default configuration (available: Development, Shipping)"],
        ]
    ],
    ["launch", Launch, "Launch the game. Optionally set an apropriate launch mode.",
        [
            ["--mode", f"Set a launch mode. Available modes {[e.name for e in LaunchMode]}"],
            ["-m", f"Set a launch mode. Available modes {[e.name for e in LaunchMode]}"]
        ]
    ],
    ["ui", LaunchUnrealInsightsTool, "Launch UnrealInsights tool.", []],
    ["rebuildlight", RebuildLighting, "Rebuild Lighting", []],
    ["cook", CookProject, "Cook content (for shipping build testing).", []],
    ["validate", DataValidator, 'Invoke DataValidation command, data validation plugin enabled required for this to run.', []],
    ["showChangelist", ShowChangelist, 'Returns changelist number of a registered repository.', []],
    ["gauntlet", GauntletTest, 'Run Gauntlet automation test. Requires \'target\' argument.',
        [
            ["--target", "Provide a name of a test to execute."]
        ]
    ],
    ["fixBinaryPermissions", FixBinaryPermissions, 'Set all dll and pdb file permissions to read-write', []],
    ["test", Test, 'Sandbox test command. Does what you tell it.', []],
]
#endregion Commands

#region Entry
"""
    Entry
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Unreal Engine Development Tool")

    logging.basicConfig(filename='UEDT.log', encoding='utf-8', level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    CommandHelp = '\n'.join([f"{command[0]} - {command[2]}" for command in commands])

    subparsers = parser.add_subparsers(dest='command')

    for command in commands:
        command_paraser = subparsers.add_parser(command[0], help=command[2])
        subcommands = command[3]
        if len(subcommands) > 0:
            for subcommand in subcommands:
                command_paraser.add_argument(subcommand[0], help=subcommand[1])
    
    args = parser.parse_args()

    CommandToExecute = None

    for command in commands:
        if args.command == command[0]:
            CommandToExecute = command[1]
            break

    if CommandToExecute is not None:
        CommandToExecute(vars(args))
    else:
        logging.getLogger().info(f'No such command "{args.command}"')
#endregion Entry
