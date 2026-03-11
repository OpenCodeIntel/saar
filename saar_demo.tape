# saar demo GIF -- VHS tape
# Run: vhs saar_demo.tape

Output saar_demo.gif
Set FontSize 15
Set Width 900
Set Height 550
Set Theme "Dracula"
Set TypingSpeed 40ms
Set PlaybackSpeed 0.8
Set Padding 24
Set MarginFill "#282a36"
Set BorderRadius 12
Set WindowBar Colorful

# Start in a clean project
Type "cd ~/Desktop/studymate-api"
Sleep 300ms
Enter
Sleep 500ms

# Show what we're working with
Type "ls"
Enter
Sleep 800ms

# The magic command
Type "saar extract ."
Sleep 400ms
Enter
Sleep 8000ms

# Show the output file
Type "cat AGENTS.md"
Enter
Sleep 1500ms

# Show diff detection
Type "# two weeks later..."
Sleep 500ms
Enter

Type "saar diff ."
Sleep 300ms
Enter
Sleep 3000ms

Sleep 2000ms
