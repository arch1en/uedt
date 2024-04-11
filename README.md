# Unreal Engine Development Tool

Available commands:

- `build`
  - Build project.
- `clean`
  - Clean project by removing Binaries folder, Intermediate folder and some Saved folders.
- `compile`
  - Compile project using MSBuild toolkit.
- `launch`
  - Launch the game. Optionally set an apropriate launch mode.
    - `-m` - Set a launch mode. Available modes "opti", "trace", "debug".
- `ui`
  - Launch UnrealInsights tool.
- `rebuildlight`
  - Rebuild Lighting.
- `cook`
  - Cook content (for shipping build testing).
- `validate`
  - Invoke DataValidation command, data validation plugin enabled required for this to run.
- `showChangelist`
  - Returns changelist number of a registered repository.
- `gauntlet`
  - Run Gauntlet automation test. Requires `target` argument.
    - `--target` - Provide a name of a test to execute.
- `fixBinaryPermissions`
  - Set all dll and pdb file permissions to read-write.
