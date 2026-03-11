# saar-demo.tape -- Core demo GIF
# Usage: vhs docs/saar-demo.tape

Output docs/saar-demo.gif
Set FontSize 13
Set Width 880
Set Height 460
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 45ms
Set Shell "zsh"
Set Framerate 24
Env PATH "/Users/devanshu/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"

Hide
Type "cd /tmp/studymate-demo && clear"
Enter
Show

Sleep 500ms
Type "ls"
Enter
Sleep 1200ms

Ctrl+L
Sleep 300ms

Type "saar extract . --no-interview"
Enter
Sleep 12s

Sleep 4s
