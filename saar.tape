# saar.tape — full viral demo
# To run: cd /tmp && vhs /Users/devanshu/Desktop/codeintel/saar/saar.tape

Output saar_demo.gif

Set FontSize 14
Set Width 980
Set Height 560
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set PlaybackSpeed 0.85
Set Padding 24
Set MarginFill "#1e1e2e"
Set BorderRadius 12
Set WindowBar Colorful
Set WindowBarSize 26

Hide
Type "export PATH='/Users/devanshu/.local/bin:/opt/homebrew/bin:$PATH'"
Enter
Type "cd /tmp/studymate-demo"
Enter
Type "clear"
Enter
Show

# Scene 1 — show the project
Type "ls backend/routes/"
Enter
Sleep 1000ms

# Scene 2 — the one command
Type "saar extract . --no-interview"
Enter
Sleep 9500ms

# Scene 3 — size check
Type "wc -l AGENTS.md"
Enter
Sleep 800ms
Type "echo '70 lines. Claude will read every single one.'"
Enter
Sleep 1200ms

# Scene 4 — add a rule instantly
Type "saar add 'Never use npm — this project uses bun'"
Enter
Sleep 1200ms

# Scene 5 — diff
Type "saar diff ."
Enter
Sleep 3500ms

Sleep 2000ms
