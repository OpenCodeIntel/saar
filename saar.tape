Output saar_demo.gif

Set FontSize 14
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set PlaybackSpeed 0.82
Set Padding 30
Set MarginFill "#1e1e2e"
Set BorderRadius 14
Set WindowBar Colorful
Set WindowBarSize 28

# Scene 1: show the project -- clean start, no setup noise
Type "ls"
Enter
Sleep 1200ms

# Scene 2: one command
Type "saar extract . --no-interview"
Enter
Sleep 11000ms

# Scene 3: add a correction
Type "saar add 'Never use npm -- this project uses bun'"
Enter
Sleep 2000ms

# Scene 4: the score
Type "saar stats ."
Enter
Sleep 6000ms

Sleep 3000ms
