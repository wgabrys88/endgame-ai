import os
def run(board):
    os.makedirs("runtime/comms",exist_ok=True)
    if not os.path.exists("runtime/comms/human.txt"):
        open("runtime/comms/human.txt","w").write("Colony active. Write here to communicate.")
    return None
