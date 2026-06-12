import glob
def run(board):
    board["colony_size"]=len(glob.glob("events-child-*.jsonl"))
    return None
