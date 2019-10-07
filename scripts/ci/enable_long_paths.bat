:: Enable long paths on Windows (needed when building since node_modules can create deep hierarchies)

REG ADD "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
