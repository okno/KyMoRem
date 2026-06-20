#ifndef AppVersion
#define AppVersion "0.1.1"
#endif

#ifndef Arch
#define Arch "x64"
#endif

#ifndef SourceDir
#define SourceDir "..\..\dist\windows\x64\KyMoRem"
#endif

#define AppName "KyMoRem"
#define AppFullName "KyMoRem - Keyboard Mouse Remote"
#define AppPublisher "Pawel Zorzan Urban AKA okno"
#define AppExeName "kymorem-agent.exe"

[Setup]
AppId={{A55D2381-37F8-4E41-97F5-4B1EEC208C01}-{#Arch}}
AppName={#AppFullName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/okno/KyMoRem
AppSupportURL=https://github.com/okno/KyMoRem/issues
DefaultDirName={autopf}\KyMoRem
DefaultGroupName=KyMoRem
DisableProgramGroupPage=yes
OutputBaseFilename=KyMoRem-{#AppVersion}-windows-{#Arch}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=no
ChangesEnvironment=no

#if Arch == "x64"
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ch"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
it.WelcomeLabel1=Benvenuto nell'installazione di KyMoRem
it.WelcomeLabel2=KyMoRem condivide mouse e tastiera tra dispositivi sulla stessa rete.
en.WelcomeLabel1=Welcome to the KyMoRem installer
en.WelcomeLabel2=KyMoRem shares mouse and keyboard across devices on the same network.
ch.WelcomeLabel1=Willkommen beim KyMoRem Installer
ch.WelcomeLabel2=KyMoRem teilt Maus und Tastatur zwischen Geraeten im gleichen Netzwerk.

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\KyMoRem Host"; Filename: "{app}\{#AppExeName}"; Parameters: "host --token kymorem-local-default-change-me"; WorkingDir: "{app}"
Name: "{group}\KyMoRem Device Demo"; Filename: "{app}\{#AppExeName}"; Parameters: "device --host 127.0.0.1:54865 --token kymorem-local-default-change-me --demo"; WorkingDir: "{app}"
Name: "{group}\Uninstall KyMoRem"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KyMoRem Host"; Filename: "{app}\{#AppExeName}"; Parameters: "host --token kymorem-local-default-change-me"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "sample-frame"; Description: "KyMoRem protocol smoke test"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\KyMoRem"
