"""rest: the organism pauses. Emits the terminal 'rest' signal. With a goal, the loop
stops here; with no goal and idle_initiative on, the loop wakes the mind again."""
log("resting")
emit("rest")
