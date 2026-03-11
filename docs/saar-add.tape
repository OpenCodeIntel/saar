# saar-add.tape -- Tribal knowledge correction GIF
# Usage: vhs docs/saar-add.tape

Output docs/saar-add.gif
Set FontSize 13
Set Width 880
Set Height 300
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
Type `saar add "Never use npm. This project uses bun only"`
Enter
Sleep 1500ms
Type `saar add --off-limits "billing/ frozen until Q3"`
Enter
Sleep 1500ms
Type `saar add --domain "Workspace means tenant not directory"`
Enter
Sleep 1500ms
Sleep 2s
