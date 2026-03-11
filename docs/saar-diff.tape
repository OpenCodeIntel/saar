# saar-diff.tape -- Staleness detection GIF
# Usage: vhs docs/saar-diff.tape

Output docs/saar-diff.gif
Set FontSize 13
Set Width 880
Set Height 360
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
Type "# 2 weeks later. did anything change?"
Enter
Sleep 1000ms
Type "saar diff ."
Enter
Sleep 10s
Sleep 3s
